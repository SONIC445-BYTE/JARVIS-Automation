"""
Namespace Manager.
Isolates resources by namespace.
"""
class NamespaceManager:
    def __init__(self):
        self.namespaces = {
            "default": {"experiments": []}
        }

    def get_namespace(self, project_id: str) -> str:
        # Simple mapping
        return "default"

    def register_experiment(self, namespace: str, experiment_id: str) -> bool:
        if namespace not in self.namespaces:
            self.namespaces[namespace] = {"experiments": []}
            
        # Check limits (mock)
        if len(self.namespaces[namespace]["experiments"]) >= 5:
            return False
            
        self.namespaces[namespace]["experiments"].append(experiment_id)
        return True
