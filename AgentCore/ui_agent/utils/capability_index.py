import json
import os
from typing import Dict, Any, List

class PlatformCapabilityIndex:
    """Tracks platform capabilities and persists them to disk."""
    
    def __init__(self, index_path: str = "data/platform_index.json"):
        self.index_path = index_path
        self.index = {} # platform_name -> {actions: [], modes: []}

    def update(self, platform_name: str, actions: List[str], modes: List[str]):
        self.index[platform_name] = {
            "actions": sorted(list(set(actions))),
            "modes": sorted(list(set(modes)))
        }
        self.persist()

    def persist(self):
        os.makedirs(os.path.dirname(self.index_path), exist_ok=True)
        with open(self.index_path, "w") as f:
            json.dump(self.index, f, indent=2)

    def get_platforms_for_action(self, action: str) -> List[str]:
        return [p for p, data in self.index.items() if action in data["actions"]]

capability_index = PlatformCapabilityIndex()
