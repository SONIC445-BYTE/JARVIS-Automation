
import subprocess
import time

def test_open():
    print("Testing open chrome directly...")
    try:
        subprocess.Popen("start chrome", shell=True)
        print("Success: Launch command sent.")
    except Exception as e:
        print(f"Failed: {e}")

if __name__ == "__main__":
    test_open()
