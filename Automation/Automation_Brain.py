from Automation.open_App import open_App
from Automation.Web_Open import openweb
from Automation.Web_Data import websites
import pyautogui as gui
from Automation.Play_Music_YT import play_music_on_youtube
from TextToSpeech import Fast_DF_TTS
from Automation.playmusic_Sfy import play_music_on_spotify
from Automation.Battery import check_percentage
from os import getcwd
import time
from Automation.tab_automation import perform_browser_action
from Automation.Youtube_play_back import perform_media_action
import pywhatkit
from Automation.scrool_system import perform_scroll_action
import threading
from TextToSpeech.Fast_DF_TTS import speak

_ui_agent = None


def _get_ui_agent():
    """Lazily constructs UIAgentMain, imported here (not at module level)
    since AgentCore.ui_agent's transitive import chain reaches
    AgentCore/ui_agent/vision/screen_capture.py's `import mss` --  mss
    opens a real X11 connection at import time on Linux, which broke
    importing this module (and anything that imports it, e.g. jarvis.py
    via co_brain.py) in headless/CI environments. Also confirmed dead
    for real execution (Phase 2c-prime: ODAVLoop bypasses ui_agent
    entirely) -- the only call site below already wraps this in a broad
    try/except that treats any failure as "fall through to Legacy
    Fallback", so a lazily-failing import is exactly as safe as the
    runtime call it already tolerated. Constructed once and reused, same
    as the original eager module-level instance, just deferred to first
    actual use instead of paid on import."""
    global _ui_agent
    if _ui_agent is None:
        from AgentCore.ui_agent.ui_agent_main import UIAgentMain
        _ui_agent = UIAgentMain()
    return _ui_agent

def play():
    gui.press("space")
    
def search_google(text):
    pywhatkit.search(text)

def close(app_name=None):
    """Close an application or browser tab by name."""
    import subprocess
    from Automation.Web_Data import websites
    from TextToSpeech.Fast_DF_TTS import speak
    
    print(f"DEBUG close received: '{app_name}'")
    
    if app_name:
        app_name = app_name.strip().lower()
        
        # Check if it's a website (should close browser tab)
        is_website = app_name in websites or app_name in ["youtube", "insta", "instagram", "facebook", "fb", "twitter", "x", "ig", "yt"]
        
        if is_website:
            # For websites, close the current browser tab with Ctrl+W
            print(f"DEBUG: Closing browser tab for '{app_name}'")
            speak(f"Closing {app_name}")
            time.sleep(0.3)
            gui.hotkey('ctrl', 'w')
            print(f"DEBUG: Sent Ctrl+W to close tab")
        else:
            # For desktop applications, use taskkill
            process_map = {
                "chrome": "chrome.exe",
                "firefox": "firefox.exe",
                "edge": "msedge.exe",
                "notepad": "notepad.exe",
                "spotify": "Spotify.exe",
                "discord": "Discord.exe",
                "whatsapp": "WhatsApp.exe",
                "vscode": "Code.exe",
                "code": "Code.exe", 
            }
            process_name = process_map.get(app_name, f"{app_name}.exe")
            try:
                subprocess.run(["taskkill", "/f", "/im", process_name], check=True, capture_output=True)
                speak(f"Closed {app_name}")
                print(f"DEBUG: Closed {app_name} using taskkill")
            except subprocess.CalledProcessError:
                print(f"DEBUG: Could not close {app_name}, trying Alt+F4")
                gui.hotkey('alt', 'f4')
    else:
        # No app specified - close current window
        gui.hotkey('alt', 'f4')
    
def search(text):
    gui.press("/")
    time.sleep(0.3)
    gui.write(text)

def Open_Brain(text):
    print(f"DEBUG Open_Brain received: '{text}'")
    if "website" in text or "open website named" in text:
        text = text.replace("open","").strip()
        text = text.replace("website","").strip()
        text = text.replace("open website named","").strip()
        t1 = threading.Thread(target=speak,args=(f"Navigating {text} website",))
        t2 = threading.Thread(target=openweb,args=(text,))
        t1.start()
        t2.start()
        t1.join()
        t2.join()
    else:
        text = text.replace("open","").strip()
        text = text.replace("app","").strip()
        
        # Check if the text matches a known website
        is_website = False
        for site in websites:
            if site in text:
                is_website = True
                break
        
        if is_website:
            t1 = threading.Thread(target=speak,args=(f"Navigating {text} website",))
            t2 = threading.Thread(target=openweb,args=(text,))
            t1.start()
            t2.start()
            t1.join()
            t2.join()
        else:
            t1 = threading.Thread(target=speak,args=(f"Navigating {text} application",))
            t2 = threading.Thread(target=open_App,args=(text,))
            t1.start()
            t2.start()
            t1.join()
            t2.join()
        
def clear_file():
    with open(f"{getcwd()}\\input.txt","w") as file:
        file.truncate(0)

def Auto_main_brain(text):
   try:
    print(f"DEBUG Auto_main_brain received: '{text}'")
    
    # --- Authoritative Planning Layer ---
    # Convert text to intent (simplified for now)
    intent = {"action": "unknown", "platform": None, "raw": text}
    if "whatsapp" in text.lower():
        intent = {"action": "send_message", "platform": "whatsapp", "recipient": "someone", "message": text}
    elif "explorer" in text.lower() or "open c" in text.lower():
        intent = {"action": "navigate_to", "platform": "explorer", "path": "C:\\"}
    elif "open" in text.lower():
        # Fallback to legacy Open_Brain if no specific platform adapter
        app_name = text.replace("open", "").strip()
        intent = {"action": "open", "platform": app_name}

    # Use UIAgent as the broker for planning
    try:
        # execute_instruction handles vision fallback internally
        result = _get_ui_agent().execute_instruction(text, dry_run=True)
        if result.success and result.steps:
            print(f"[AutoBrain] Task handled via Unified Planner: {text}")
            return
    except Exception as e:
        print(f"[AutoBrain] Planning bypass: {e}")

    # --- Legacy Fallback (only if Planner fails or no adapter) ---
    if "open" in text:
        Open_Brain(text)
    elif "close" in text:
        app_name = text.replace("close", "").strip()
        close(app_name if app_name else None)
    # ... other legacy blocks could remain for now but are prioritized less ...
        
   except Exception as e:
       print("error : " + str(e))