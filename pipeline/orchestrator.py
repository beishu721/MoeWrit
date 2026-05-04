import streamlit as st
from agents.editor import generate_script
from agents.crew import generate_draft, generate_draft_stream
from agents.quality_checker import quality_check
from agents.reviser import revise_draft, revise_draft_stream
from agents.state_updater import update_world_state


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


def run_pipeline_stream(user_input, world_state, placeholder_draft, placeholder_final):
    """执行流式创作流水线。初稿和修正稿通过 streamlit 容器流式输出。"""
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

        # 步骤 2：流式生成初稿
        status.update(label="步骤 2/5：创作班组正在撰写初稿……")
        draft_text = ""
        for chunk in generate_draft_stream(results["script"], world_state):
            draft_text += chunk
            placeholder_draft.markdown(draft_text)
        results["draft"] = draft_text.strip()
        status.update(label="步骤 2/5：初稿撰写完成 ✓")

        # 步骤 3：质检
        status.update(label="步骤 3/5：质检员正在审查初稿……")
        results["quality_report"] = quality_check(
            results["script"], results["draft"], world_state
        )
        status.update(label="步骤 3/5：质检报告生成完成 ✓")

        # 步骤 4：流式修正
        status.update(label="步骤 4/5：正在根据质检意见修正初稿……")
        final_text = ""
        for chunk in revise_draft_stream(
            results["draft"], results["quality_report"], results["script"]
        ):
            final_text += chunk
            placeholder_final.markdown(final_text)
        results["final_draft"] = final_text.strip()
        status.update(label="步骤 4/5：修正终稿完成 ✓")

        # 步骤 5：更新世界状态
        status.update(label="步骤 5/5：世界知识库正在更新世界状态……")
        results["state_update"] = update_world_state(
            results["final_draft"], results["script"], world_state
        )
        status.update(label="步骤 5/5：世界状态更新完成 ✓", state="complete")

    return results


class PipelineEditor:
    """交互式流水线编辑器：每步完成后允许用户编辑中间产物。"""

    def __init__(self, user_input, world_state):
        self.user_input = user_input
        self.world_state = world_state
        self.results = {}

    def run_step(self, step_key):
        """根据 step_key 执行对应的流水线步骤。返回 True 表示成功。"""
        if step_key == "script":
            if "_pipeline_error" in self.results:
                return False
            try:
                self.results["script"] = generate_script(
                    self.user_input, self.world_state
                )
            except RuntimeError as e:
                self.results["_pipeline_error"] = str(e)
                return False
            if (
                isinstance(self.results["script"], dict)
                and self.results["script"].get("_error")
            ):
                self.results["_pipeline_error"] = self.results["script"]["message"]
                return False
            return True

        elif step_key == "draft":
            draft_text = ""
            for chunk in generate_draft_stream(
                self.results["script"], self.world_state
            ):
                draft_text += chunk
                yield chunk
            self.results["draft"] = draft_text.strip()
            yield None  # signal completion

        elif step_key == "quality_report":
            self.results["quality_report"] = quality_check(
                self.results["script"],
                self.results["draft"],
                self.world_state,
            )
            return True

        elif step_key == "final_draft":
            final_text = ""
            for chunk in revise_draft_stream(
                self.results["draft"],
                self.results["quality_report"],
                self.results["script"],
            ):
                final_text += chunk
                yield chunk
            self.results["final_draft"] = final_text.strip()
            yield None

        elif step_key == "state_update":
            self.results["state_update"] = update_world_state(
                self.results["final_draft"],
                self.results["script"],
                self.world_state,
            )
            return True

        return True
