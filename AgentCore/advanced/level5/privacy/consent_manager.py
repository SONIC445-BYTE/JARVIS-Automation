"""
Consent Manager for Level-5.
"""
class ConsentManager:
    def __init__(self):
        self.consents = {}

    def grant_consent(self, user_id: str, scope: str):
        self.consents[user_id] = scope

    def has_consent(self, user_id: str) -> bool:
        return user_id in self.consents
