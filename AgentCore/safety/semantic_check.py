"""
Semantic Safety Check.
Calculates semantic retention ratio to detect truncation or unauthorized deletion.
"""
import ast

def get_ast_size(tree: ast.AST) -> int:
    """Count number of nodes in AST."""
    return sum(1 for _ in ast.walk(tree))

def semantic_retention_ratio(original_code: str, modified_code: str) -> float:
    """
    Calculate ratio of preserved semantic complexity.
    Ratio = Size(Modified) / Size(Original)
    
    This is a heuristic. A robust implementation would map nodes.
    For stress hardening, ensuring we don't drop 90% of the code is a good start.
    """
    if not original_code.strip():
        return 1.0 if not modified_code.strip() else 1.0
        
    try:
        orig_tree = ast.parse(original_code)
        mod_tree = ast.parse(modified_code)
        
        orig_size = get_ast_size(orig_tree)
        mod_size = get_ast_size(mod_tree)
        
        if orig_size == 0:
            return 1.0
            
        return mod_size / orig_size
    except SyntaxError:
        # If modification is invalid syntax, it fails retention check technically (unsafe)
        return 0.0

def validate_retention(original_code: str, modified_code: str, threshold: float = 0.30) -> bool:
    ratio = semantic_retention_ratio(original_code, modified_code)
    return ratio >= threshold
