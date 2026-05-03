import streamlit as st
import json
import re
import time
import os
import traceback
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

# 确保从项目根目录加载 .env
_ENV_FILE = Path(__file__).parent / ".env"
load_dotenv(_ENV_FILE, override=True)

WORLD_STATE_FILE = "world_state.md"


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

def read_world_state():
    """读取世界状态文件全文。"""
    if not os.path.exists(WORLD_STATE_FILE):
        return "（世界状态文件不存在）"
    with open(WORLD_STATE_FILE, "r", encoding="utf-8") as f:
        return f.read()


def load_config():
    """加载配置，返回 dict。"""
    return {
        "api_key": os.getenv("OPENAI_API_KEY", ""),
        "base_url": os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        "model": os.getenv("MODEL_NAME", "gpt-4o"),
    }


def call_llm(system_prompt, user_prompt, json_mode=False, temperature=0.7):
    """通用 LLM 调用。json_mode=True 时启用 JSON Mode。"""
    config = load_config()
    if not config["api_key"] or config["api_key"] == "your-api-key-here":
        raise RuntimeError(
            "API Key 未配置。请编辑 .env 文件，设置 OPENAI_API_KEY 后再试。"
        )

    client = OpenAI(
        api_key=config["api_key"],
        base_url=config["base_url"],
        timeout=120.0,
        max_retries=1,
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    kwargs = {
        "model": config["model"],
        "messages": messages,
        "temperature": temperature,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    response = client.chat.completions.create(**kwargs)
    return response.choices[0].message.content


def parse_json_response(raw_response):
    """尝试解析 LLM 返回的 JSON。先直接解析，失败后用正则提取。"""
    try:
        return json.loads(raw_response.strip())
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", raw_response)
        if match:
            return json.loads(match.group())
        raise


# ── 主编剧 System Prompt ──

EDITOR_SYSTEM_PROMPT = """你是一位资深网文主编剧。请根据用户指令和当前世界状态，生成下一章的剧本。
你必须严格按照以下JSON格式返回，字段不得缺少或多余：

{"chapter_number": int, "scene": str, "conflict": str, "emotion_level": "高/中/低", "key_events": [str, ...], "foreshadowing_to_plant": str, "characters_involved": [str, ...], "status_changes": {角色: 状态描述, ...}}

注意：
1. emotion_level只能是"高"、"中"、"低"三个值之一。
2. key_events至少包含3个事件节点。
3. status_changes要明确标注本章结束后各角色的状态变化。
4. 必须紧密结合世界状态中已记录的角色、伏笔和情节进度，不得凭空编造冲突信息。
5. 你只能返回 JSON，不要附带任何解释、Markdown 代码块标记或其他文字。"""


# ── 创作班组 System Prompt ──

CREW_SYSTEM_PROMPT = """你是一位经验丰富的网文写手。你将收到一份结构化的章节剧本（JSON格式）和当前的世界状态。
请根据剧本指令，写出一段小说正文（800-1500字）。

写作要求：
1. 注意描写细节，包括环境、动作、对话和内心感受。
2. 根据剧本中的 emotion_level 调整行文节奏——"高"则加强紧张感和冲突渲染，"低"则侧重内心独白和环境氛围。
3. 必须紧密结合世界状态中记录的角色特征和状态（如伤势、情绪、伏笔等），在描写中自然体现，不得凭空编造。
4. 严格按照剧本中的 key_events 顺序推进情节，每个事件节点都要有对应的段落。
5. 对话要符合角色性格，动作描写要体现角色的身体状态。
6. 你只能返回小说正文，不要附带任何解释、评价或 Markdown 标记。"""

# ── 质检员 System Prompt ──

QUALITY_CHECKER_SYSTEM_PROMPT = """你是一位严格的小说逻辑审查员。你需要对比三份材料：世界状态、本章剧本、正文初稿。

请找出正文初稿中至少1个逻辑或事实矛盾，并提供具体的修改建议。同时，找出世界状态里一个可用的未回收伏笔，建议如何在当前情节中使用它。

你必须严格按照以下JSON格式返回，字段不得缺少或多余：

{"logic_conflicts": [{"type": "事实矛盾/性格不一致/时间线错误/设定冲突", "description": "具体描述矛盾所在", "suggestion": "具体的修改建议"}], "foreshadowing_suggestion": {"available_foreshadowing": "伏笔ID和内容", "usage_tip": "在当前场景中的具体使用方式"}}

注意：
1. 如果你没有发现任何逻辑矛盾，logic_conflicts 返回空列表 []。
2. foreshadowing_suggestion 必须始终提供一个建议，即使没有明显的未回收伏笔也要尽力挖掘。
3. description 和 suggestion 必须具体、可操作，不能泛泛而谈。
4. 你只能返回 JSON，不要附带任何解释、Markdown 代码块标记或其他文字。"""

# ── 修正重生成 System Prompt ──

REVISER_SYSTEM_PROMPT = """你是一位精益求精的网文修改专家。你会收到原始正文初稿、质检报告（指出了逻辑矛盾）和原始剧本。

请根据质检报告中的每一条问题和建议，对正文进行修正和重写，输出修正后的完整小说正文。

修改要求：
1. 必须逐一处理质检报告中指出的每一条逻辑矛盾，不可遗漏。
2. 如果质检报告提供了伏笔利用建议，请自然地融入修正后的正文中。
3. 修正时应尽量保留原文的优点和流畅的段落，只对有问题的地方进行精准修改或补充。
4. 修正后的正文应保持800-1500字的篇幅。
5. 你只能返回修正后的小说正文，不要附带任何解释、修改说明或 Markdown 标记。"""

# ── 世界状态更新 System Prompt ──

STATE_UPDATER_SYSTEM_PROMPT = """你是一位严谨的世界状态记录员（史官）。你会收到本章的终稿正文和当前世界状态。

请根据终稿内容，提取本章产生的状态变更，用 Markdown 格式输出需要追加到世界状态文件中的内容。

输出格式要求（严格遵循）：
1. 用 ## 第N章更新 作为标题
2. 包含 ### 新增状态 段落，用 - 列表记录每个角色的状态变化
3. 包含 ### 本章伏笔推进 段落，记录已有伏笔在本章的进展
4. 包含 ### 新埋伏笔 段落，记录本章新埋下的伏笔（用 V00X 编号）
5. 内容要简洁准确，每条不超过一句话
6. 你只能返回需要追加的 Markdown 内容，不要附带任何解释或其他文字。"""


def get_world_state_text():
    """读取世界状态（带缓存：仅在文件变更时重读）。"""
    need_reload = True
    if "world_state_text" in st.session_state and "world_state_mtime" in st.session_state:
        try:
            current_mtime = os.path.getmtime(WORLD_STATE_FILE)
            if current_mtime == st.session_state["world_state_mtime"]:
                need_reload = False
        except OSError:
            pass
    if need_reload:
        text = read_world_state()
        st.session_state["world_state_text"] = text
        try:
            st.session_state["world_state_mtime"] = os.path.getmtime(WORLD_STATE_FILE)
        except OSError:
            st.session_state["world_state_mtime"] = 0
    return st.session_state["world_state_text"]


def parse_world_state(md_text):
    """将 world_state.md 全文解析为结构化 dict。"""
    result = {
        "current_time": {},
        "characters": [],
        "unresolved_foreshadowing": [],
        "resolved_foreshadowing": [],
    }

    # 按 ## 拆分段落
    sections = {}
    current_heading = None
    current_lines = []

    for line in md_text.split("\n"):
        if line.startswith("## "):
            if current_heading:
                sections[current_heading] = "\n".join(current_lines)
            current_heading = line[3:].strip()
            current_lines = []
        else:
            current_lines.append(line)
    if current_heading:
        sections[current_heading] = "\n".join(current_lines)

    # 解析时间线段落
    timeline_text = sections.get("当前时间线", "")
    for line in timeline_text.split("\n"):
        line = line.strip()
        if line.startswith("- "):
            item = line[2:]
            if "：" in item:
                key, val = item.split("：", 1)
                key_map = {"章节进度": "chapter_progress", "时间": "time", "地点": "location"}
                mapped = key_map.get(key.strip(), key.strip())
                result["current_time"][mapped] = val.strip()

    # 解析角色状态
    char_text = sections.get("角色状态", "")
    for line in char_text.split("\n"):
        line = line.strip()
        if line.startswith("- "):
            item = line[2:]
            if "：" in item:
                name, rest = item.split("：", 1)
                mood = ""
                desc = rest.strip()
                if "，当前情绪：" in rest:
                    desc_part, mood = rest.rsplit("，当前情绪：", 1)
                    desc = desc_part.strip()
                    mood = mood.strip()
                result["characters"].append({
                    "name": name.strip(),
                    "description": desc,
                    "mood": mood,
                })

    # 解析伏笔（未回收 / 已回收）
    for section_name, target_key in [
        ("未回收伏笔", "unresolved_foreshadowing"),
        ("已回收伏笔", "resolved_foreshadowing"),
    ]:
        f_text = sections.get(section_name, "")
        for line in f_text.split("\n"):
            line = line.strip()
            if line.startswith("- ") and "：" in line:
                item = line[2:]
                fid, content = item.split("：", 1)
                if fid.strip() not in ("（暂无）", ""):
                    result[target_key].append({
                        "id": fid.strip(),
                        "content": content.strip(),
                    })

    return result


# ---------------------------------------------------------------------------
# 流水线阶段函数（全部使用真实 LLM 调用）
# ---------------------------------------------------------------------------

def generate_script(user_input, world_state):
    """主编剧 Agent：调用 LLM 生成章节剧本 JSON，含重试逻辑。"""
    user_prompt = f"用户指令：{user_input}\n\n当前世界状态：\n{world_state}\n\n请输出下一章剧本JSON。"

    last_error = None
    raw_response = None
    last_traceback = ""

    for attempt in range(2):
        try:
            t0 = time.time()
            raw_response = call_llm(
                EDITOR_SYSTEM_PROMPT, user_prompt, json_mode=True, temperature=0.7
            )
            elapsed = time.time() - t0
            st.write(f"[DEBUG] LLM 调用耗时: {elapsed:.1f}s (第{attempt+1}次)")
            result = parse_json_response(raw_response)
            required = [
                "chapter_number", "scene", "conflict", "emotion_level",
                "key_events", "foreshadowing_to_plant",
                "characters_involved", "status_changes",
            ]
            missing = [k for k in required if k not in result]
            if missing:
                raise ValueError(f"返回 JSON 缺少字段：{', '.join(missing)}")
            return result
        except Exception as e:
            last_error = e
            last_traceback = traceback.format_exc()
            if attempt == 0:
                st.write(f"[DEBUG] 第1次尝试失败: {type(e).__name__}: {e}")
                continue

    return {
        "_error": True,
        "message": (
            f"剧本生成失败（重试 2 次后仍无法解析）。\n\n"
            f"异常类型：{type(last_error).__name__}\n"
            f"异常内容：{last_error}\n\n"
            f"请求URL：{os.getenv('OPENAI_BASE_URL', '?')}\n"
            f"模型名称：{os.getenv('MODEL_NAME', '?')}"
        ),
        "raw_response": raw_response or "(无返回内容)",
        "_traceback": last_traceback,
    }


def generate_draft(script, world_state):
    """创作班组 Agent：根据剧本生成小说正文。"""
    script_json = json.dumps(script, ensure_ascii=False, indent=2)
    user_prompt = (
        f"世界状态：\n{world_state}\n\n"
        f"本章剧本：\n{script_json}\n\n"
        f"请根据剧本写出小说正文。"
    )

    last_error = None
    for attempt in range(2):
        try:
            t0 = time.time()
            raw_response = call_llm(CREW_SYSTEM_PROMPT, user_prompt, temperature=0.8)
            elapsed = time.time() - t0
            st.write(f"[DEBUG] 创作班组 LLM 耗时: {elapsed:.1f}s (第{attempt+1}次)")
            draft = raw_response.strip()
            if len(draft) < 200:
                raise ValueError(f"正文过短（{len(draft)}字），可能生成失败")
            return draft
        except Exception as e:
            last_error = e
            if attempt == 0:
                st.write(f"[DEBUG] 创作班组第1次尝试失败: {type(e).__name__}: {e}")
                continue

    return f"[初稿生成失败] 重试2次后仍失败。错误：{type(last_error).__name__}: {last_error}"


def quality_check(script, draft, world_state):
    """质检员 Agent：逻辑事实核查 + 伏笔利用建议。"""
    script_json = json.dumps(script, ensure_ascii=False, indent=2)
    user_prompt = (
        f"世界状态：\n{world_state}\n\n"
        f"本章剧本：\n{script_json}\n\n"
        f"正文初稿：\n{draft}\n\n"
        f"请检查逻辑矛盾，并提供伏笔利用建议。"
    )

    last_error = None
    for attempt in range(2):
        try:
            t0 = time.time()
            raw_response = call_llm(
                QUALITY_CHECKER_SYSTEM_PROMPT, user_prompt, json_mode=True, temperature=0.5
            )
            elapsed = time.time() - t0
            st.write(f"[DEBUG] 质检员 LLM 耗时: {elapsed:.1f}s (第{attempt+1}次)")
            result = parse_json_response(raw_response)
            if "logic_conflicts" not in result or "foreshadowing_suggestion" not in result:
                raise ValueError("返回 JSON 缺少必要字段")
            return result
        except Exception as e:
            last_error = e
            if attempt == 0:
                st.write(f"[DEBUG] 质检员第1次尝试失败: {type(e).__name__}: {e}")
                continue

    return {
        "logic_conflicts": [
            {
                "type": "系统错误",
                "description": f"质检员Agent调用失败：{type(last_error).__name__}: {last_error}",
                "suggestion": "请人工审查初稿",
            }
        ],
        "foreshadowing_suggestion": {
            "available_foreshadowing": "N/A",
            "usage_tip": "质检失败，请人工审查",
        },
    }


def revise_draft(draft, quality_report, script):
    """修正重生成：根据质检报告修正正文。"""
    report_json = json.dumps(quality_report, ensure_ascii=False, indent=2)
    script_json = json.dumps(script, ensure_ascii=False, indent=2)
    user_prompt = (
        f"以下正文存在逻辑问题，需要修正：\n\n"
        f"原始剧本：\n{script_json}\n\n"
        f"原始正文：\n{draft}\n\n"
        f"质检报告：\n{report_json}\n\n"
        f"请修正上述问题，重写正文。"
    )

    last_error = None
    for attempt in range(2):
        try:
            t0 = time.time()
            raw_response = call_llm(REVISER_SYSTEM_PROMPT, user_prompt, temperature=0.7)
            elapsed = time.time() - t0
            st.write(f"[DEBUG] 修正重生成 LLM 耗时: {elapsed:.1f}s (第{attempt+1}次)")
            revised = raw_response.strip()
            if len(revised) < 200:
                raise ValueError(f"修正后正文过短（{len(revised)}字），可能生成失败")
            return revised
        except Exception as e:
            last_error = e
            if attempt == 0:
                st.write(f"[DEBUG] 修正重生成第1次尝试失败: {type(e).__name__}: {e}")
                continue

    return f"[修正重生成失败] 重试2次后仍失败。错误：{type(last_error).__name__}: {last_error}\n\n保留原稿：\n\n{draft}"


def update_world_state(final_draft, script, world_state_text):
    """世界知识库 Agent：提取状态变更，更新世界状态文件。"""
    script_json = json.dumps(script, ensure_ascii=False, indent=2)
    chapter_num = script.get("chapter_number", "?")
    user_prompt = (
        f"当前世界状态：\n{world_state_text}\n\n"
        f"本章剧本：\n{script_json}\n\n"
        f"本章终稿正文：\n{final_draft}\n\n"
        f"请提取本章的状态变更，输出需要追加到世界状态文件的内容。"
    )

    last_error = None
    new_entries = ""
    for attempt in range(2):
        try:
            t0 = time.time()
            raw_response = call_llm(
                STATE_UPDATER_SYSTEM_PROMPT, user_prompt, temperature=0.4
            )
            elapsed = time.time() - t0
            st.write(f"[DEBUG] 状态更新 LLM 耗时: {elapsed:.1f}s (第{attempt+1}次)")
            new_entries = raw_response.strip()
            if len(new_entries) < 50:
                raise ValueError(f"状态更新内容过短（{len(new_entries)}字）")
            break
        except Exception as e:
            last_error = e
            if attempt == 0:
                st.write(f"[DEBUG] 状态更新第1次尝试失败: {type(e).__name__}: {e}")
                continue
    else:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        new_entries = (
            f"## 第{chapter_num}章更新（{ts}）\n\n"
            f"### 新增状态\n"
            f"- 状态更新失败：{type(last_error).__name__}: {last_error}\n\n"
            f"### 本章伏笔推进\n- （自动提取失败）\n\n"
            f"### 新埋伏笔\n- （自动提取失败）\n"
        )

    # 追加写入世界状态文件
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    header = f"\n\n---\n\n## 第{chapter_num}章更新（{timestamp}）\n\n"
    full_entry = header + new_entries.lstrip("\n")

    try:
        with open(WORLD_STATE_FILE, "a", encoding="utf-8") as f:
            f.write(full_entry)
        st.write(f"[DEBUG] 世界状态已写入 {WORLD_STATE_FILE}")
    except OSError as e:
        st.warning(f"世界状态文件写入失败：{e}")

    return full_entry


# ---------------------------------------------------------------------------
# 流水线编排
# ---------------------------------------------------------------------------

def run_pipeline(user_input, world_state):
    """执行完整的创作流水线，返回各阶段结果。"""
    results = {}

    with st.status("流水线执行中……", expanded=True) as status:
        # 步骤 1：生成剧本
        status.update(label="步骤 1/5：主编剧正在生成剧本……")
        try:
            results["script"] = generate_script(user_input, world_state)
        except RuntimeError as e:
            status.update(label="步骤 1/5：主编剧剧本生成失败 ✗", state="error")
            results["_pipeline_error"] = str(e)
            return results
        if isinstance(results["script"], dict) and results["script"].get("_error"):
            status.update(label="步骤 1/5：主编剧剧本生成失败 ✗", state="error")
            results["_pipeline_error"] = results["script"]["message"]
            return results
        status.update(label="步骤 1/5：主编剧剧本生成完成 ✓")

        # 步骤 2：生成初稿
        status.update(label="步骤 2/5：创作班组正在撰写初稿……")
        results["draft"] = generate_draft(results["script"], world_state)
        status.update(label="步骤 2/5：初稿撰写完成 ✓")

        # 步骤 3：质检
        status.update(label="步骤 3/5：质检员正在审查初稿……")
        results["quality_report"] = quality_check(
            results["script"], results["draft"], world_state
        )
        status.update(label="步骤 3/5：质检报告生成完成 ✓")

        # 步骤 4：修正
        status.update(label="步骤 4/5：正在根据质检意见修正初稿……")
        results["final_draft"] = revise_draft(
            results["draft"], results["quality_report"], results["script"]
        )
        status.update(label="步骤 4/5：修正终稿完成 ✓")

        # 步骤 5：更新世界状态
        status.update(label="步骤 5/5：世界知识库正在更新世界状态……")
        results["state_update"] = update_world_state(
            results["final_draft"], results["script"], world_state
        )
        status.update(label="步骤 5/5：世界状态更新完成 ✓", state="complete")

    return results


# ---------------------------------------------------------------------------
# UI 渲染
# ---------------------------------------------------------------------------

def render_sidebar():
    """侧边栏：世界状态预览（结构化展示）。"""
    world_state_text = get_world_state_text()
    ws = parse_world_state(world_state_text)

    with st.sidebar:
        st.header("世界状态")

        # .env 配置检查
        config = load_config()
        if not config["api_key"] or config["api_key"] == "your-api-key-here":
            st.warning(
                "API Key 未配置。请复制 `.env.example` 为 `.env`，"
                "填入真实的 `OPENAI_API_KEY`。"
            )

        # ── 当前进度 ──
        st.subheader("当前进度")
        timeline = ws["current_time"]
        if timeline:
            cols = st.columns(3)
            cols[0].metric("章节", timeline.get("chapter_progress", "-"))
            cols[1].metric("时间", timeline.get("time", "-"))
            cols[2].metric("地点", timeline.get("location", "-"))

        st.divider()

        # ── 角色状态 ──
        st.subheader("角色状态")
        characters = ws["characters"]
        if characters:
            for char in characters:
                label = char["name"]
                if char.get("mood"):
                    label += f"  [{char['mood']}]"
                with st.expander(label, expanded=False):
                    st.caption(char.get("description", ""))
        else:
            st.caption("（暂无角色数据）")

        st.divider()

        # ── 伏笔 ──
        st.subheader("伏笔")
        unresolved = ws["unresolved_foreshadowing"]
        if unresolved:
            for f in unresolved:
                st.warning(f"**{f['id']}** {f['content']}")
        else:
            st.caption("无未回收伏笔")

        resolved = ws["resolved_foreshadowing"]
        if resolved:
            for f in resolved:
                st.info(f"~~{f['id']}~~ {f['content']}（已回收）")

        st.divider()
        st.caption("管理世界状态：在页面顶部展开编辑面板")


def render_results(results):
    """渲染流水线各阶段的输出。"""
    # 流水线错误
    if "_pipeline_error" in results:
        st.error(f"流水线执行中断：{results['_pipeline_error']}")
        if "script" in results and isinstance(results["script"], dict):
            raw = results["script"].get("raw_response", "")
            tb = results["script"].get("_traceback", "")
            if raw:
                with st.expander("查看 LLM 原始返回"):
                    st.code(raw)
            if tb:
                with st.expander("查看完整堆栈"):
                    st.code(tb)

    script = results["script"]
    draft = results["draft"]
    quality_report = results["quality_report"]
    final_draft = results["final_draft"]
    state_update = results["state_update"]

    # ---------- 主编剧剧本 ----------
    st.markdown("### 主编剧剧本")
    with st.expander("点击展开/折叠 JSON 剧本", expanded=False):
        if isinstance(script, dict) and script.get("_error"):
            st.error(script.get("message", "未知错误"))
            if script.get("raw_response"):
                st.caption("LLM 原始返回：")
                st.code(script["raw_response"])
        else:
            st.json(script)

    # ---------- 初稿正文 ----------
    st.markdown("### 初稿正文")
    st.markdown(draft)

    # ---------- 质检报告 ----------
    st.markdown("### 质检报告")

    logic_conflicts = quality_report.get("logic_conflicts", [])
    if logic_conflicts:
        for i, conflict in enumerate(logic_conflicts, 1):
            st.warning(
                f"**问题 {i}：{conflict.get('type', '')}**\n\n"
                f"{conflict.get('description', '')}\n\n"
                f"**修改建议：**{conflict.get('suggestion', '')}"
            )
    else:
        st.success("未发现逻辑矛盾。")

    foreshadowing = quality_report.get("foreshadowing_suggestion", {})
    if foreshadowing:
        st.info(
            f"**伏笔利用建议**\n\n"
            f"**可用伏笔：**{foreshadowing.get('available_foreshadowing', '')}\n\n"
            f"**使用建议：**{foreshadowing.get('usage_tip', '')}"
        )

    # ---------- 修正终稿 ----------
    st.markdown("### 修正终稿")
    st.markdown(final_draft)

    # ---------- 世界状态更新日志 ----------
    st.markdown("### 世界状态更新日志")
    st.info(state_update)


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------

def main():
    st.set_page_config(
        page_title="墨灵 · Demo控制台",
        page_icon="",
        layout="wide",
    )

    st.title("墨灵 · Demo控制台")
    st.caption("多Agent协同网文创作系统 — 概念验证Demo")

    render_sidebar()

    # ── 世界状态管理面板 ──
    with st.expander("查看/编辑世界状态", expanded=False):
        col_a, col_b = st.columns([3, 1])
        with col_a:
            edited_text = st.text_area(
                "编辑 world_state.md",
                value=get_world_state_text(),
                height=280,
                label_visibility="collapsed",
                key="world_state_editor",
            )
        with col_b:
            st.markdown("**当前结构化预览**")
            ws = parse_world_state(edited_text)
            st.caption(f"角色：{len(ws['characters'])} 人 | "
                       f"未回收伏笔：{len(ws['unresolved_foreshadowing'])} | "
                       f"已回收伏笔：{len(ws['resolved_foreshadowing'])}")
            for char in ws["characters"]:
                mood_tag = f" [{char['mood']}]" if char.get("mood") else ""
                st.caption(f"- {char['name']}{mood_tag}")
            if st.button("保存到文件", use_container_width=True, type="primary"):
                with open(WORLD_STATE_FILE, "w", encoding="utf-8") as f:
                    f.write(edited_text)
                st.session_state["world_state_text"] = edited_text
                try:
                    st.session_state["world_state_mtime"] = os.path.getmtime(
                        WORLD_STATE_FILE
                    )
                except OSError:
                    pass
                st.success("已保存")
                st.rerun()

    # 用户指令输入
    st.markdown("### 用户指令")
    default_instruction = "写第4章，让陌生少女醒来，但她似乎对铁牛有很深的敌意。"
    user_input = st.text_area(
        "请输入创作指令：",
        value=default_instruction,
        height=80,
        placeholder="输入你的创作指令……",
    )

    # 执行按钮
    col1, col2, col3 = st.columns([1, 1, 4])
    with col1:
        execute_clicked = st.button("执行", type="primary", use_container_width=True)
    with col2:
        clear_clicked = st.button("清空结果", use_container_width=True)

    if clear_clicked:
        st.session_state.pop("pipeline_results", None)

    if execute_clicked:
        world_state = get_world_state_text()
        try:
            results = run_pipeline(user_input, world_state)
        except RuntimeError as e:
            results = {"_pipeline_error": str(e)}
        st.session_state["pipeline_results"] = results

    # 展示结果
    if "pipeline_results" in st.session_state:
        st.divider()
        render_results(st.session_state["pipeline_results"])


if __name__ == "__main__":
    main()
