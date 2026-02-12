import pyttsx3
import os

def test_tts():
    print("Initializing pyttsx3...")
    engine = pyttsx3.init()
    text = "Hello, I am testing the offline text to speech engine."
    outfile = "test_speech.wav"
    
    print(f"Saving '{text}' to {outfile}...")
    engine.save_to_file(text, outfile)
    engine.runAndWait()
    
    if os.path.exists(outfile):
        print(f"Success! {outfile} created. Size: {os.path.getsize(outfile)} bytes")
        # clean up
        # os.remove(outfile)
    else:
        print("Failed to create audio file.")

if __name__ == "__main__":
    test_tts()
