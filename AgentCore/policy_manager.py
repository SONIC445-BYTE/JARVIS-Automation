"""
Policy Manager - Profile & Policy Configuration
=================================================
Manages user profiles and their associated policies.

Sprint 5: Trust & Identity
"""

import os
import json
import time
from typing import Dict, List, Optional
from dataclasses import dataclass, field, asdict
from pathlib import Path

from .permission_engine import Role, Permission, PermissionEngine


@dataclass
class UserProfile:
    """User profile with role and custom policies."""
    profile_id: str
    name: str
    role: Role
    voice_profile_id: Optional[str] = None
    
    # Custom permissions (overrides role defaults)
    extra_permissions: List[str] = field(default_factory=list)
    denied_permissions: List[str] = field(default_factory=list)
    
    # Restrictions
    app_whitelist: List[str] = field(default_factory=list)
    app_blacklist: List[str] = field(default_factory=list)
    time_restrictions: Dict[str, tuple] = field(default_factory=dict)
    
    # Metadata
    created_at: float = field(default_factory=time.time)
    last_active: Optional[float] = None
    is_active: bool = True
    
    def to_dict(self) -> Dict:
        d = asdict(self)
        d['role'] = self.role.value
        return d
    
    @staticmethod
    def from_dict(data: Dict) -> 'UserProfile':
        data['role'] = Role(data['role'])
        return UserProfile(**data)


