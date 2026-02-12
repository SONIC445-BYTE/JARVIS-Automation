"""
Permission Engine - Role-Based Access Control
===============================================
Manages permissions for actions based on user profiles.

Sprint 5: Trust & Identity
"""

import re
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field
from enum import Enum


class Permission(Enum):
    """Available permissions."""
    # Read operations
    READ_FILES = "read_files"
    READ_SETTINGS = "read_settings"
    READ_HISTORY = "read_history"
    
    # Write operations
    WRITE_FILES = "write_files"
    MODIFY_SETTINGS = "modify_settings"
    
    # App operations
    OPEN_APPS = "open_apps"
    CLOSE_APPS = "close_apps"
    SEND_MESSAGES = "send_messages"
    
    # System operations
    SYSTEM_COMMANDS = "system_commands"
    INSTALL_SOFTWARE = "install_software"
    NETWORK_ACCESS = "network_access"
    
    # Administrative
    MANAGE_PROFILES = "manage_profiles"
    VIEW_AUDIT_LOG = "view_audit_log"
    MODIFY_POLICIES = "modify_policies"


class Role(Enum):
    """User roles with preset permission sets."""
    OWNER = "owner"       # Full access
    ADMIN = "admin"       # Most access, no policy changes
    USER = "user"         # Standard operations
    GUEST = "guest"       # Limited, read-only
    CHILD = "child"       # Restricted access


# Default permissions per role
ROLE_PERMISSIONS: Dict[Role, Set[Permission]] = {
    Role.OWNER: set(Permission),  # All permissions
    
    Role.ADMIN: {
        Permission.READ_FILES, Permission.READ_SETTINGS, Permission.READ_HISTORY,
        Permission.WRITE_FILES, Permission.MODIFY_SETTINGS,
        Permission.OPEN_APPS, Permission.CLOSE_APPS, Permission.SEND_MESSAGES,
        Permission.SYSTEM_COMMANDS, Permission.NETWORK_ACCESS,
        Permission.MANAGE_PROFILES, Permission.VIEW_AUDIT_LOG
    },
    
    Role.USER: {
        Permission.READ_FILES, Permission.READ_SETTINGS,
        Permission.WRITE_FILES,
        Permission.OPEN_APPS, Permission.CLOSE_APPS, Permission.SEND_MESSAGES,
        Permission.NETWORK_ACCESS
    },
    
    Role.GUEST: {
        Permission.READ_FILES, Permission.READ_SETTINGS,
        Permission.OPEN_APPS
    },
    
    Role.CHILD: {
        Permission.READ_FILES,
        Permission.OPEN_APPS
    }
}


@dataclass
class AccessDecision:
    """Result of permission check."""
    allowed: bool
    permission: Permission
    reason: str
    require_confirmation: bool = False


@dataclass
class PolicyRule:
    """Custom permission rule."""
    rule_id: str
    permission: Permission
    effect: str  # "allow" or "deny"
    conditions: Dict = field(default_factory=dict)
    # Conditions can include: time_range, app_whitelist, etc.


