import importlib
import sys

packages = [
    'requests',
    'winotify',
    'pyautogui',
    'pywhatkit',
    'pygame',
    'psutil',
    'selenium',
    'webdriver_manager',
    'webscout',
    'lxml.html.clean',
    'gradio_client',
    'colorlog',
    'yaspin',
    'cv2',
    'pyaudio',
    'scipy',
    'wmi',
    'comtypes',
    'pycaw'
]

failed = []
for package in packages:
    try:
        importlib.import_module(package)
        print(f"Successfully imported {package}")
    except ImportError as e:
        print(f"Failed to import {package}: {e}")
        failed.append(package)

if failed:
    print(f"Failed to verify {len(failed)} packages: {', '.join(failed)}")
    sys.exit(1)
else:
    print("All packages verified successfully!")
