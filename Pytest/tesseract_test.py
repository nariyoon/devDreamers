# tesseract_test.py
import cv2
import pytesseract
import time

class Pytesseract:
    def __init__(self):
        pass

    def detect(self, image, draw_image, squares):
        start_time = time.time()
        recognized_digits = []
        for sq in squares:
            x, y, w, h = cv2.boundingRect(sq)
            roi = image[y:y+h, x:x+w]
            roi_gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            roi_gray = cv2.resize(roi_gray, (28, 28))
            _, roi_gray = cv2.threshold(roi_gray, 100, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            text = pytesseract.image_to_string(roi_gray, config='--psm 10 -c tessedit_char_whitelist=0123456789')
            recognized_digit = text.strip()
            if recognized_digit.isdigit():                
                recognized_digits.append(([(x, y), (x + w, y + h)], recognized_digit))
                label = f"Digit: {recognized_digit}"
                cv2.putText(draw_image, label, (x, y - 90), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)
        end_time = time.time()
        return recognized_digits, (end_time - start_time)
