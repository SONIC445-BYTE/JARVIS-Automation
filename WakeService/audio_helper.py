"""
Audio Helper - User-Session Audio Capture
==========================================
Runs in user session to capture audio (mic access).
Communicates with Windows Service via named pipe.

BLOCKER FIX: LocalSystem can't access mic, so we split:
- Service = supervisor (runs before login)
- This helper = audio capture (runs in user session)
"""

import os
import sys
import time
import threading
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    import win32pipe
    import win32file
    import pywintypes
    PYWIN32_AVAILABLE = True
except ImportError:
    PYWIN32_AVAILABLE = False

from WakeService.wake_detector import WakeDetector
from WakeService.local_stt import LocalSTT
from WakeService.resource_governor import ResourceGovernor


PIPE_NAME = r'\\.\pipe\JARVISAudioPipe'


class AudioHelper:
    """
    User-session audio helper.
    
    Responsibilities:
    - Capture audio (has mic access in user context)
    - Detect wake word
    - Recognize speech
    - Send results to Windows Service via named pipe
    """
    
    def __init__(self):
        self.running = False
        self.pipe_handle = None
        self.wake_detector = None
        self.stt = None
        self.governor = ResourceGovernor()
        self.is_active = False
        
    def start(self):
        """Start the audio helper."""
        print("[AudioHelper] Starting...")
        self.running = True
        
        # Connect to service pipe
        self._connect_pipe()
        
        # Initialize audio components
        self.wake_detector = WakeDetector(callback=self._on_wake)
        self.stt = LocalSTT()
        
        # Start wake detection
        self.wake_detector.start()
        print("[AudioHelper] Wake detection started")
        
        # Start heartbeat
        heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        heartbeat_thread.start()
        
        # Main loop
        self._main_loop()
    
    def _connect_pipe(self):
        """Connect to service named pipe."""
        if not PYWIN32_AVAILABLE:
            print("[AudioHelper] pywin32 not available, running standalone")
            return
        
        max_retries = 10
        for i in range(max_retries):
            try:
                self.pipe_handle = win32file.CreateFile(
                    PIPE_NAME,
                    win32file.GENERIC_READ | win32file.GENERIC_WRITE,
                    0, None,
                    win32file.OPEN_EXISTING,
                    0, None
                )
                print("[AudioHelper] Connected to service pipe")
                return
            except pywintypes.error:
                print(f"[AudioHelper] Pipe connect attempt {i+1}/{max_retries}...")
                time.sleep(1)
        
        print("[AudioHelper] Could not connect to service, running standalone")
    
    def _main_loop(self):
        """Main helper loop."""
        while self.running:
            # Apply resource governance
            self.governor.apply_throttle(self.is_active)
            
            # Check for messages from service
            self._check_pipe()
            
            time.sleep(0.1)
    
    def _on_wake(self):
        """Called when wake word detected."""
        print("[AudioHelper] Wake word detected!")
        self.is_active = True
        
        # Notify service
        self._send_to_service("WAKE:JARVIS")
        
        # Enter active mode
        self._active_mode()
    
    def _active_mode(self):
        """Process commands in active mode."""
        print("[AudioHelper] Entering active mode")
        
        # Speak acknowledgment
        self._speak("Yes?")
        
        # Listen for command with timeout
        timeout = 15.0
        start = time.time()
        
        while self.is_active and (time.time() - start) < timeout:
            text = self.stt.listen_once(timeout=5)
            
            if text:
                print(f"[AudioHelper] Heard: {text}")
                
                # Check for sleep/shutdown
                if any(phrase in text.lower() for phrase in ["go to sleep", "stop", "never mind"]):
                    self._speak("Going to sleep")
                    break
                    
                if any(phrase in text.lower() for phrase in ["shut down", "shutdown"]):
                    self._speak("Are you sure you want to shut down?")
                    confirm = self.stt.listen_once(timeout=5)
                    if confirm and "yes" in confirm.lower():
                        self._send_to_service("COMMAND:shutdown")
                        self._speak("Shutting down")
                        self.running = False
                        break
                    else:
                        self._speak("Shutdown cancelled")
                        continue
                
                # Send command to service
                self._send_to_service(f"COMMAND:{text}")
                
                # Reset timeout
                start = time.time()
        
        print("[AudioHelper] Returning to sleep mode")
        self.is_active = False
    
    def _send_to_service(self, message: str):
        """Send message to service via pipe."""
        if self.pipe_handle:
            try:
                win32file.WriteFile(self.pipe_handle, message.encode('utf-8'))
            except:
                pass
        else:
            # Standalone mode - write directly to input.txt
            if message.startswith("COMMAND:"):
                command = message[8:]
                input_file = PROJECT_ROOT / "input.txt"
                with open(input_file, "w") as f:
                    f.write(f"jarvis {command}".lower())
    
    def _check_pipe(self):
        """Check for messages from service."""
        if not self.pipe_handle:
            return
        
        try:
            result, data = win32file.ReadFile(self.pipe_handle, 4096)
            if data:
                message = data.decode('utf-8').strip()
                print(f"[AudioHelper] Service message: {message}")
        except:
            pass
    
    def _heartbeat_loop(self):
        """Send heartbeats to service."""
        while self.running:
            self._send_to_service("HEARTBEAT")
            time.sleep(5)
    
    def _speak(self, text: str):
        """Speak using TTS."""
        try:
            from TextToSpeech.Fast_DF_TTS import speak
            speak(text)
        except:
            try:
                import pyttsx3
                engine = pyttsx3.init()
                engine.say(text)
                engine.runAndWait()
            except:
                print(f"[AudioHelper] TTS: {text}")
    
    def stop(self):
        """Stop the helper."""
        self.running = False
        if self.wake_detector:
            self.wake_detector.stop()
        if self.pipe_handle:
            try:
                win32file.CloseHandle(self.pipe_handle)
            except:
                pass
        print("[AudioHelper] Stopped")


def main():
    """Run audio helper."""
    helper = AudioHelper()
    try:
        helper.start()
    except KeyboardInterrupt:
        helper.stop()


if __name__ == "__main__":
    main()
