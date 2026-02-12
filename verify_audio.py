import pyttsx3
import time

def verify_audio():
    try:
        print("Initializing PyTTSx3...")
        engine = pyttsx3.init()
        print("Testing speech...")
        engine.say("Audio check one two three")
        engine.runAndWait()
        print("Speech verification successful.")
    except Exception as e:
        print(f"Audio verification failed: {e}")

if __name__ == "__main__":
    verify_audio()
