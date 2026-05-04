import json
import time
import streamlit as st
from core.llm import call_llm, call_llm_stream

CREW_SYSTEM_PROMPT = """你是一位经验丰富的网文写手。你将收到一份结构化的章节剧本（JSON格式）和当前的世界状态。
请根据剧本指令，写出一段小说正文（800-1500字）。

写作要求：
1. 注意描写细节，包括环境、动作、对话和内心感受。
2. 根据剧本中的 emotion_level 调整行文节奏——"高"则加强紧张感和冲突渲染，"低"则侧重内心独白和环境氛围。
3. 必须紧密结合世界状态中记录的角色特征和状态（如伤势、情绪、伏笔等），在描写中自然体现，不得凭空编造。
4. 严格按照剧本中的 key_events 顺序推进情节，每个事件节点都要有对应的段落。
5. 对话要符合角色性格，动作描写要体现角色的身体状态。
6. 你只能返回小说正文，不要附带任何解释、评价或 Markdown 标记。"""


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


def generate_draft_stream(script, world_state):
    """创作班组 Agent：流式生成小说正文。"""
    script_json = json.dumps(script, ensure_ascii=False, indent=2)
    user_prompt = (
        f"世界状态：\n{world_state}\n\n"
        f"本章剧本：\n{script_json}\n\n"
        f"请根据剧本写出小说正文。"
    )
    return call_llm_stream(CREW_SYSTEM_PROMPT, user_prompt, temperature=0.8)
