import cv2
import numpy as np

def match_digits(image, squares, ref_images):
    matched_squares = []

    for sq in squares:
        x, y, w, h = cv2.boundingRect(sq)
        roi = image[y:y+h, x:x+w]
        roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        _, roi = cv2.threshold(roi, 100, 255, cv2.THRESH_BINARY)
        roi = cv2.resize(roi, (ref_images[0]['img'].shape[1], ref_images[0]['img'].shape[0]))

        min_diff = float('inf')
        recognized_digit = None
        for ref_image in ref_images:
            diff = cv2.absdiff(roi, ref_image['img'])
            non_zero_count = np.count_nonzero(diff)
            if non_zero_count < min_diff:
                min_diff = non_zero_count
                recognized_digit = ref_image['name']

        print(f"Recognized digit: {recognized_digit}")
        
        # 사각형 그리기
        cv2.polylines(image, [sq], True, (0, 0, 255), 3)
        
        # 숫자 추가
        if recognized_digit is not None:
            label = f"Digit: {recognized_digit}"
            label_size, baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
            cv2.rectangle(image, (x, y - label_size[1] - 10), (x + label_size[0], y), (0, 0, 255), cv2.FILLED)
            cv2.putText(image, label, (x, y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

        matched_squares.append((sq, recognized_digit))  # 사각형과 인식된 숫자 저장

    return matched_squares
