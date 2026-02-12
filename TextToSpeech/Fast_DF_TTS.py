import pyttsx3 # pip install pyttsx3
import pygame # pip install pygame
import os
from typing import Union # pip install typing
import sys
import time
import threading

# Initialize pyttsx3 engine locally inside Co_speak
# engine = pyttsx3.init()
# voices = engine.getProperty('voices')
# Set to a female voice if available, or just default
# engine.setProperty('voice', voices[1].id) # Index 1 is usually female (Zira) on Windows

def print_animated_message(message):
    try:
        for char in message:
            sys.stdout.write(char)
            sys.stdout.flush()
            time.sleep(0.050)  # Adjust the sleep duration for the animation speed
        print()
    except Exception:
        print(message)

def Co_speak(message: str, voice: str = "Matthew", folder: str = "", extension: str = ".wav") -> Union[None,str]:
    try:
        # Initializing pyttsx3 engine locally for thread safety
        engine = pyttsx3.init()
        voices = engine.getProperty('voices')
        # engine.setProperty('voice', voices[1].id) # Uncomment if female voice needed
        
        # Generate unique filename to avoid conflicts or caching issues
        # Using .wav for better compatibility with pyttsx3 save_to_file on Windows
        filename = f"speech_{int(time.time())}.wav"
        file_path = os.path.join(folder, filename)
        
        # Save audio to file using pyttsx3
        # We need to run the engine loop. Since this is called from a thread, verify loop safety.
        # pyttsx3 is generally synchronous with save_to_file + runAndWait
        engine.save_to_file(message, file_path)
        engine.runAndWait() 
        
        if not os.path.exists(file_path):
            print("Error: Audio file was not created by pyttsx3")
            return None

        # Play audio using pygame
        pygame.mixer.init()
        pygame.mixer.music.load(file_path)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(10)
        pygame.mixer.music.unload()
        pygame.mixer.quit()

        try:
            os.remove(file_path)
        except PermissionError:
            pass # Sometimes file is still locked, ignore
        return None
    except Exception as e:
        print(f"TTS Error: {e}")

def speak(text):
    t1 = threading.Thread(target=Co_speak,args=(text,))
    t2 = threading.Thread(target=print_animated_message,args=(text,))
    t1.start()
    t2.start()
    t1.join()
    t2.join()


#c