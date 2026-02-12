"""
Template Manager for Tier-1.
Handles creation of files from Jinja2 templates.
"""
import os
from typing import Dict, Any, Optional
import jinja2

class TemplateManager:
    def __init__(self, template_dir: str = None):
        if template_dir is None:
            # Default to AgentCore/code_engine/templates
            base_path = os.path.dirname(os.path.dirname(__file__))
            template_dir = os.path.join(base_path, "templates")
        
        self.template_dir = template_dir
        if not os.path.exists(self.template_dir):
            os.makedirs(self.template_dir, exist_ok=True)
            
        self.env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(self.template_dir),
            autoescape=jinja2.select_autoescape(['html', 'xml', 'py'])
        )

    def render(self, template_name: str, context: Dict[str, Any]) -> str:
        """Render a template with the given context."""
        try:
            template = self.env.get_template(template_name)
            return template.render(**context)
        except jinja2.TemplateNotFound:
            raise FileNotFoundError(f"Template '{template_name}' not found in {self.template_dir}")
        except Exception as e:
            raise RuntimeError(f"Failed to render template '{template_name}': {e}")

    def create_file(self, target_path: str, template_name: str, context: Dict[str, Any], dry_run: bool = False) -> Dict[str, Any]:
        """Create a file from a template."""
        content = self.render(template_name, context)
        
        if dry_run:
            return {
                "action": "create_file",
                "path": target_path,
                "content_preview": content[:200],
                "dry_run": True
            }
            
        # Ensure directory exists
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        
        with open(target_path, 'w', encoding='utf-8') as f:
            f.write(content)
            
        return {
            "action": "create_file",
            "path": target_path,
            "success": True
        }

    def list_templates(self):
        return self.env.list_templates()
