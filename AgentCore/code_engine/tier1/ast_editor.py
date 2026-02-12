"""
AST Editor for Tier-1.
Performs safe code transformations.
Prefers libcst if available; falls back to AST-guided string insertion to preserve comments/formatting.
"""
import ast
import os
from typing import Dict, Any, List, Optional, Tuple

class ASTEditor:
    def __init__(self):
        self.use_libcst = False
        try:
            import libcst
            self.use_libcst = True
        except ImportError:
            pass
            
    def apply_edit(self, file_path: str, edit_spec: Dict[str, Any], dry_run: bool = False) -> Dict[str, Any]:
        """Apply an edit to a file."""
        if not os.path.exists(file_path):
            return {"success": False, "error": f"File {file_path} not found"}
            
        with open(file_path, 'r', encoding='utf-8') as f:
            source_code = f.read()
            
        new_code = None
        action = edit_spec.get('type')
        
        try:
            if action == 'add_import':
                new_code = self._add_import(source_code, edit_spec)
            elif action == 'add_function':
                new_code = self._add_function(source_code, edit_spec)
            elif action == 'replace_function':
                new_code = self._replace_function(source_code, edit_spec)
            else:
                return {"success": False, "error": f"Unknown edit type: {action}"}
                
            if dry_run:
                # Generate diff
                import difflib
                diff = difflib.unified_diff(
                    source_code.splitlines(keepends=True),
                    new_code.splitlines(keepends=True),
                    fromfile=file_path,
                    tofile=file_path
                )
                return {
                    "success": True,
                    "diff": "".join(diff),
                    "dry_run": True
                }
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_code)
                
            return {"success": True, "dry_run": False}
            
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _add_import(self, source: str, spec: Dict[str, Any]) -> str:
        """Add an import statement."""
        import_line = spec['line']
        lines = source.splitlines(keepends=True)
        
        # Simple prepend for now if no sophisticated logic
        # Ideally find last import using AST
        tree = ast.parse(source)
        last_import_line = 0
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                last_import_line = max(last_import_line, node.end_lineno)
        
        insert_idx = last_import_line
        lines.insert(insert_idx, import_line + '\n')
        return "".join(lines)

    def _add_function(self, source: str, spec: Dict[str, Any]) -> str:
        """Add a function to a class or module."""
        target_class = spec.get('target_class') # None for module level
        function_code = spec['code']
        
        lines = source.splitlines(keepends=True)
        tree = ast.parse(source)
        
        insert_line = len(lines) # Default to end
        indent = ""
        
        if target_class:
            found = False
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef) and node.name == target_class:
                    insert_line = node.end_lineno
                    # Infer indentation from last method or pass
                    if node.body:
                        last_node = node.body[-1]
                        # This is tricky without libcst/tokenize to get exact indent
                        # We'll assume standard 4 spaces for now or look at line
                        indent = "    " # default
                        found = True
            if not found:
                raise ValueError(f"Class {target_class} not found")
        else:
            # Module level -> end of file
            pass

        # Prepare code
        indented_code = ""
        for line in function_code.splitlines():
            indented_code += indent + line + "\n"
            
        lines.insert(insert_line, "\n" + indented_code)
        return "".join(lines)

    def _replace_function(self, source: str, spec: Dict[str, Any]) -> str:
        """Replace a function body."""
        target_name = spec['name']
        new_code = spec['code']
        target_class = spec.get('target_class')
        
        lines = source.splitlines(keepends=True)
        tree = ast.parse(source)
        
        target_node = None
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == target_name:
                # check parent class if needed (simplified check here)
                target_node = node
                break
                
        if not target_node:
            raise ValueError(f"Function {target_name} not found")
            
        start = target_node.lineno - 1
        end = target_node.end_lineno
        
        # Preserve indentation of definition
        # But replacing entire body or entire function?
        # Let's replace entire function for simplicity
        
        lines[start:end] = [new_code + "\n"]
        return "".join(lines)
