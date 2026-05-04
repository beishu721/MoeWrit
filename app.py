import json
import os
import streamlit as st
from core.world_state import get_world_state_text, parse_world_state, WORLD_STATE_FILE
from agents.editor import generate_script
from agents.crew import generate_draft_stream
from agents.quality_checker import quality_check
from agents.reviser import revise_draft_stream
from agents.state_updater import update_world_state
from ui.sidebar import render_sidebar
from ui.results import render_results

PIPELINE_STEPS = [
    "script",
    "draft",
    "quality_report",
    "final_draft",
    "state_update",
]

STEP_LABELS = {
    "script": "生成剧本",
    "draft": "撰写初稿",
    "quality_report": "质检审查",
    "final_draft": "修正终稿",
    "state_update": "更新世界状态",
}


def init_session():
    """初始化 session state。"""
    defaults = {
        "pipeline_step": 0,
        "pipeline_results": {},
        "pipeline_error": None,
        "edit_script": "",
        "edit_draft": "",
        "edit_quality_notes": "",
        "edit_final_draft": "",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def render_world_state_editor():
    """世界状态管理面板。"""
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
            st.caption(
                f"角色：{len(ws['characters'])} 人 | "
                f"未回收伏笔：{len(ws['unresolved_foreshadowing'])} | "
                f"已回收伏笔：{len(ws['resolved_foreshadowing'])}"
            )
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


def execute_step_script(user_input, world_state):
    """执行步骤1：生成剧本。"""
    with st.status("步骤 1/5：主编剧正在生成剧本……", expanded=True) as status:
        try:
            result = generate_script(user_input, world_state)
        except RuntimeError as e:
            status.update(label="步骤 1/5：主编剧剧本生成失败 ✗", state="error")
            st.session_state["pipeline_error"] = str(e)
            return None
        if isinstance(result, dict) and result.get("_error"):
            status.update(label="步骤 1/5：主编剧剧本生成失败 ✗", state="error")
            st.session_state["pipeline_error"] = result["message"]
            st.session_state["pipeline_results"]["script"] = result
            return None
        status.update(label="步骤 1/5：主编剧剧本生成完成 ✓", state="complete")
        st.session_state["pipeline_results"]["script"] = result
        return result


def execute_step_draft(world_state):
    """执行步骤2：流式生成初稿。"""
    script = st.session_state["pipeline_results"]["script"]
    with st.status("步骤 2/5：创作班组正在撰写初稿……", expanded=True) as status:
        placeholder = st.empty()
        draft_text = ""
        try:
            for chunk in generate_draft_stream(script, world_state):
                draft_text += chunk
                placeholder.markdown(draft_text)
        except Exception as e:
            status.update(label="步骤 2/5：初稿生成失败 ✗", state="error")
            draft_text = f"[初稿生成失败] {e}"
        status.update(label="步骤 2/5：初稿撰写完成 ✓", state="complete")
    st.session_state["pipeline_results"]["draft"] = draft_text.strip()


def execute_step_quality(world_state):
    """执行步骤3：质检审查。"""
    script = st.session_state["pipeline_results"]["script"]
    draft = st.session_state["pipeline_results"]["draft"]
    with st.status("步骤 3/5：质检员正在审查初稿……", expanded=True) as status:
        result = quality_check(script, draft, world_state)
        status.update(label="步骤 3/5：质检报告生成完成 ✓", state="complete")
    st.session_state["pipeline_results"]["quality_report"] = result


def execute_step_revision():
    """执行步骤4：流式修正终稿。"""
    script = st.session_state["pipeline_results"]["script"]
    draft = st.session_state["pipeline_results"]["draft"]
    quality_report = st.session_state["pipeline_results"]["quality_report"]

    # 允许用户在质检阶段追加修改意见
    extra_notes = st.session_state.get("edit_quality_notes", "").strip()
    if extra_notes:
        quality_report = dict(quality_report)
        quality_report["_user_notes"] = extra_notes

    with st.status("步骤 4/5：正在根据质检意见修正初稿……", expanded=True) as status:
        placeholder = st.empty()
        final_text = ""
        try:
            for chunk in revise_draft_stream(draft, quality_report, script):
                final_text += chunk
                placeholder.markdown(final_text)
        except Exception as e:
            status.update(label="步骤 4/5：修正失败 ✗", state="error")
            final_text = f"[修正重生成失败] {e}\n\n保留原稿：\n\n{draft}"
        status.update(label="步骤 4/5：修正终稿完成 ✓", state="complete")
    st.session_state["pipeline_results"]["final_draft"] = final_text.strip()


def execute_step_state_update(world_state):
    """执行步骤5：更新世界状态。"""
    script = st.session_state["pipeline_results"]["script"]
    final_draft = st.session_state["pipeline_results"]["final_draft"]
    with st.status("步骤 5/5：世界知识库正在更新世界状态……", expanded=True) as status:
        result = update_world_state(final_draft, script, world_state)
        status.update(label="步骤 5/5：世界状态更新完成 ✓", state="complete")
    st.session_state["pipeline_results"]["state_update"] = result


def render_step_editor(step_key):
    """展示当前步骤的编辑界面。"""
    results = st.session_state["pipeline_results"]

    if step_key == "script":
        script = results.get("script", {})
        if isinstance(script, dict) and not script.get("_error"):
            with st.expander("主编剧剧本 (JSON)", expanded=True):
                script_str = st.text_area(
                    "可编辑剧本 JSON：",
                    value=st.session_state.get(
                        "edit_script",
                        json.dumps(script, ensure_ascii=False, indent=2),
                    ),
                    height=300,
                    key="edit_script_input",
                )
                st.session_state["edit_script"] = script_str
            if st.button("确认并继续 → 撰写初稿", type="primary", use_container_width=True):
                try:
                    edited = json.loads(
                        st.session_state["edit_script"].strip()
                    )
                    st.session_state["pipeline_results"]["script"] = edited
                except Exception:
                    pass  # 保留原始 script
                st.session_state["pipeline_step"] = 2
                st.rerun()

    elif step_key == "draft":
        draft = results.get("draft", "")
        if draft:
            st.markdown("### 初稿正文")
            edited = st.text_area(
                "可编辑初稿正文：",
                value=st.session_state.get("edit_draft", draft),
                height=350,
                key="edit_draft_input",
            )
            st.session_state["edit_draft"] = edited
            if st.button("确认并继续 → 质检审查", type="primary", use_container_width=True):
                st.session_state["pipeline_results"]["draft"] = (
                    st.session_state["edit_draft"]
                )
                st.session_state["pipeline_step"] = 3
                st.rerun()

    elif step_key == "quality_report":
        quality_report = results.get("quality_report", {})
        if quality_report:
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

            extra_notes = st.text_area(
                "追加修改意见（可选，将传递给修正 Agent）：",
                value=st.session_state.get("edit_quality_notes", ""),
                height=120,
                key="edit_quality_notes_input",
                placeholder="输入你想要额外修改的方向……",
            )
            st.session_state["edit_quality_notes"] = extra_notes

            if st.button("确认并继续 → 修正终稿", type="primary", use_container_width=True):
                st.session_state["pipeline_step"] = 4
                st.rerun()

    elif step_key == "final_draft":
        final_draft = results.get("final_draft", "")
        if final_draft:
            st.markdown("### 修正终稿")
            edited = st.text_area(
                "可编辑修正终稿：",
                value=st.session_state.get("edit_final_draft", final_draft),
                height=350,
                key="edit_final_draft_input",
            )
            st.session_state["edit_final_draft"] = edited
            if st.button("确认并继续 → 更新世界状态", type="primary", use_container_width=True):
                st.session_state["pipeline_results"]["final_draft"] = (
                    st.session_state["edit_final_draft"]
                )
                st.session_state["pipeline_step"] = 5
                st.rerun()


def render_final_results():
    """展示全部完成后的最终结果。"""
    results = st.session_state["pipeline_results"]
    st.success("流水线执行完毕！")
    st.divider()
    render_results(results)
    if st.button("开始新章节", use_container_width=True):
        st.session_state["pipeline_step"] = 0
        st.session_state["pipeline_results"] = {}
        st.session_state["pipeline_error"] = None
        st.session_state["edit_script"] = ""
        st.session_state["edit_draft"] = ""
        st.session_state["edit_quality_notes"] = ""
        st.session_state["edit_final_draft"] = ""
        st.rerun()


def main():
    st.set_page_config(
        page_title="墨灵 · Demo控制台",
        page_icon="",
        layout="wide",
    )

    st.title("墨灵 · Demo控制台")
    st.caption("多Agent协同网文创作系统 — 概念验证Demo")

    init_session()
    render_sidebar()
    render_world_state_editor()

    step = st.session_state["pipeline_step"]
    world_state = get_world_state_text()

    # ── 阶段 0：输入指令 ──
    if step == 0:
        st.markdown("### 用户指令")
        user_input = st.text_area(
            "请输入创作指令：",
            value="写第4章，让陌生少女醒来，但她似乎对铁牛有很深的敌意。",
            height=80,
            placeholder="输入你的创作指令……",
            key="user_input",
        )

        col1, col2, _ = st.columns([1, 1, 4])
        with col1:
            execute_clicked = st.button(
                "执行", type="primary", use_container_width=True
            )
        with col2:
            clear_clicked = st.button("清空结果", use_container_width=True)

        if clear_clicked:
            st.session_state["pipeline_results"] = {}
            st.session_state["pipeline_error"] = None
            st.rerun()

        if execute_clicked and user_input.strip():
            st.session_state["pipeline_step"] = 1
            st.session_state["_user_input"] = user_input.strip()
            st.rerun()

    # ── 阶段 1：生成剧本 ──
    elif step == 1:
        user_input = st.session_state.get("_user_input", "")
        if "script" not in st.session_state["pipeline_results"]:
            execute_step_script(user_input, world_state)

        if st.session_state.get("pipeline_error"):
            st.error(f"流水线执行中断：{st.session_state['pipeline_error']}")
            if st.button("重新开始"):
                st.session_state["pipeline_step"] = 0
                st.session_state["pipeline_error"] = None
                st.rerun()
        else:
            render_step_editor("script")

    # ── 阶段 2：撰写初稿（流式） ──
    elif step == 2:
        if "draft" not in st.session_state["pipeline_results"]:
            execute_step_draft(world_state)
        render_step_editor("draft")

    # ── 阶段 3：质检审查 ──
    elif step == 3:
        if "quality_report" not in st.session_state["pipeline_results"]:
            execute_step_quality(world_state)
        render_step_editor("quality_report")

    # ── 阶段 4：修正终稿（流式） ──
    elif step == 4:
        if "final_draft" not in st.session_state["pipeline_results"]:
            execute_step_revision()
        render_step_editor("final_draft")

    # ── 阶段 5：更新世界状态 ──
    elif step == 5:
        if "state_update" not in st.session_state["pipeline_results"]:
            execute_step_state_update(world_state)
        render_final_results()

    # 展示历史结果（如果在 idle 且有缓存）
    if step == 0 and st.session_state["pipeline_results"]:
        st.divider()
        render_results(st.session_state["pipeline_results"])


if __name__ == "__main__":
    main()
