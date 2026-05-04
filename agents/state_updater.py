import json
import time
import os
from datetime import datetime
import streamlit as st
from core.llm import call_llm

STATE_UPDATER_SYSTEM_PROMPT = """你是一位严谨的世界状态记录员（史官）。你会收到本章的终稿正文和当前世界状态。

请根据终稿内容，提取本章产生的状态变更，用 Markdown 格式输出需要追加到世界状态文件中的内容。

输出格式要求（严格遵循）：
1. 用 ## 第N章更新 作为标题
2. 包含 ### 新增状态 段落，用 - 列表记录每个角色的状态变化
3. 包含 ### 本章伏笔推进 段落，记录已有伏笔在本章的进展
4. 包含 ### 新埋伏笔 段落，记录本章新埋下的伏笔（用 V00X 编号）
5. 内容要简洁准确，每条不超过一句话
6. 你只能返回需要追加的 Markdown 内容，不要附带任何解释或其他文字。"""

WORLD_STATE_FILE = "world_state.md"


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
