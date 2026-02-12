import pywinauto
from PIL import Image
import mss
import mss.tools
from typing import Optional, Tuple
import os

class ScreenCapture:
    """Handles screen captures for UI vision."""
    
    def __init__(self):
        self.sct = mss.mss()
    
    def capture(self, region: Optional[Tuple[int, int, int, int]] = None) -> Image.Image:
        """
        Capture a region of the screen.
        region: (x, y, width, height)
        """
        if region:
            monitor = {"top": region[1], "left": region[0], "width": region[2], "height": region[3]}
        else:
            # Capture primary monitor
            monitor = self.sct.monitors[1]
            
        sct_img = self.sct.grab(monitor)
        return Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")

    def capture_window(self, hwnd: int) -> Image.Image:
        """Capture a specific window by its handle."""
        from pywinauto import Desktop
        try:
            app = pywinauto.Desktop(backend="uia").window(handle=hwnd)
            return app.capture_as_image()
        except Exception as e:
            print(f"[ScreenCapture] Error capturing window {hwnd}: {e}")
            return None

if __name__ == "__main__":
    import sys
    if "--once" in sys.argv:
        cap = ScreenCapture()
        img = cap.capture()
        os.makedirs("data/screenshots", exist_ok=True)
        path = "data/screenshots/validation_test.png"
        img.save(path)
        print(f"Screenshot saved to {path}")
