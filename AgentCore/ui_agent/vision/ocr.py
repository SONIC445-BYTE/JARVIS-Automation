from dataclasses import dataclass
from typing import List, Tuple, Dict, Any
import pytesseract
from PIL import Image

@dataclass
class TextBlock:
    text: str
    bbox: Tuple[int, int, int, int] # x, y, w, h
    confidence: float

class OCRWrapper:
    """Wrapper for OCR capabilities."""
    
    def __init__(self):
        # Tesseract path should be in system PATH or configured
        pass
        
    def extract_text(self, image: Image.Image) -> List[TextBlock]:
        """Extract text blocks from image."""
        try:
            data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
            blocks = []
            
            n_boxes = len(data['text'])
            for i in range(n_boxes):
                if int(data['conf'][i]) > 0: # Filter low confidence
                    blocks.append(TextBlock(
                        text=data['text'][i],
                        bbox=(data['left'][i], data['top'][i], data['width'][i], data['height'][i]),
                        confidence=float(data['conf'][i])
                    ))
            return blocks
        except Exception as e:
            print(f"[OCR] Error: {e}")
            return []

if __name__ == "__main__":
    import sys
    if "--test" in sys.argv:
        from .screen_capture import ScreenCapture
        cap = ScreenCapture()
        img = cap.capture()
        ocr = OCRWrapper()
        blocks = ocr.extract_text(img)
        print(f"Detected {len(blocks)} text blocks.")
        for b in blocks[:5]:
             print(f" - [{b.confidence:.2f}] '{b.text}' at {b.bbox}")
        if any(b.bbox == (0,0,0,0) or b.bbox is None for b in blocks):
             print("🚨 RED FLAG: Found null bounding boxes")
        else:
             print("✅ No null bounding boxes")
