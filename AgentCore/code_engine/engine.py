import os
import time
import difflib
import json
import re
from pathlib import Path
from typing import Dict, Any, Optional
from .generator_helper import GeneratorHelper

class CodeEngine:
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        # Read feature flags
        self.base_path = Path(__file__).parent.parent.parent
        self.flag_path = self.base_path / "feature_flags/code_engine.yaml"
        self.config = config or self._read_flag()
        self.generator = GeneratorHelper()

    def _read_flag(self) -> Dict[str, Any]:
        """Read feature flag configuration."""
        if not self.flag_path.exists():
            return {}
        try:
            import yaml
            with open(self.flag_path, 'r') as f:
                return yaml.safe_load(f) or {}
        except ImportError:
            # Fallback for simple yaml parsing if pyyaml missing
            config = {}
            with open(self.flag_path, 'r') as f:
                for line in f:
                    if ':' in line:
                        key, val = line.split(':', 1)
                        key = key.strip()
                        val = val.strip().split('#')[0].strip()
                        if val.lower() == 'true': val = True
                        elif val.lower() == 'false': val = False
                        elif val.startswith('"') and val.endswith('"'): val = val[1:-1]
                        config[key] = val
            return config
        except Exception as e:
            print(f"[CodeEngine] Error reading flags: {e}")
            return {}

    def handle_command(self, text: str, context: Optional[Dict[str, Any]] = None, dry_run: bool = True) -> Dict[str, Any]:
        """
        Handle a coding command.
        
        Args:
            text: The user command (e.g., "write a python script...")
            context: Execution context (user, cwd, etc.)
            dry_run: If True, only simulate changes.
        """
        context = context or {}
        
        # 1. Parse Language Hint
        lang = "python"
        if "python" in text.lower():
            lang = "python"
        elif "java" in text.lower():
            lang = "java"
        elif "javascript" in text.lower() or "js" in text.lower():
            lang = "javascript"
        elif "html" in text.lower():
            lang = "html"
        elif "css" in text.lower():
            lang = "css"
        elif "bash" in text.lower() or "shell" in text.lower():
            lang = "bash"

        # 2. Generate Code
        generated_raw = self.generator.generate_code(text, lang, context)
        
        # 3. Parse Files
        files_to_process = {} # filename -> content
        
        # Regex for "### filename" blocks
        parts = re.split(r'(^|\n)###\s+([^\n]+)\n', generated_raw)
        
        if len(parts) > 1:
            # Multi-file detected
            i = 1
            while i < len(parts) - 1:
                fname = parts[i+1].strip()
                content = parts[i+2] if i+2 < len(parts) else ""
                files_to_process[fname] = content
                i += 3
        else:
            # Single file heuristic
            filename = "script.py"
            if lang == "python": filename = "hello_world.py"
            elif lang == "java": filename = "Main.java"
            elif lang == "javascript": filename = "script.js"
            elif lang == "html": filename = "index.html"
            elif lang == "css": filename = "style.css"
            elif lang == "bash": filename = "script.sh"
            
            # Try to extract filename from text if present
            match = re.search(r'\b([\w-]+\.\w+)\b', text)
            if match:
                filename = match.group(1)
            files_to_process[filename] = generated_raw

        # 4. Create Sandbox Path
        ts = time.strftime("%Y%m%d_%H%M%S")
        sandbox_root_str = self.config.get("sandbox_root", "projects/sandbox")
        if not os.path.isabs(sandbox_root_str):
            sandbox_root = self.base_path / sandbox_root_str
        else:
            sandbox_root = Path(sandbox_root_str)
            
        target_dir = sandbox_root / ts
        
        # 5. Process Each File
        config_auto_write = self.config.get("auto_write", False)
        should_write = (not dry_run) and config_auto_write
        
        results = []
        full_diff = []
        
        for fname, content in files_to_process.items():
            # Sanitize fname to prevent traversal
            # Allow path components but ensure no ..
            clean_fname = fname.replace("..", "__")
            if clean_fname.startswith("/"): clean_fname = clean_fname[1:]
            
            fpath = target_dir / clean_fname
            
            # Diff
            diff = "\n".join(list(difflib.unified_diff(
                [], # New file
                content.splitlines(), 
                fromfile='/dev/null', 
                tofile=str(fpath), 
                lineterm=''
            )))
            full_diff.append(diff)
            
            if should_write:
                try:
                    fpath.parent.mkdir(parents=True, exist_ok=True)
                    with open(fpath, "w", encoding="utf-8") as f:
                        f.write(content)
                    results.append(str(fpath))
                except Exception as e:
                    print(f"Error writing {fname}: {e}")

        # 6. Return Summary
        summary_lines = [f"{'Created' if should_write else 'Would create'} {fname}" for fname in files_to_process.keys()]
        summary = f"Generated {len(files_to_process)} files in {target_dir}:\n" + "\n".join(summary_lines)
        
        return {
            "dry_run": not should_write,
            "patch_summary": summary,
            "patch_diff": "\n".join(full_diff),
            "file_path": str(target_dir),
            "sandbox_path": str(target_dir)
        }
