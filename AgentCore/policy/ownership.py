"""
Ownership Policy Manager.
"""
import yaml
import os
from typing import Tuple, Dict, Any, List
from fnmatch import fnmatch

class OwnershipPolicy:
    def __init__(self, registry_path: str = None):
        if registry_path is None:
            base_path = os.path.dirname(__file__)
            registry_path = os.path.join(base_path, "ownership_registry.yaml")
        self.registry_path = registry_path
        self._load_registry()

    def _load_registry(self):
        try:
            with open(self.registry_path, 'r') as f:
                self.config = yaml.safe_load(f) or {}
        except Exception:
            self.config = {"domains": {}}

    def get_domain(self, path: str) -> str:
        domains = self.config.get('domains', {})
        # Normalize path
        path = path.replace("\\", "/")
        
        # Check patterns
        for domain_name, rules in domains.items():
            for pattern in rules.get('path_patterns', []):
                 if fnmatch(path, pattern) or fnmatch(path, f"**/{pattern}"):
                     return domain_name
        return "unknown"

    def is_edit_allowed(self, user_id: str, path: str, change_meta: Dict[str, Any] = None) -> Tuple[bool, str]:
        domain = self.get_domain(path)
        rules = self.config.get('domains', {}).get(domain, {})
        policy = rules.get('policy', 'read_only')
        
        if policy == 'read_only':
            return False, f"Path {path} is in READ-ONLY domain: {domain}"
            
        if policy == 'modifiable_with_approval':
            # In a real check, we'd look for approval in change_meta
            if change_meta and change_meta.get('approved'):
                return True, "Approved"
            return False, f"Path {path} requires approval"
            
        if policy == 'auto_allowed':
            return True, "Auto Allowed"
            
        return False, "Unknown Policy"
