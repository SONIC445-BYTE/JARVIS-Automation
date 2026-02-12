import speech_recognition as sr

def test_sr():
    r = sr.Recognizer()
    print("Testing SpeechRecognition...")
    print("Available Microphones:", sr.Microphone.list_microphone_names())
    
    with sr.Microphone() as source:
        print("Adjusting for ambient noise...")
        r.adjust_for_ambient_noise(source)
        print("Say something (5s limit)...")
        try:
            audio = r.listen(source, timeout=5, phrase_time_limit=5)
            print("Recognizing...")
            text = r.recognize_google(audio)
            print(f"Success! You said: {text}")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    test_sr()
