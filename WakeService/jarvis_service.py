"""
JARVIS Service - Main Entry Point for Persistent Wake System
==============================================================
Runs as background service, always listening.

Start: python -m WakeService.jarvis_service
"""

import os
import sys
import time
import threading
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from WakeService.wake_detector import WakeDetector
from WakeService.local_stt import LocalSTT
from WakeService.mode_manager import ModeManager, JarvisMode


class JarvisService:
    """
    Main JARVIS persistent service.
    
    Lifecycle:
    1. Boot → Initialize all components
    2. Sleep → Listen for "Jarvis" wake word
    3. Wake → Acknowledge, switch to active
    4. Active → Process commands
    5. Sleep → Return after timeout
    """
    
    def __init__(self):
        self.mode_manager = ModeManager()
        self.wake_detector: WakeDetector = None
        self.stt: LocalSTT = None
        self._running = False
        self._main_thread: threading.Thread = None
        
        # Set environment variable for service mode
        os.environ["JARVIS_SERVICE_MODE"] = "1"
    
    def start(self):
        """Start the JARVIS service."""
        print("=" * 60)
        print("JARVIS Persistent Wake Service Starting...")
        print("=" * 60)
        
        self._running = True
        
        # Initialize components
        self._initialize()
        
        # Transition to sleep mode
        self.mode_manager.transition(JarvisMode.SLEEP)
        
        # Start wake word detection
        self.wake_detector.start()
        
        # Speak greeting
        self._speak("JARVIS online. Say Jarvis to wake me.")
        
        print("DEBUG JarvisService: Running in background...")
        print("DEBUG JarvisService: Say 'Jarvis' to wake")
        
        # Keep service alive
        try:
            while self._running:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nShutting down...")
            self.stop()
    
    def _initialize(self):
        """Initialize all service components."""
        print("DEBUG JarvisService: Initializing...")
        
        # Initialize wake detector
        self.wake_detector = WakeDetector(callback=self._on_wake_detected)
        
        # Initialize STT
        self.stt = LocalSTT()
        
        # Set mode change callback
        self.mode_manager.set_callback(self._on_mode_change)
        
        print("DEBUG JarvisService: Components initialized")
    
    def _on_wake_detected(self):
        """Called when wake word detected."""
        if not self.mode_manager.is_sleeping():
            return  # Already awake
        
        print("DEBUG JarvisService: Wake word detected!")
        
        # Transition to wake mode
        self.mode_manager.transition(JarvisMode.WAKE)
        
        # Acknowledge
        self._speak("Yes?")
        
        # Transition to active mode
        self.mode_manager.transition(JarvisMode.ACTIVE)
        
        # Start command processing loop
        self._process_commands()
    
    def _process_commands(self):
        """Process commands in active mode."""
        print("DEBUG JarvisService: Active mode - listening for commands")
        
        while self.mode_manager.is_active():
            # Listen for command
            text = self.stt.listen_once(timeout=10)
            
            if not text:
                print("DEBUG JarvisService: No speech detected")
                continue
            
            print(f"DEBUG JarvisService: Heard: '{text}'")
            
            # Reset timeout
            self.mode_manager.reset_timeout()
            
            # Check for mode-changing commands
            new_mode = self.mode_manager.check_command(text)
            if new_mode:
                if new_mode == JarvisMode.SHUTDOWN:
                    self._speak("Shutting down. Goodbye.")
                    self.stop()
                    return
                elif new_mode == JarvisMode.SLEEP:
                    self._speak("Going to sleep.")
                    self.mode_manager.transition(JarvisMode.SLEEP)
                    return
            
            # Process command through existing system
            self._execute_command(text)
        
        # Returned to sleep
        print("DEBUG JarvisService: Returning to sleep mode")
    
    def _execute_command(self, command: str):
        """Execute command through existing JARVIS system."""
        try:
            # Write to input.txt for existing system to pick up
            input_file = PROJECT_ROOT / "input.txt"
            
            # Add "jarvis" prefix if not present
            if "jarvis" not in command.lower():
                command = f"jarvis {command}"
            
            with open(input_file, "w") as f:
                f.write(command.lower())
            
            print(f"DEBUG JarvisService: Wrote command to input.txt: '{command}'")
            
            # Wait briefly for processing
            time.sleep(0.5)
            
        except Exception as e:
            print(f"ERROR JarvisService: {e}")
            self._speak(f"Error executing command: {str(e)[:50]}")
    
    def _on_mode_change(self, old_mode: JarvisMode, new_mode: JarvisMode):
        """Handle mode transitions."""
        print(f"DEBUG JarvisService: Mode changed: {old_mode.value} → {new_mode.value}")
        
        if new_mode == JarvisMode.SLEEP:
            # Restart wake word detection
            if self.wake_detector:
                self.wake_detector.start()
    
    def _speak(self, text: str):
        """Speak text using existing TTS."""
        try:
            from TextToSpeech.Fast_DF_TTS import speak
            # Run in thread to not block
            threading.Thread(target=speak, args=(text,), daemon=True).start()
        except Exception as e:
            print(f"DEBUG JarvisService: TTS error: {e}")
            # Fallback to pyttsx3
            try:
                import pyttsx3
                engine = pyttsx3.init()
                engine.say(text)
                engine.runAndWait()
            except:
                print(f"JARVIS: {text}")
    
    def stop(self):
        """Stop the service."""
        print("DEBUG JarvisService: Stopping...")
        self._running = False
        
        if self.wake_detector:
            self.wake_detector.stop()
        
        self.mode_manager.transition(JarvisMode.SHUTDOWN)
        print("JARVIS Service stopped.")
    
    def get_status(self) -> dict:
        """Get service status."""
        return {
            "running": self._running,
            **self.mode_manager.get_status()
        }


def run_service():
    """Run JARVIS as a service."""
    service = JarvisService()
    service.start()


if __name__ == "__main__":
    run_service()
