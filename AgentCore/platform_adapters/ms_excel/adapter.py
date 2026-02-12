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


class MsExcelAdapter(BaseAdapter):
    """Adapter for Microsoft Excel (local desktop application)."""

    EXE_HINT = "EXCEL.EXE"

    @property
    def platform_name(self) -> str:
        return "Microsoft Excel"

    @property
    def supported_actions(self) -> List[str]:
        return ["blank_workbook_created", "workbook_from_template_created", "workbook_saved", "workbook_saved_as", "workbook_saved_as_pdf", "workbook_closed", "cell_value_entered", "cell_formula_entered", "cell_format_changed", "row_inserted", "row_deleted", "column_inserted", "column_deleted", "sheet_added", "sheet_renamed", "sheet_deleted", "sheet_moved", "range_selected", "range_copied", "range_pasted", "range_cut", "auto_fill_applied", "flash_fill_used", "sort_applied", "filter_applied", "advanced_filter_applied", "pivot_table_created", "pivot_chart_created", "chart_created", "chart_type_changed", "chart_data_range_modified", "conditional_formatting_applied", "data_validation_applied", "vlookup_formula_used", "index_match_formula_used", "sumif_formula_used", "macro_recorded", "macro_run", "vba_editor_opened", "freeze_panes_applied", "split_window_applied", "name_manager_opened", "named_range_created", "data_connection_created", "power_query_opened", "protect_sheet_applied", "protect_workbook_applied"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "msexcel" in title or "microsoftexcel" in title or "excel" in title

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
        return "excel" in title
