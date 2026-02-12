"""
Validators for Tier-1.
Performs static analysischecks on code.
"""
import ast
import os
from typing import Dict, Any, List

class Validator:
    def check_syntax(self, code: str) -> Dict[str, Any]:
        """Check for syntax errors."""
        try:
            ast.parse(code)
            return {"valid": True}
        except SyntaxError as e:
            return {
                "valid": False,
                "error": str(e),
                "line": e.lineno
            }

    def check_file(self, file_path: str) -> Dict[str, Any]:
        """Check a file for syntax and forbidden patterns."""
        if not os.path.exists(file_path):
            return {"valid": False, "error": "File not found"}
            
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            syntax_result = self.check_syntax(content)
            if not syntax_result['valid']:
                return syntax_result
            
            # Additional static checks (e.g. no hardcoded secrets, dangerous imports)
            # Simple heuristic check
            dangerous_imports = ["subprocess", "os.system", "shutil.rmtree"]
            found_dangers = []
            
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name in dangerous_imports:
                            found_dangers.append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module in dangerous_imports:
                         found_dangers.append(node.module)
            
            if found_dangers:
                return {
                    "valid": True, # Syntactically valid, but warned
                    "warnings": f"Dangerous imports found: {found_dangers}"
                }
                
            return {"valid": True}
            
        except Exception as e:
            return {"valid": False, "error": str(e)}
