import json
import time
import os
import traceback
import streamlit as st
from core.llm import call_llm, parse_json_response

EDITOR_SYSTEM_PROMPT = """你是一位资深网文主编剧。请根据用户指令和当前世界状态，生成下一章的剧本。
你必须严格按照以下JSON格式返回，字段不得缺少或多余：

{"chapter_number": int, "scene": str, "conflict": str, "emotion_level": "高/中/低", "key_events": [str, ...], "foreshadowing_to_plant": str, "characters_involved": [str, ...], "status_changes": {角色: 状态描述, ...}}

注意：
1. emotion_level只能是"高"、"中"、"低"三个值之一。
2. key_events至少包含3个事件节点。
3. status_changes要明确标注本章结束后各角色的状态变化。
4. 必须紧密结合世界状态中已记录的角色、伏笔和情节进度，不得凭空编造冲突信息。
5. 你只能返回 JSON，不要附带任何解释、Markdown 代码块标记或其他文字。"""


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
