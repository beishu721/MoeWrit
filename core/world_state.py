import os
import streamlit as st

WORLD_STATE_FILE = "world_state.md"


def read_world_state():
    if not os.path.exists(WORLD_STATE_FILE):
        return "（世界状态文件不存在）"
    with open(WORLD_STATE_FILE, "r", encoding="utf-8") as f:
        return f.read()


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
