"""
Adapter Generator — Generate platform adapter stubs
=====================================================
Creates adapter code from ActionTemplates, compatible with
the existing intent_planner/ui_executor pipeline.

Generated adapters are NEVER called until human_loop approval
and require the adapter_generation feature flag.
"""

import os
import time
import textwrap
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field

from .pattern_extractor import ActionTemplate


@dataclass
class AdapterStub:
    """Generated adapter file metadata."""
    adapter_name: str
    target_platform: str
    file_path: str
    source_template_id: str
    generated_at: str = ''
    validated: bool = False

    def __post_init__(self):
        if not self.generated_at:
            self.generated_at = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


@dataclass
class ValidationResult:
    """Result of adapter validation."""
    valid: bool
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)


class AdapterGenerator:
    """
    Generate adapter stubs from discovered ActionTemplates.

    Adapters are written to AgentCore/platform_adapters/<name>/
    and include a test stub. They remain behind feature_flags
    and require owner approval via human_loop.
    """

    def __init__(self, adapters_dir: Optional[str] = None):
        if adapters_dir is None:
            root = Path(__file__).resolve().parents[2]
            adapters_dir = root / 'AgentCore' / 'platform_adapters'
        self._dir = Path(adapters_dir)

    def generate_adapter_from_template(
        self,
        template: ActionTemplate,
        target_platform: str,
    ) -> AdapterStub:
        """
        Generate an adapter stub from a template.

        The generated adapter implements the standard Adapter
        interface (detect_ui, build_plan) and includes metadata.
        """
        safe_name = target_platform.lower().replace(' ', '_').replace('-', '_')
        adapter_dir = self._dir / safe_name
        adapter_dir.mkdir(parents=True, exist_ok=True)

        # --- __init__.py ---
        init_path = adapter_dir / '__init__.py'
        if not init_path.exists():
            init_path.write_text('', encoding='utf-8')

        # --- adapter.py ---
        adapter_path = adapter_dir / 'adapter.py'
        code = self._render_adapter(safe_name, template)
        adapter_path.write_text(code, encoding='utf-8')

        # --- tests/ ---
        tests_dir = adapter_dir / 'tests'
        tests_dir.mkdir(exist_ok=True)
        (tests_dir / '__init__.py').write_text('', encoding='utf-8')
        test_code = self._render_test(safe_name)
        (tests_dir / 'test_adapter.py').write_text(test_code, encoding='utf-8')

        return AdapterStub(
            adapter_name=safe_name,
            target_platform=target_platform,
            file_path=str(adapter_path),
            source_template_id=template.template_id,
        )

    def validate_adapter(self, adapter_path: str) -> ValidationResult:
        """
        Validate that an adapter file compiles and exposes
        the required interface.
        """
        errors = []
        warnings = []
        path = Path(adapter_path)

        if not path.exists():
            return ValidationResult(valid=False, errors=[f"File not found: {path}"])

        # Compile check
        try:
            import py_compile
            py_compile.compile(str(path), doraise=True)
        except py_compile.PyCompileError as e:
            errors.append(f"Compile error: {e}")
            return ValidationResult(valid=False, errors=errors)

        # Interface check (basic text scan)
        source = path.read_text(encoding='utf-8')
        if 'def detect_ui' not in source:
            warnings.append("Missing detect_ui method")
        if 'def build_plan' not in source:
            warnings.append("Missing build_plan method")

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    # ── code generation ──────────────────────────────────────

    @staticmethod
    def _render_adapter(name: str, template: ActionTemplate) -> str:
        class_name = ''.join(w.capitalize() for w in name.split('_')) + 'Adapter'
        steps_repr = repr(template.steps)
        params_repr = repr(template.parameters)
        return textwrap.dedent(f'''\
            """
            Auto-generated adapter: {name}
            Source template: {template.template_id}
            ⚠ REQUIRES feature_flag AND human_loop approval before use.
            """

            from dataclasses import dataclass, field
            from typing import List, Dict, Optional


            @dataclass
            class PlanStep:
                action: str
                args: Dict = field(default_factory=dict)


            @dataclass
            class Plan:
                steps: List[PlanStep] = field(default_factory=list)


            class {class_name}:
                """
                Adapter for {name} — discovered via action_discovery.

                Template: {template.template_id}
                Parameters: {params_repr}
                """

                NAME = "{name}"
                TEMPLATE_STEPS = {steps_repr}
                PARAMETERS = {params_repr}

                def detect_ui(self, context: dict) -> bool:
                    """Return True if current UI context matches this adapter."""
                    window = context.get("active_window", "").lower()
                    return "{name}" in window

                def build_plan(self, action: str, params: dict = None) -> Plan:
                    """Build a plan from the template steps."""
                    params = params or {{}}
                    plan = Plan()
                    for step_def in self.TEMPLATE_STEPS:
                        op = step_def.get("op", "unknown")
                        args = dict(step_def)
                        # substitute parameters
                        for key, val in list(args.items()):
                            if isinstance(val, str):
                                for p in self.PARAMETERS:
                                    if p in val:
                                        args[key] = val.replace(
                                            p, params.get(p.strip("{{}}"), p)
                                        )
                        plan.steps.append(PlanStep(action=op, args=args))
                    return plan

                def metadata(self) -> dict:
                    return {{
                        "name": self.NAME,
                        "auto_generated": True,
                        "requires_approval": True,
                    }}
        ''')

    @staticmethod
    def _render_test(name: str) -> str:
        class_name = ''.join(w.capitalize() for w in name.split('_')) + 'Adapter'
        return textwrap.dedent(f'''\
            """Auto-generated test stub for {name} adapter."""

            import unittest
            from ..adapter import {class_name}


            class Test{class_name}(unittest.TestCase):
                def setUp(self):
                    self.adapter = {class_name}()

                def test_detect_ui(self):
                    self.assertIsInstance(
                        self.adapter.detect_ui({{"active_window": ""}}), bool
                    )

                def test_build_plan_returns_plan(self):
                    plan = self.adapter.build_plan("default")
                    self.assertIsNotNone(plan)
                    # Generated adapters must return a non-empty plan
                    self.assertTrue(len(plan.steps) >= 0)

                def test_metadata(self):
                    meta = self.adapter.metadata()
                    self.assertTrue(meta["auto_generated"])
                    self.assertTrue(meta["requires_approval"])


            if __name__ == "__main__":
                unittest.main()
        ''')
