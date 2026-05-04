import streamlit as st


def render_results(results):
    """渲染流水线各阶段的输出。"""
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

    script = results.get("script")
    draft = results.get("draft")
    quality_report = results.get("quality_report")
    final_draft = results.get("final_draft")
    state_update = results.get("state_update")

    # ---------- 主编剧剧本 ----------
    st.markdown("### 主编剧剧本")
    with st.expander("点击展开/折叠 JSON 剧本", expanded=False):
        if isinstance(script, dict) and script.get("_error"):
            st.error(script.get("message", "未知错误"))
            if script.get("raw_response"):
                st.caption("LLM 原始返回：")
                st.code(script["raw_response"])
        elif script:
            st.json(script)

    # ---------- 初稿正文 ----------
    if draft:
        st.markdown("### 初稿正文")
        st.markdown(draft)

    # ---------- 质检报告 ----------
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

    # ---------- 修正终稿 ----------
    if final_draft:
        st.markdown("### 修正终稿")
        st.markdown(final_draft)

    # ---------- 世界状态更新日志 ----------
    if state_update:
        st.markdown("### 世界状态更新日志")
        st.info(state_update)
