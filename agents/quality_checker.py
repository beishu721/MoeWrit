import json
import time
import streamlit as st
from core.llm import call_llm, parse_json_response

QUALITY_CHECKER_SYSTEM_PROMPT = """你是一位严格的小说逻辑审查员。你需要对比三份材料：世界状态、本章剧本、正文初稿。

请找出正文初稿中至少1个逻辑或事实矛盾，并提供具体的修改建议。同时，找出世界状态里一个可用的未回收伏笔，建议如何在当前情节中使用它。

你必须严格按照以下JSON格式返回，字段不得缺少或多余：

{"logic_conflicts": [{"type": "事实矛盾/性格不一致/时间线错误/设定冲突", "description": "具体描述矛盾所在", "suggestion": "具体的修改建议"}], "foreshadowing_suggestion": {"available_foreshadowing": "伏笔ID和内容", "usage_tip": "在当前场景中的具体使用方式"}}

注意：
1. 如果你没有发现任何逻辑矛盾，logic_conflicts 返回空列表 []。
2. foreshadowing_suggestion 必须始终提供一个建议，即使没有明显的未回收伏笔也要尽力挖掘。
3. description 和 suggestion 必须具体、可操作，不能泛泛而谈。
4. 你只能返回 JSON，不要附带任何解释、Markdown 代码块标记或其他文字。"""


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
