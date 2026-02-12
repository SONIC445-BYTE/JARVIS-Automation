"""
TTS Engine - Offline Text-to-Speech
=====================================
Piper TTS primary, Windows SAPI fallback.

Sprint 6: Conversational Intelligence
"""

import os
import time
import subprocess
import tempfile
from typing import Optional, Callable
from pathlib import Path
from threading import Thread, Event
from dataclasses import dataclass


@dataclass
class TTSConfig:
    """TTS configuration."""
    voice: str = "en_US-lessac-medium"  # Piper voice
    rate: float = 1.0
    volume: float = 1.0


class TTSEngine:
    """
    Offline text-to-speech.
    
    Priority:
    1. Piper TTS (best quality, offline)
    2. Windows SAPI (fallback, always available)
    
    Features:
    - Async playback
    - Interruption
    - Queue management
    """
    
    def __init__(self, config: TTSConfig = None):
        self.config = config or TTSConfig()
        
        self._speaking = Event()
        self._interrupt = Event()
        self._current_process: Optional[subprocess.Popen] = None
        
        # Check available backends
        self._piper_available = self._check_piper()
        self._backend = "piper" if self._piper_available else "sapi"
        
        print(f"[TTSEngine] Backend: {self._backend}")
    
    def _check_piper(self) -> bool:
        """Check if Piper TTS is available."""
        try:
            result = subprocess.run(
                ["piper", "--help"],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False
    
    def speak(self, text: str, blocking: bool = True) -> bool:
        """
        Speak text.
        
        Args:
            text: Text to speak
            blocking: Wait for completion
            
        Returns:
            True if started successfully
        """
        if not text.strip():
            return False
        
        self._interrupt.clear()
        self._speaking.set()
        
        if blocking:
            self._speak_internal(text)
            return True
        else:
            thread = Thread(target=self._speak_internal, args=(text,))
            thread.daemon = True
            thread.start()
            return True
    
    def _speak_internal(self, text: str):
        """Internal speak implementation."""
        try:
            if self._backend == "piper":
                self._speak_piper(text)
            else:
                self._speak_sapi(text)
        finally:
            self._speaking.clear()
    
    def _speak_piper(self, text: str):
        """Speak using Piper TTS."""
        try:
            # Create temp file for audio
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                wav_path = f.name
            
            # Generate audio
            process = subprocess.Popen(
                ["piper", "--model", self.config.voice, "--output_file", wav_path],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            process.communicate(input=text.encode(), timeout=30)
            
            if self._interrupt.is_set():
                return
            
            # Play audio
            if os.path.exists(wav_path):
                self._play_audio(wav_path)
                os.unlink(wav_path)
                
        except Exception as e:
            print(f"[TTSEngine] Piper error: {e}")
            # Fallback to SAPI
            self._speak_sapi(text)
    
    def _speak_sapi(self, text: str):
        """Speak using Windows SAPI."""
        try:
            # PowerShell command for SAPI
            ps_script = f'''
            Add-Type -AssemblyName System.Speech
            $synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
            $synth.Rate = {int((self.config.rate - 1) * 5)}
            $synth.Volume = {int(self.config.volume * 100)}
            $synth.Speak("{text.replace('"', "'")}")
            '''
            
            self._current_process = subprocess.Popen(
                ["powershell", "-Command", ps_script],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            # Wait with interrupt check
            while self._current_process.poll() is None:
                if self._interrupt.is_set():
                    self._current_process.terminate()
                    return
                time.sleep(0.1)
                
        except Exception as e:
            print(f"[TTSEngine] SAPI error: {e}")
    
    def _play_audio(self, path: str):
        """Play audio file."""
        try:
            # Use PowerShell to play audio
            self._current_process = subprocess.Popen(
                ["powershell", "-Command", f'(New-Object Media.SoundPlayer "{path}").PlaySync()'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            while self._current_process.poll() is None:
                if self._interrupt.is_set():
                    self._current_process.terminate()
                    return
                time.sleep(0.1)
                
        except Exception as e:
            print(f"[TTSEngine] Audio playback error: {e}")
    
    def stop(self):
        """Stop current speech."""
        self._interrupt.set()
        
        if self._current_process:
            try:
                self._current_process.terminate()
            except:
                pass
    
    def is_speaking(self) -> bool:
        """Check if currently speaking."""
        return self._speaking.is_set()
    
    def wait(self, timeout: float = None) -> bool:
        """Wait for speech to complete."""
        return self._speaking.wait(timeout)
    
    # Convenience methods
    
    def greet(self):
        """Speak greeting."""
        self.speak("Yes?", blocking=False)
    
    def confirm(self, action: str = None):
        """Speak confirmation."""
        text = f"Done. {action}" if action else "Done."
        self.speak(text, blocking=False)
    
    def error(self, message: str = None):
        """Speak error."""
        text = message or "I encountered an issue."
        self.speak(text, blocking=False)
    
    def ask(self, question: str):
        """Speak question and wait."""
        self.speak(question, blocking=True)


def test_tts_engine():
    """Test TTS engine."""
    print("TTS Engine Test")
    print("=" * 50)
    
    tts = TTSEngine()
    
    print(f"Backend: {tts._backend}")
    
    # Test speech
    print("Speaking...")
    tts.speak("Hello, I am JARVIS. How can I help you today?")
    
    print("Test complete")


if __name__ == "__main__":
    test_tts_engine()