class PermissionEngine:
    """
    Evaluates permissions for actions.
    
    Checks:
    - Role-based permissions
    - Custom policy rules
    - Time-based restrictions
    - App whitelists/blacklists
    """
    
    def __init__(self):
        self._custom_rules: Dict[str, PolicyRule] = {}
        self._app_whitelist: Set[str] = set()
        self._app_blacklist: Set[str] = set()
        self._time_restrictions: Dict[str, tuple] = {}  # permission -> (start_hour, end_hour)
    
    def check(self, permission: Permission, role: Role, 
             context: Dict = None) -> AccessDecision:
        """
        Check if permission is allowed.
        
        Args:
            permission: Permission to check
            role: User's role
            context: Additional context (app_name, time, etc.)
            
        Returns:
            AccessDecision
        """
        context = context or {}
        
        # Check role permissions first
        role_perms = ROLE_PERMISSIONS.get(role, set())
        
        if permission not in role_perms:
            return AccessDecision(
                allowed=False,
                permission=permission,
                reason=f"Permission {permission.value} not granted to role {role.value}"
            )
        
        # Check custom deny rules
        for rule in self._custom_rules.values():
            if rule.permission == permission and rule.effect == "deny":
                if self._rule_matches(rule, context):
                    return AccessDecision(
                        allowed=False,
                        permission=permission,
                        reason=f"Denied by rule: {rule.rule_id}"
                    )
        
        # Check app whitelist/blacklist
        app_name = context.get("app_name", "").lower()
        if app_name:
            if self._app_blacklist and app_name in self._app_blacklist:
                return AccessDecision(
                    allowed=False,
                    permission=permission,
                    reason=f"App '{app_name}' is blacklisted"
                )
            
            if self._app_whitelist and app_name not in self._app_whitelist:
                return AccessDecision(
                    allowed=False,
                    permission=permission,
                    reason=f"App '{app_name}' is not in whitelist"
                )
        
        # Check time restrictions
        if permission.value in self._time_restrictions:
            import datetime
            current_hour = datetime.datetime.now().hour
            start, end = self._time_restrictions[permission.value]
            
            if not (start <= current_hour < end):
                return AccessDecision(
                    allowed=False,
                    permission=permission,
                    reason=f"Permission only allowed between {start}:00 and {end}:00"
                )
        
        # Check if confirmation required (for high-risk permissions)
        require_confirm = permission in [
            Permission.SYSTEM_COMMANDS,
            Permission.INSTALL_SOFTWARE,
            Permission.MODIFY_POLICIES
        ]
        
        return AccessDecision(
            allowed=True,
            permission=permission,
            reason="Allowed",
            require_confirmation=require_confirm
        )
    
    def _rule_matches(self, rule: PolicyRule, context: Dict) -> bool:
        """Check if rule conditions match context."""
        for key, value in rule.conditions.items():
            if key not in context:
                continue
            
            if isinstance(value, list):
                if context[key] not in value:
                    return False
            elif context[key] != value:
                return False
        
        return True
    
    def add_rule(self, permission: Permission, effect: str, 
                conditions: Dict = None, rule_id: str = None) -> PolicyRule:
        """
        Add a custom permission rule.
        
        Args:
            permission: Permission to affect
            effect: "allow" or "deny"
            conditions: When rule applies
            rule_id: Custom rule ID (auto-generated if None)
        """
        if rule_id is None:
            rule_id = f"rule_{len(self._custom_rules) + 1}"
        
        rule = PolicyRule(
            rule_id=rule_id,
            permission=permission,
            effect=effect,
            conditions=conditions or {}
        )
        
        self._custom_rules[rule_id] = rule
        return rule
    
    def remove_rule(self, rule_id: str) -> bool:
        """Remove a custom rule."""
        return self._custom_rules.pop(rule_id, None) is not None
    
    def set_app_whitelist(self, apps: List[str]):
        """Set allowed apps (empty = allow all)."""
        self._app_whitelist = set(a.lower() for a in apps)
    
    def set_app_blacklist(self, apps: List[str]):
        """Set blocked apps."""
        self._app_blacklist = set(a.lower() for a in apps)
    
    def set_time_restriction(self, permission: Permission, 
                            start_hour: int, end_hour: int):
        """Set time-based restriction for a permission."""
        self._time_restrictions[permission.value] = (start_hour, end_hour)
    
    def get_allowed_permissions(self, role: Role) -> List[Permission]:
        """Get all permissions allowed for a role."""
        return list(ROLE_PERMISSIONS.get(role, set()))
    
    def get_rules(self) -> List[Dict]:
        """Get all custom rules."""
        return [
            {
                "rule_id": r.rule_id,
                "permission": r.permission.value,
                "effect": r.effect,
                "conditions": r.conditions
            }
            for r in self._custom_rules.values()
        ]


def test_permission_engine():
    """Test permission engine."""
    print("Permission Engine Test")
    print("=" * 50)
    
    engine = PermissionEngine()
    
    # Check owner permissions
    result = engine.check(Permission.SYSTEM_COMMANDS, Role.OWNER)
    print(f"Owner - system commands: {result.allowed} (confirm: {result.require_confirmation})")
    
    # Check guest permissions
    result = engine.check(Permission.WRITE_FILES, Role.GUEST)
    print(f"Guest - write files: {result.allowed} ({result.reason})")
    
    # Add custom rule
    engine.add_rule(Permission.SEND_MESSAGES, "deny", {"app_name": "telegram"})
    
    # Check with context
    result = engine.check(Permission.SEND_MESSAGES, Role.USER, {"app_name": "telegram"})
    print(f"User - send messages (telegram): {result.allowed} ({result.reason})")
    
    result = engine.check(Permission.SEND_MESSAGES, Role.USER, {"app_name": "whatsapp"})
    print(f"User - send messages (whatsapp): {result.allowed}")
    
    # Set app blacklist
    engine.set_app_blacklist(["tiktok", "instagram"])
    result = engine.check(Permission.OPEN_APPS, Role.USER, {"app_name": "tiktok"})
    print(f"User - open tiktok: {result.allowed} ({result.reason})")


if __name__ == "__main__":
    test_permission_engine()
