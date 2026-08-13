"""
Local Speech-to-Text - Vosk Offline Engine
============================================
Full speech recognition for active mode.

Runs locally, no API calls.
"""

import os
import json
import queue
import threading
from typing import Optional, Callable
from pathlib import Path


class LocalSTT:
    """
    Local speech-to-text using Vosk.
    
    - Offline: No internet required
    - Fast: <500ms latency
    - Accurate: Works well for commands
    """
    
    # Model will be downloaded to this directory
    MODEL_DIR = Path(__file__).parent / "models"
    # Swapped from vosk-model-small-en-us-0.15 (40MB, WER 9.85 on
    # librispeech test-clean) to vosk-model-en-us-0.22 (1.8GB, WER 5.69) --
    # measured directly, not assumed: on a 6-phrase set including the exact
    # commands reported failing live ("open notepad", "open spotify"), the
    # small model mis-transcribed "open spotify" as "open spot if i" and
    # "open whatsapp" as "open what's app" (neither would match any
    # platform alias); the large model got both exactly right, 5/6 exact
    # matches vs 3/6 for small (6/6 vs 4/6 case-insensitive -- the one
    # remaining "mismatch" for both models was a capitalization difference,
    # not a transcription error). Real cost: ~35s to load (vs ~1-2s for the
    # small model) and ~2.7GB on disk (vs ~70MB) -- see the execution log's
    # STT accuracy entry for the full measurement and the lighter-weight
    # vosk-model-en-us-0.22-lgraph (128MB) alternative if that load time
    # proves too costly. WakeService/wake_detector.py's grammar-restricted
    # ["jarvis"]-only wake-word detector deliberately stays on the small
    # model -- a different, continuously-running, latency-sensitive task
    # not implicated in the reported command-misrecognition failures.
    MODEL_NAME = "vosk-model-en-us-0.22"
    MODEL_URL = "https://alphacephei.com/vosk/models/vosk-model-en-us-0.22.zip"
    
    def __init__(self, on_result: Optional[Callable[[str], None]] = None):
        """
        Initialize local STT.
        
        Args:
            on_result: Callback when speech recognized
        """
        self.on_result = on_result
        self.is_listening = False
        self._stop_event = threading.Event()
        self._model = None
        self._recognizer = None
        self._audio_queue = queue.Queue()
        
        self._initialize()
    
    def _initialize(self):
        """Initialize Vosk model."""
        try:
            from vosk import Model, KaldiRecognizer
            
            model_path = self.MODEL_DIR / self.MODEL_NAME
            
            if not model_path.exists():
                print(f"DEBUG LocalSTT: Model not found, downloading...")
                self._download_model()
            
            if model_path.exists():
                self._model = Model(str(model_path))
                self._recognizer = KaldiRecognizer(self._model, 16000)
                print("DEBUG LocalSTT: Vosk model loaded successfully")
            else:
                print("WARNING LocalSTT: Model not available")
                
        except ImportError:
            print("WARNING LocalSTT: Vosk not installed")
        except Exception as e:
            print(f"ERROR LocalSTT: {e}")
    
    def _download_model(self):
        """Download Vosk model if not present."""
        import urllib.request
        import zipfile
        
        self.MODEL_DIR.mkdir(parents=True, exist_ok=True)
        zip_path = self.MODEL_DIR / f"{self.MODEL_NAME}.zip"
        
        try:
            print(f"Downloading Vosk model (~1.8GB, this will take a while)...")
            urllib.request.urlretrieve(self.MODEL_URL, zip_path)
            
            print("Extracting model...")
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(self.MODEL_DIR)
            
            zip_path.unlink()  # Remove zip
            print("Model ready!")
            
        except Exception as e:
            print(f"ERROR downloading model: {e}")
    
    def listen_once(self, timeout: float = 5.0) -> Optional[str]:
        """
        Listen for a single phrase using the local Vosk recognizer.
        """
        if not self._recognizer:
            return None
        
        try:
            import sounddevice as sd
            import numpy as np

            def callback(indata, frames, time_info, status):
                if self._stop_event.is_set():
                    return
                audio_bytes = (indata[:, 0] * 32768).astype(np.int16).tobytes()
                self._audio_queue.put(audio_bytes)
            
            with sd.InputStream(
                samplerate=16000,
                blocksize=8000,
                channels=1,
                dtype=np.float32,
                callback=callback
            ):
                start_time = __import__('time').time()
                
                while __import__('time').time() - start_time < timeout:
                    if self._stop_event.is_set():
                        break
                        
                    try:
                        audio = self._audio_queue.get(timeout=0.1)
                        if self._recognizer.AcceptWaveform(audio):
                            result = json.loads(self._recognizer.Result())
                            if result.get("text"):
                                return result["text"]
                    except queue.Empty:
                        continue
                
                # Get final result
                result = json.loads(self._recognizer.FinalResult())
                return result.get("text") or None
                
        except Exception as e:
            print(f"ERROR LocalSTT: {e}")
            return None

    def start_continuous(self, on_speech: Callable[[str], None]):
        """
        Start continuous speech recognition.
        
        Args:
            on_speech: Called with each recognized phrase
        """
        self.is_listening = True
        self._stop_event.clear()
        
        def listen_loop():
            while not self._stop_event.is_set():
                text = self.listen_once(timeout=10)
                if text and on_speech:
                    on_speech(text)
        
        self._listen_thread = threading.Thread(target=listen_loop, daemon=True)
        self._listen_thread.start()
    
    def stop(self):
        """Stop listening."""
        self.is_listening = False
        self._stop_event.set()


def test_local_stt():
    """Test local speech-to-text."""
    print("=" * 50)
    print("Local STT Test")
    print("Speak a command...")
    print("=" * 50)
    
    stt = LocalSTT()
    text = stt.listen_once(timeout=10)
    
    if text:
        print(f"✓ Recognized: '{text}'")
    else:
        print("✗ No speech detected")


if __name__ == "__main__":
    test_local_stt()