class PolicyManager:
    """
    Manages user profiles and policies.
    
    Features:
    - Create/update/delete profiles
    - Switch active profile
    - Configure per-profile permissions
    - Export/import configuration
    """
    
    def __init__(self, config_dir: Optional[Path] = None):
        if config_dir is None:
            config_dir = Path(__file__).parent.parent / "data" / "policies"
        
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        self._profiles_file = self.config_dir / "profiles.json"
        
        self._profiles: Dict[str, UserProfile] = {}
        self._active_profile_id: Optional[str] = None
        self._permission_engine = PermissionEngine()
        
        self._load()
    
    def _load(self):
        """Load profiles from disk."""
        if not self._profiles_file.exists():
            return
        
        try:
            with open(self._profiles_file, 'r') as f:
                data = json.load(f)
            
            for profile_data in data.get("profiles", []):
                profile = UserProfile.from_dict(profile_data)
                self._profiles[profile.profile_id] = profile
            
            self._active_profile_id = data.get("active_profile")
            
        except Exception as e:
            print(f"[PolicyManager] Load error: {e}")
    
    def _save(self):
        """Save profiles to disk."""
        try:
            data = {
                "profiles": [p.to_dict() for p in self._profiles.values()],
                "active_profile": self._active_profile_id,
                "updated_at": time.time()
            }
            
            with open(self._profiles_file, 'w') as f:
                json.dump(data, f, indent=2)
                
        except Exception as e:
            print(f"[PolicyManager] Save error: {e}")
    
    def create_profile(self, name: str, role: Role = Role.USER,
                      voice_profile_id: str = None) -> UserProfile:
        """
        Create a new user profile.
        
        Args:
            name: Display name
            role: User role
            voice_profile_id: Associated voice profile
            
        Returns:
            Created UserProfile
        """
        import hashlib
        profile_id = hashlib.md5(f"{name}_{time.time()}".encode()).hexdigest()[:8]
        
        profile = UserProfile(
            profile_id=profile_id,
            name=name,
            role=role,
            voice_profile_id=voice_profile_id
        )
        
        self._profiles[profile_id] = profile
        self._save()
        
        print(f"[PolicyManager] Created profile: {name} ({role.value})")
        return profile
    
    def get_profile(self, profile_id: str) -> Optional[UserProfile]:
        """Get a profile by ID."""
        return self._profiles.get(profile_id)
    
    def update_profile(self, profile_id: str, **kwargs) -> Optional[UserProfile]:
        """Update profile fields."""
        profile = self._profiles.get(profile_id)
        if not profile:
            return None
        
        for key, value in kwargs.items():
            if hasattr(profile, key):
                if key == 'role' and isinstance(value, str):
                    value = Role(value)
                setattr(profile, key, value)
        
        self._save()
        return profile
    
    def delete_profile(self, profile_id: str) -> bool:
        """Delete a profile."""
        if profile_id not in self._profiles:
            return False
        
        del self._profiles[profile_id]
        
        if self._active_profile_id == profile_id:
            self._active_profile_id = None
        
        self._save()
        return True
    
    def set_active_profile(self, profile_id: str) -> bool:
        """Set the active profile."""
        if profile_id not in self._profiles:
            return False
        
        self._active_profile_id = profile_id
        self._profiles[profile_id].last_active = time.time()
        self._save()
        
        # Apply profile to permission engine
        self._apply_profile(self._profiles[profile_id])
        
        return True
    
    def get_active_profile(self) -> Optional[UserProfile]:
        """Get currently active profile."""
        if self._active_profile_id:
            return self._profiles.get(self._active_profile_id)
        return None
    
    def _apply_profile(self, profile: UserProfile):
        """Apply profile settings to permission engine."""
        # Set app restrictions
        if profile.app_whitelist:
            self._permission_engine.set_app_whitelist(profile.app_whitelist)
        else:
            self._permission_engine.set_app_whitelist([])
        
        if profile.app_blacklist:
            self._permission_engine.set_app_blacklist(profile.app_blacklist)
        else:
            self._permission_engine.set_app_blacklist([])
        
        # Set time restrictions
        for perm_str, (start, end) in profile.time_restrictions.items():
            try:
                perm = Permission(perm_str)
                self._permission_engine.set_time_restriction(perm, start, end)
            except:
                pass
    
    def check_permission(self, permission: Permission, context: Dict = None):
        """Check permission for active profile."""
        profile = self.get_active_profile()
        if not profile:
            return None
        
        return self._permission_engine.check(permission, profile.role, context)
    
    # Profile policies
    
    def grant_permission(self, profile_id: str, permission: Permission):
        """Grant extra permission to profile."""
        profile = self._profiles.get(profile_id)
        if profile and permission.value not in profile.extra_permissions:
            profile.extra_permissions.append(permission.value)
            self._save()
    
    def revoke_permission(self, profile_id: str, permission: Permission):
        """Deny permission for profile."""
        profile = self._profiles.get(profile_id)
        if profile and permission.value not in profile.denied_permissions:
            profile.denied_permissions.append(permission.value)
            self._save()
    
    def set_app_restrictions(self, profile_id: str, 
                            whitelist: List[str] = None,
                            blacklist: List[str] = None):
        """Set app restrictions for profile."""
        profile = self._profiles.get(profile_id)
        if profile:
            if whitelist is not None:
                profile.app_whitelist = whitelist
            if blacklist is not None:
                profile.app_blacklist = blacklist
            self._save()
    
    def set_time_restriction(self, profile_id: str, permission: Permission,
                            start_hour: int, end_hour: int):
        """Set time restriction for a permission."""
        profile = self._profiles.get(profile_id)
        if profile:
            profile.time_restrictions[permission.value] = (start_hour, end_hour)
            self._save()
    
    # Export/Import
    
    def export_config(self, output_file: Path) -> bool:
        """Export all profiles to file."""
        try:
            data = {
                "version": 1,
                "exported_at": time.time(),
                "profiles": [p.to_dict() for p in self._profiles.values()]
            }
            
            with open(output_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            return True
        except Exception as e:
            print(f"[PolicyManager] Export error: {e}")
            return False
    
    def import_config(self, input_file: Path) -> bool:
        """Import profiles from file."""
        try:
            with open(input_file, 'r') as f:
                data = json.load(f)
            
            for profile_data in data.get("profiles", []):
                profile = UserProfile.from_dict(profile_data)
                self._profiles[profile.profile_id] = profile
            
            self._save()
            return True
            
        except Exception as e:
            print(f"[PolicyManager] Import error: {e}")
            return False
    
    def list_profiles(self) -> List[Dict]:
        """List all profiles."""
        return [
            {
                "profile_id": p.profile_id,
                "name": p.name,
                "role": p.role.value,
                "is_active": p.profile_id == self._active_profile_id,
                "has_voice": p.voice_profile_id is not None
            }
            for p in self._profiles.values()
        ]


def test_policy_manager():
    """Test policy manager."""
    print("Policy Manager Test")
    print("=" * 50)
    
    manager = PolicyManager()
    
    # Create profiles
    owner = manager.create_profile("Dad", Role.OWNER)
    child = manager.create_profile("Kid", Role.CHILD)
    
    # Set active
    manager.set_active_profile(owner.profile_id)
    print(f"Active: {manager.get_active_profile().name}")
    
    # Set restrictions for child
    manager.set_app_restrictions(child.profile_id, 
                                blacklist=["tiktok", "instagram"])
    manager.set_time_restriction(child.profile_id, Permission.OPEN_APPS, 9, 21)
    
    # List profiles
    profiles = manager.list_profiles()
    print(f"Profiles: {profiles}")
    
    # Check permission
    manager.set_active_profile(child.profile_id)
    result = manager.check_permission(Permission.SYSTEM_COMMANDS)
    print(f"Child - system commands: {result}")


if __name__ == "__main__":
    test_policy_manager()
