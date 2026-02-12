"""
Resource Guard.
Enforces limits on expensive operations.
"""
import yaml
import os
import time

class ResourceGuard:
    def __init__(self):
        base_path = os.path.dirname(os.path.dirname(__file__))
        self.config_path = os.path.join(base_path, "config", "limits.yaml")
        self.last_request = {}
        self.active_requests = {}
        self._load_config()

    def _load_config(self):
        try:
            with open(self.config_path, 'r') as f:
                self.config = yaml.safe_load(f) or {}
        except Exception:
            self.config = {}

    def allow_request(self, resource_type: str) -> bool:
        limits = self.config.get(resource_type, {})
        if not limits:
            return True
            
        now = time.time()
        
        # Check cooldown
        last = self.last_request.get(resource_type, 0)
        cooldown = limits.get("request_cooldown_s", 0)
        if now - last < cooldown:
            return False
            
        # Check concurrency (mock implementation as we don't have shared state DB)
        # In single process, this works.
        current_active = self.active_requests.get(resource_type, 0)
        max_parallel = limits.get("max_parallel", 1)
        if current_active >= max_parallel:
            return False
            
        self.last_request[resource_type] = now
        self.active_requests[resource_type] = current_active + 1
        return True

    def release_request(self, resource_type: str):
        current = self.active_requests.get(resource_type, 0)
        if current > 0:
            self.active_requests[resource_type] = current - 1
