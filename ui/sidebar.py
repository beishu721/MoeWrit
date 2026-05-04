import streamlit as st
from core.config import load_config
from core.world_state import get_world_state_text, parse_world_state


def render_sidebar():
    """侧边栏：世界状态预览（结构化展示）。"""
    world_state_text = get_world_state_text()
    ws = parse_world_state(world_state_text)

    with st.sidebar:
        st.header("世界状态")

        config = load_config()
        if not config["api_key"] or config["api_key"] == "your-api-key-here":
            st.warning(
                "API Key 未配置。请复制 `.env.example` 为 `.env`，"
                "填入真实的 `OPENAI_API_KEY`。"
            )

        st.subheader("当前进度")
        timeline = ws["current_time"]
        if timeline:
            cols = st.columns(3)
            cols[0].metric("章节", timeline.get("chapter_progress", "-"))
            cols[1].metric("时间", timeline.get("time", "-"))
            cols[2].metric("地点", timeline.get("location", "-"))

        st.divider()

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
