from typing import Dict, Any, Optional

import libcst as cst


class _ReplaceOrAppendFunction(cst.CSTTransformer):
    """Replaces the first FunctionDef matching `name` in place; leaves a
    marker (found=False) if no match was seen, so the caller can append
    the new function as a fallback instead of silently dropping it."""

    def __init__(self, name: str, new_function: cst.FunctionDef):
        self.name = name
        self.new_function = new_function
        self.found = False

    def leave_FunctionDef(self, original_node: cst.FunctionDef, updated_node: cst.FunctionDef):
        if original_node.name.value == self.name:
            self.found = True
            return self.new_function
        return updated_node


class ASTFixer:
    def apply_transform(self, file_content: str, spec: Dict[str, Any]) -> str:
        """
        Apply a structural transform to file_content using LibCST --
        parses to a concrete syntax tree, transforms just the targeted
        node, and renders back to source, preserving everything else
        (formatting, comments, unrelated code) exactly. Real
        implementation of what this file's own placeholder comment
        described ("In real implementation: import libcst as cst ->
        parse -> transform -> code").

        Supported spec shapes:
        - {"type": "replace_full", "code": "..."} -- whole-file
          replacement. Kept from the placeholder; still a legitimate,
          simple case, and not really an "AST" operation at all.
        - {"type": "replace_function", "name": "...", "code": "..."} --
          replaces the named function's entire definition with `code`
          (a full "def ..." block) wherever it appears in the file, or
          appends it as a new top-level function if no function with
          that name exists yet.

        On a parse error (malformed file_content or malformed spec
        "code") or an unrecognized transform type, returns file_content
        unchanged -- an honest no-op rather than a guess, matching the
        rest of this codebase's "don't fabricate on failure" convention.
        """
        transform_type = spec.get("type")

        if transform_type == "replace_full":
            return spec.get("code", file_content)

        if transform_type == "replace_function":
            return self._replace_function(file_content, spec)

        return file_content

    def _replace_function(self, file_content: str, spec: Dict[str, Any]) -> str:
        name = spec.get("name")
        code = spec.get("code", "")
        if not name or not code:
            return file_content

        try:
            module = cst.parse_module(file_content)
        except cst.ParserSyntaxError as e:
            print(f"[ASTFixer] Could not parse existing file content, leaving unchanged: {e}")
            return file_content

        new_function = self._extract_function_def(code)
        if new_function is None:
            print("[ASTFixer] spec['code'] for replace_function did not contain a valid function definition")
            return file_content

        transformer = _ReplaceOrAppendFunction(name, new_function)
        new_module = module.visit(transformer)

        if not transformer.found:
            new_module = new_module.with_changes(body=[*new_module.body, new_function])

        return new_module.code

    @staticmethod
    def _extract_function_def(code: str) -> Optional[cst.FunctionDef]:
        try:
            parsed = cst.parse_module(code)
        except cst.ParserSyntaxError as e:
            print(f"[ASTFixer] Could not parse spec['code'] as Python: {e}")
            return None
        for stmt in parsed.body:
            if isinstance(stmt, cst.FunctionDef):
                return stmt
        return None
