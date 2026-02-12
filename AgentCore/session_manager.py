"""
Session Manager - Timeboxed Sessions
=======================================
Manages authenticated sessions with expiry.

Sprint 5: Trust & Identity
"""

import time
import uuid
from typing import Dict, Optional
from dataclasses import dataclass, field
from threading import Timer


@dataclass
class Session:
    """Active session."""
    session_id: str
    profile_id: str
    profile_name: str
    role: str
    
    created_at: float = field(default_factory=time.time)
    expires_at: float = 0
    last_activity: float = field(default_factory=time.time)
    
    # Security
    verification_level: str = "standard"  # standard, enhanced, full
    voice_verified: bool = False
    
    # Activity
    action_count: int = 0
    
    def is_expired(self) -> bool:
        """Check if session has expired."""
        return time.time() > self.expires_at
    
    def remaining_seconds(self) -> float:
        """Get remaining session time."""
        return max(0, self.expires_at - time.time())
    
    def extend(self, seconds: float):
        """Extend session expiry."""
        self.expires_at = time.time() + seconds
    
    def record_activity(self):
        """Record activity in session."""
        self.last_activity = time.time()
        self.action_count += 1


class SessionManager:
    """
    Manages authenticated sessions.
    
    Features:
    - Timeboxed sessions with auto-expiry
    - Session extension on activity
    - Multiple verification levels
    - Auto-lock on idle
    """
    
    DEFAULT_SESSION_DURATION = 3600  # 1 hour
    IDLE_TIMEOUT = 900  # 15 minutes
    MAX_SESSION_DURATION = 86400  # 24 hours
    
    def __init__(self):
        self._sessions: Dict[str, Session] = {}
        self._current_session_id: Optional[str] = None
        self._expiry_timers: Dict[str, Timer] = {}
        self._activity_timer: Optional[Timer] = None
    
    def create_session(self, profile_id: str, profile_name: str, 
                      role: str, voice_verified: bool = False,
                      duration: float = None) -> Session:
        """
        Create a new session.
        
        Args:
            profile_id: User profile ID
            profile_name: Display name
            role: User role
            voice_verified: Whether voice was verified
            duration: Session duration in seconds
            
        Returns:
            Created Session
        """
        session_id = str(uuid.uuid4())[:16]
        
        if duration is None:
            duration = self.DEFAULT_SESSION_DURATION
        
        duration = min(duration, self.MAX_SESSION_DURATION)
        
        session = Session(
            session_id=session_id,
            profile_id=profile_id,
            profile_name=profile_name,
            role=role,
            expires_at=time.time() + duration,
            voice_verified=voice_verified,
            verification_level="enhanced" if voice_verified else "standard"
        )
        
        self._sessions[session_id] = session
        self._current_session_id = session_id
        
        self._set_expiry_timer(session_id, duration)
        self._start_activity_monitor()
        
        print(f"[SessionManager] Created session for {profile_name} ({role})")
        return session
    
    def _set_expiry_timer(self, session_id: str, duration: float):
        """Set timer for session expiry."""
        # Cancel existing timer
        if session_id in self._expiry_timers:
            self._expiry_timers[session_id].cancel()
        
        timer = Timer(duration, self._on_session_expired, [session_id])
        timer.daemon = True
        timer.start()
        self._expiry_timers[session_id] = timer
    
    def _on_session_expired(self, session_id: str):
        """Handle session expiry."""
        session = self._sessions.get(session_id)
        if session:
            print(f"[SessionManager] Session expired: {session.profile_name}")
            self.end_session(session_id)
    
    def _start_activity_monitor(self):
        """Start idle timeout monitor."""
        if self._activity_timer:
            self._activity_timer.cancel()
        
        self._activity_timer = Timer(self.IDLE_TIMEOUT, self._on_idle_timeout)
        self._activity_timer.daemon = True
        self._activity_timer.start()
    
    def _on_idle_timeout(self):
        """Handle idle timeout."""
        session = self.get_current_session()
        if session:
            idle_time = time.time() - session.last_activity
            if idle_time >= self.IDLE_TIMEOUT:
                print(f"[SessionManager] Session idle timeout: {session.profile_name}")
                self.lock_session(session.session_id)
    
    def record_activity(self):
        """Record user activity (resets idle timer)."""
        session = self.get_current_session()
        if session:
            session.record_activity()
            self._start_activity_monitor()
    
    def get_session(self, session_id: str) -> Optional[Session]:
        """Get session by ID."""
        session = self._sessions.get(session_id)
        if session and not session.is_expired():
            return session
        return None
    
    def get_current_session(self) -> Optional[Session]:
        """Get current active session."""
        if self._current_session_id:
            return self.get_session(self._current_session_id)
        return None
    
    def extend_session(self, session_id: str = None, 
                      minutes: float = 30) -> bool:
        """
        Extend session duration.
        
        Args:
            session_id: Session to extend (None = current)
            minutes: Minutes to add
            
        Returns:
            True if extended
        """
        if session_id is None:
            session_id = self._current_session_id
        
        session = self.get_session(session_id)
        if not session:
            return False
        
        # Check max duration
        current_duration = session.expires_at - session.created_at
        additional = minutes * 60
        
        if current_duration + additional > self.MAX_SESSION_DURATION:
            additional = self.MAX_SESSION_DURATION - current_duration
        
        if additional <= 0:
            return False
        
        session.extend(session.remaining_seconds() + additional)
        self._set_expiry_timer(session_id, session.remaining_seconds())
        
        print(f"[SessionManager] Extended session by {minutes} minutes")
        return True
    
    def lock_session(self, session_id: str = None):
        """Lock session (requires re-verification to unlock)."""
        if session_id is None:
            session_id = self._current_session_id
        
        session = self._sessions.get(session_id)
        if session:
            session.verification_level = "locked"
            print(f"[SessionManager] Session locked: {session.profile_name}")
    
    def unlock_session(self, session_id: str, voice_verified: bool = False) -> bool:
        """Unlock a locked session."""
        session = self._sessions.get(session_id)
        if not session:
            return False
        
        if session.verification_level == "locked":
            session.verification_level = "enhanced" if voice_verified else "standard"
            session.record_activity()
            return True
        
        return False
    
    def end_session(self, session_id: str = None):
        """End a session."""
        if session_id is None:
            session_id = self._current_session_id
        
        if session_id in self._sessions:
            session = self._sessions[session_id]
            print(f"[SessionManager] Ended session: {session.profile_name}")
            
            del self._sessions[session_id]
            
            if session_id in self._expiry_timers:
                self._expiry_timers[session_id].cancel()
                del self._expiry_timers[session_id]
        
        if self._current_session_id == session_id:
            self._current_session_id = None
    
    def end_all_sessions(self):
        """End all sessions (logout everywhere)."""
        for timer in self._expiry_timers.values():
            timer.cancel()
        
        self._sessions.clear()
        self._expiry_timers.clear()
        self._current_session_id = None
        
        if self._activity_timer:
            self._activity_timer.cancel()
        
        print("[SessionManager] All sessions ended")
    
    def is_authenticated(self) -> bool:
        """Check if there's an active, unlocked session."""
        session = self.get_current_session()
        return session is not None and session.verification_level != "locked"
    
    def get_verification_level(self) -> str:
        """Get current verification level."""
        session = self.get_current_session()
        return session.verification_level if session else "none"
    
    def get_active_sessions(self) -> list:
        """Get all active sessions."""
        return [
            {
                "session_id": s.session_id,
                "profile_name": s.profile_name,
                "role": s.role,
                "remaining_minutes": int(s.remaining_seconds() / 60),
                "verification_level": s.verification_level,
                "is_current": s.session_id == self._current_session_id
            }
            for s in self._sessions.values()
            if not s.is_expired()
        ]


