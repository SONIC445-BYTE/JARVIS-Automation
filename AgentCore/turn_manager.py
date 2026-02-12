"""
Turn Manager - User Turn and Barge-In Detection
=================================================
Handles turn-taking and interruptions.

Sprint 6: Conversational Intelligence
"""

import time
from typing import Optional, Callable
from threading import Thread, Event
from dataclasses import dataclass


@dataclass
class TurnConfig:
    """Turn management configuration."""
    silence_threshold: float = 1.5   # Seconds of silence = end of turn
    min_speech_duration: float = 0.3  # Min speech to count as turn
    barge_in_enabled: bool = True    # Allow interrupting JARVIS
    volume_threshold: float = 0.02   # Audio level threshold


class TurnManager:
    """
    Manages conversation turn-taking.
    
    Features:
    - Silence detection (end of user turn)
    - Barge-in handling (user interrupts)
    - Turn validation
    """
    
    def __init__(self, config: TurnConfig = None):
        self.config = config or TurnConfig()
        
        self._in_user_turn = Event()
        self._barge_in = Event()
        self._speech_start: Optional[float] = None
        self._last_speech: Optional[float] = None
    
    def on_speech_detected(self, volume: float = 0.0):
        """
        Called when speech/audio is detected.
        
        Args:
            volume: Audio volume level
        """
        now = time.time()
        
        if not self._in_user_turn.is_set():
            if volume > self.config.volume_threshold:
                self._in_user_turn.set()
                self._speech_start = now
                self._last_speech = now
        else:
            if volume > self.config.volume_threshold:
                self._last_speech = now
    
    def on_silence_detected(self):
        """Called when silence is detected."""
        if self._in_user_turn.is_set() and self._last_speech:
            silence_duration = time.time() - self._last_speech
            
            if silence_duration >= self.config.silence_threshold:
                # Turn complete
                self._in_user_turn.clear()
    
    def is_user_speaking(self) -> bool:
        """Check if user is currently speaking."""
        return self._in_user_turn.is_set()
    
    def is_turn_complete(self) -> bool:
        """Check if user turn is complete."""
        if not self._in_user_turn.is_set():
            return True
        
        if self._last_speech:
            silence = time.time() - self._last_speech
            return silence >= self.config.silence_threshold
        
        return False
    
    def wait_for_turn_complete(self, timeout: float = 30) -> bool:
        """
        Wait for user to finish speaking.
        
        Args:
            timeout: Max wait time
            
        Returns:
            True if turn complete, False if timeout
        """
        start = time.time()
        
        while time.time() - start < timeout:
            if self.is_turn_complete():
                return True
            time.sleep(0.1)
        
        return False
    
    def get_turn_duration(self) -> float:
        """Get duration of current/last turn."""
        if self._speech_start and self._last_speech:
            return self._last_speech - self._speech_start
        return 0.0
    
    def is_valid_turn(self) -> bool:
        """Check if turn meets minimum duration."""
        return self.get_turn_duration() >= self.config.min_speech_duration
    
    # Barge-in handling
    
    def check_barge_in(self, is_jarvis_speaking: bool, user_audio_level: float) -> bool:
        """
        Check if user is interrupting JARVIS.
        
        Args:
            is_jarvis_speaking: Whether JARVIS is currently speaking
            user_audio_level: Current user audio level
            
        Returns:
            True if barge-in detected
        """
        if not self.config.barge_in_enabled:
            return False
        
        if is_jarvis_speaking and user_audio_level > self.config.volume_threshold:
            self._barge_in.set()
            return True
        
        return False
    
    def consume_barge_in(self) -> bool:
        """
        Check and clear barge-in flag.
        
        Returns:
            True if barge-in was pending
        """
        was_set = self._barge_in.is_set()
        self._barge_in.clear()
        return was_set
    
    def reset(self):
        """Reset turn state."""
        self._in_user_turn.clear()
        self._barge_in.clear()
        self._speech_start = None
        self._last_speech = None


class SilenceDetector:
    """
    Detects silence in audio stream.
    
    Used for:
    - End of user turn
    - Auto-sleep trigger
    """
    
    def __init__(self, threshold: float = 0.02, window: float = 1.0):
        self.threshold = threshold
        self.window = window
        self._samples: list = []
        self._last_sample_time: float = 0
    
    def add_sample(self, volume: float):
        """Add audio volume sample."""
        now = time.time()
        self._samples.append((now, volume))
        
        # Remove old samples
        cutoff = now - self.window
        self._samples = [(t, v) for t, v in self._samples if t > cutoff]
    
    def is_silent(self) -> bool:
        """Check if current window is silent."""
        if not self._samples:
            return True
        
        avg_volume = sum(v for _, v in self._samples) / len(self._samples)
        return avg_volume < self.threshold
    
    def get_silence_duration(self) -> float:
        """Get duration of current silence."""
        if not self._samples:
            return float('inf')
        
        # Find last non-silent sample
        for t, v in reversed(self._samples):
            if v >= self.threshold:
                return time.time() - t
        
        return self.window


def test_turn_manager():
    """Test turn manager."""
    print("Turn Manager Test")
    print("=" * 50)
    
    manager = TurnManager()
    
    # Simulate speech
    print("Simulating speech...")
    manager.on_speech_detected(0.1)
    print(f"User speaking: {manager.is_user_speaking()}")
    
    time.sleep(0.5)
    manager.on_speech_detected(0.15)
    
    time.sleep(0.5)
    manager.on_speech_detected(0.05)
    
    print(f"Turn duration: {manager.get_turn_duration():.2f}s")
    print(f"Valid turn: {manager.is_valid_turn()}")
    
    # Simulate silence
    print("\nSimulating silence...")
    time.sleep(2)
    manager.on_silence_detected()
    print(f"Turn complete: {manager.is_turn_complete()}")


if __name__ == "__main__":
    test_turn_manager()
