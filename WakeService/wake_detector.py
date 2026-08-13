"""
Wake Word Detector - Vosk-Only FREE Offline Detection
=======================================================
Grammar-restricted keyword spotting for "Jarvis" only.

NO PAID APIS. Fully offline. Low CPU.
"""

import os
import sys
import json
import time
import queue
import threading
from pathlib import Path
from typing import Callable, Optional

# Model configuration
MODEL_DIR = Path(__file__).parent / "models"
MODEL_NAME = "vosk-model-small-en-us-0.15"
MODEL_URL = "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip"


class WakeDetector:
    """
    FREE, OFFLINE wake word detector using Vosk.
    
    Uses grammar-restricted recognition:
    - Grammar: ["jarvis"] only
    - Minimal CPU when idle
    - No paid APIs
    """
    
    # Grammar restricted to wake word ONLY
    WAKE_GRAMMAR = '["jarvis", "[unk]"]'
    
    def __init__(self, callback: Optional[Callable] = None):
        """
        Initialize wake detector.
        
        Args:
            callback: Function to call when "Jarvis" detected
        """
        self.callback = callback
        self.is_listening = False
        self._stop_event = threading.Event()
        self._model = None
        self._recognizer = None
        self._audio_queue = queue.Queue()
        self._listen_thread: Optional[threading.Thread] = None
        # A single spoken "jarvis" can make Vosk's PartialResult() stabilize
        # on the exact text "jarvis" across more than one 250ms chunk before
        # AcceptWaveform finalizes it -- each stable partial re-matched the
        # grammar and called self.callback() again with no guard, firing the
        # wake callback more than once for one utterance (reported live:
        # saying the wake word once activated two conversation loops).
        # Cooldown covers both the partial and the final-result branches,
        # since a final match can also land within the same trailing audio
        # right after a partial already fired.
        self._WAKE_FIRE_COOLDOWN_S = 1.5
        self._last_fire_time = 0.0

        self._initialize()
    
    def _try_fire(self) -> bool:
        """
        Gate a wake-word match behind the cooldown and invoke the
        callback if it passes. Returns whether it fired, so callers can
        decide what (if anything) to print.

        Extracted from the two near-identical fire sites in
        _listen_loop() (AcceptWaveform-final and PartialResult) so the
        debounce logic has exactly one implementation and is directly
        unit-testable without needing a real audio stream.
        """
        now = time.time()
        if now - self._last_fire_time < self._WAKE_FIRE_COOLDOWN_S:
            return False
        self._last_fire_time = now
        if self.callback:
            self.callback()
        return True

    def _initialize(self):
        """Initialize Vosk with grammar restriction."""
        try:
            from vosk import Model, KaldiRecognizer
            
            model_path = MODEL_DIR / MODEL_NAME
            
            if not model_path.exists():
                print("[WakeDetector] Model not found, downloading...")
                self._download_model()
            
            if model_path.exists():
                print("[WakeDetector] Loading Vosk model...")
                self._model = Model(str(model_path))
                
                # Grammar-restricted recognizer - ONLY recognizes "jarvis"
                self._recognizer = KaldiRecognizer(self._model, 16000, self.WAKE_GRAMMAR)
                self._recognizer.SetWords(True)
                
                print("[WakeDetector] Vosk initialized with grammar: [jarvis]")
            else:
                print("[WakeDetector] ERROR: Model not available")
                
        except ImportError:
            print("[WakeDetector] ERROR: vosk not installed. Run: pip install vosk")
        except Exception as e:
            print(f"[WakeDetector] ERROR: {e}")
    
    def _download_model(self):
        """Download Vosk model (~50MB)."""
        import urllib.request
        import zipfile
        
        MODEL_DIR.mkdir(parents=True, exist_ok=True)
        zip_path = MODEL_DIR / f"{MODEL_NAME}.zip"
        
        try:
            print(f"[WakeDetector] Downloading Vosk model (~50MB)...")
            print(f"[WakeDetector] This is a one-time download.")
            
            urllib.request.urlretrieve(MODEL_URL, zip_path)
            
            print("[WakeDetector] Extracting model...")
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(MODEL_DIR)
            
            zip_path.unlink()
            print("[WakeDetector] Model ready!")
            
        except Exception as e:
            print(f"[WakeDetector] ERROR downloading model: {e}")
    
    def start(self):
        """Start listening for wake word."""
        if not self._recognizer:
            print("[WakeDetector] Cannot start - model not loaded")
            return
        
        self.is_listening = True
        self._stop_event.clear()
        
        self._listen_thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._listen_thread.start()
        
        print("[WakeDetector] Listening for 'Jarvis'...")
    
    def _listen_loop(self):
        """Main listening loop - grammar restricted to wake word only."""
        try:
            import sounddevice as sd
            import numpy as np
            
            def audio_callback(indata, frames, time_info, status):
                if not self._stop_event.is_set():
                    self._audio_queue.put(bytes(indata))
            
            # Open audio stream
            with sd.RawInputStream(
                samplerate=16000,
                blocksize=4000,  # 250ms chunks for low latency
                dtype='int16',
                channels=1,
                callback=audio_callback
            ):
                while not self._stop_event.is_set():
                    try:
                        data = self._audio_queue.get(timeout=0.5)
                        
                        if self._recognizer.AcceptWaveform(data):
                            result = json.loads(self._recognizer.Result())
                            text = result.get("text", "").lower().strip()
                            
                            # Check for wake word
                            if text == "jarvis":
                                # ASCII-only: found live that a Unicode
                                # checkmark here raises UnicodeEncodeError
                                # on a cp1252 Windows console -- caught by
                                # the broad except below and silently
                                # swallowed, so detection succeeded but
                                # this print's crash meant self.callback()
                                # on the next line never ran. Root cause
                                # of the reported "wake word doesn't
                                # work" -- see jarvis.py's stdout
                                # reconfigure for the other half of this
                                # fix (this module has callers, e.g.
                                # WakeService/jarvis_service.py, that
                                # don't go through jarvis.py's entry
                                # point and so don't get that fix).
                                if self._try_fire():
                                    print("[WakeDetector] Wake word detected!")
                        else:
                            # Partial result - check for early detection
                            partial = json.loads(self._recognizer.PartialResult())
                            partial_text = partial.get("partial", "").lower().strip()

                            if partial_text == "jarvis":
                                if self._try_fire():
                                    print("[WakeDetector] Wake word detected (partial)!")
                                # Reset recognizer after detection (or after
                                # a within-cooldown repeat of the same
                                # stabilized partial) so the next chunk
                                # starts a fresh utterance either way.
                                self._recognizer.Reset()
                                
                    except queue.Empty:
                        continue
                    except Exception as e:
                        print(f"[WakeDetector] Audio error: {e}")
                        time.sleep(0.5)
                        
        except Exception as e:
            print(f"[WakeDetector] Stream error: {e}")
    
    def stop(self):
        """Stop listening."""
        self.is_listening = False
        self._stop_event.set()
        
        # Clear queue
        while not self._audio_queue.empty():
            try:
                self._audio_queue.get_nowait()
            except:
                break
        
        print("[WakeDetector] Stopped")
    
    def reset(self):
        """Reset recognizer state for clean restart."""
        if self._recognizer:
            self._recognizer.Reset()
    
    def __del__(self):
        self.stop()


def test_wake_detector():
    """Test wake word detection."""
    print("=" * 50)
    print("Vosk Wake Word Detection Test")
    print("Say 'Jarvis' to trigger...")
    print("(Press Ctrl+C to stop)")
    print("=" * 50)
    
    detected = threading.Event()
    
    def on_wake():
        print("\nWAKE WORD DETECTED!")
        detected.set()
    
    detector = WakeDetector(callback=on_wake)
    detector.start()
    
    try:
        while not detected.wait(timeout=1):
            pass
        print("Test PASSED!")
    except KeyboardInterrupt:
        print("\nTest interrupted")
    finally:
        detector.stop()


if __name__ == "__main__":
    test_wake_detector()