def test_session_manager():
    """Test session manager."""
    print("Session Manager Test")
    print("=" * 50)
    
    manager = SessionManager()
    
    # Create session
    session = manager.create_session(
        profile_id="profile_1",
        profile_name="Test User",
        role="user",
        voice_verified=True,
        duration=60  # 1 minute for testing
    )
    
    print(f"Created: {session.session_id}")
    print(f"Expires in: {session.remaining_seconds():.0f}s")
    print(f"Authenticated: {manager.is_authenticated()}")
    print(f"Verification: {manager.get_verification_level()}")
    
    # Record activity
    manager.record_activity()
    print("Activity recorded")
    
    # Extend session
    manager.extend_session(minutes=5)
    print(f"Extended. Expires in: {session.remaining_seconds():.0f}s")
    
    # Lock session
    manager.lock_session()
    print(f"Locked. Authenticated: {manager.is_authenticated()}")
    
    # Unlock
    manager.unlock_session(session.session_id, voice_verified=True)
    print(f"Unlocked. Authenticated: {manager.is_authenticated()}")
    
    # List sessions
    print(f"Active sessions: {manager.get_active_sessions()}")
    
    # End session
    manager.end_session()
    print(f"Ended. Authenticated: {manager.is_authenticated()}")


if __name__ == "__main__":
    test_session_manager()
