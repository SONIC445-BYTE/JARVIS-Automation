from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan

try:
    from ...intent_planner import ExecutionStep
except ImportError:
    from dataclasses import dataclass
    @dataclass
    class ExecutionStep:
        action: str = ""
        target: str = ""
        parameters: dict = None

import subprocess, os


class MsPowerpointAdapter(BaseAdapter):
    """Adapter for Microsoft PowerPoint (local desktop application)."""

    EXE_HINT = "POWERPNT.EXE"

    @property
    def platform_name(self) -> str:
        return "Microsoft PowerPoint"

    @property
    def supported_actions(self) -> List[str]:
        return ["blank_presentation_created", "presentation_from_template_created", "presentation_saved", "presentation_saved_as", "presentation_saved_as_pdf", "presentation_closed", "slide_added", "slide_deleted", "slide_duplicated", "slide_moved", "slide_layout_changed", "slide_design_applied", "text_typed", "text_formatted", "text_box_inserted", "image_inserted", "shape_inserted", "chart_inserted", "table_inserted", "video_inserted", "audio_inserted", "icon_inserted", "animation_applied", "animation_removed", "animation_reordered", "transition_applied", "transition_timing_set", "slide_show_started", "slide_show_from_beginning", "slide_show_from_current_slide", "presenter_view_used", "notes_added", "comments_added", "comments_resolved", "slide_master_edited", "custom_layout_created", "hyperlink_inserted", "action_button_added", "section_added", "section_renamed", "rehearse_timings_used", "record_slide_show_used", "export_to_video_executed"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "mspowerpoint" in title or "microsoftpowerpoint" in title or "powerpnt" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        if action_name not in self.supported_actions:
            return Plan(steps=[], confidence=0.0)
        # Default: launch the application if not running
        steps.append(ExecutionStep(
            action="launch_app",
            target=self.EXE_HINT,
            parameters={"exe": self.EXE_HINT, "action": action_name, **params}
        ))
        return Plan(steps=steps, confidence=0.80)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        title = ui_snapshot.get("active_window", "").lower()
        return "powerpnt" in title
