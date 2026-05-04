import json
import time
import streamlit as st
from core.llm import call_llm, call_llm_stream

REVISER_SYSTEM_PROMPT = """你是一位精益求精的网文修改专家。你会收到原始正文初稿、质检报告（指出了逻辑矛盾）和原始剧本。

请根据质检报告中的每一条问题和建议，对正文进行修正和重写，输出修正后的完整小说正文。

修改要求：
1. 必须逐一处理质检报告中指出的每一条逻辑矛盾，不可遗漏。
2. 如果质检报告提供了伏笔利用建议，请自然地融入修正后的正文中。
3. 修正时应尽量保留原文的优点和流畅的段落，只对有问题的地方进行精准修改或补充。
4. 修正后的正文应保持800-1500字的篇幅。
5. 你只能返回修正后的小说正文，不要附带任何解释、修改说明或 Markdown 标记。"""


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


def revise_draft_stream(draft, quality_report, script):
    """修正重生成：流式生成修正稿。"""
    report_json = json.dumps(quality_report, ensure_ascii=False, indent=2)
    script_json = json.dumps(script, ensure_ascii=False, indent=2)
    user_prompt = (
        f"以下正文存在逻辑问题，需要修正：\n\n"
        f"原始剧本：\n{script_json}\n\n"
        f"原始正文：\n{draft}\n\n"
        f"质检报告：\n{report_json}\n\n"
        f"请修正上述问题，重写正文。"
    )
    return call_llm_stream(REVISER_SYSTEM_PROMPT, user_prompt, temperature=0.7)
