import cv2
import pytesseract
import numpy as np
import base64

# Configure Tesseract path if necessary
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

def solve_captcha(base64_data):
    """
    Processes a base64 encoded CAPTCHA image and returns the solved text.
    """
    try:
        # Extract base64 payload if data URL is present
        if 'base64,' in base64_data:
            base64_data = base64_data.split('base64,', 1)[-1]
        
        # Decode base64 string to bytes
        img_bytes = base64.b64decode(base64_data)
    except Exception as e:
        raise ValueError(f"Base64 decoding failed: {e}")

    # Convert bytes to OpenCV image
    np_array = np.frombuffer(img_bytes, np.uint8)
    img = cv2.imdecode(np_array, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Failed to decode image from base64 data")

    # Image processing pipeline
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    kernel = np.ones((2, 2), np.uint8)
    cleaned = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel, iterations=1)

    # Configure Tesseract for CAPTCHA text extraction
    config = r'--oem 3 --psm 8 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*()=,.?'
    text = pytesseract.image_to_string(cleaned, config=config).strip()

    return text

if __name__ == "__main__":
    import sys
    # Test mode: accept local image file path
    test_image = sys.argv[1] if len(sys.argv) > 1 else "captcha.png"
    try:
        with open(test_image, "rb") as f:
            test_data = base64.b64encode(f.read()).decode('utf-8')
        print("CAPTCHA text:", solve_captcha(test_data))
    except Exception as e:
        print(f"Error processing {test_image}: {e}")