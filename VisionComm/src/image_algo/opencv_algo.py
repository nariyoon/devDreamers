import cv2
import numpy as np


'''
Not Used
'''

def draw_squares(img, squares):
    for square, digit in squares:
        cv2.polylines(img, [square], True, (0, 0, 255), 3)
        # x, y = np.mean(square, axis=0).astype(int)
        # cv2.putText(img, digit, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

def match_digits(image, draw_image, squares, ref_images):
    matched_squares = []

    for sq in squares:
        x, y, w, h = cv2.boundingRect(sq)
        roi = image[y:y+h, x:x+w]
        roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        _, roi = cv2.threshold(roi, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)  # Otsu's Binarization 적용
        roi = cv2.resize(roi, (ref_images[0]['img'].shape[1], ref_images[0]['img'].shape[0]))

        min_diff = float('inf')
        recognized_digit = None
        best_match_img = None

        for ref_image in ref_images:
            diff = cv2.absdiff(roi, ref_image['img'])
            non_zero_count = np.count_nonzero(diff)
            if non_zero_count < min_diff:
                min_diff = non_zero_count
                recognized_digit = ref_image['name']
                best_match_img = ref_image['img']

        # # 매칭된 순간에만 비교 이미지를 표시
        # if best_match_img is not None:
        #     cv2.imshow(f"ROI vs {recognized_digit}", np.hstack((roi, best_match_img)))
        #     cv2.waitKey(0)  # 키 입력을 대기

        # print(f"Recognized digit: {recognized_digit} with min_diff: {min_diff}")
        
        # 사각형 그리기
        # cv2.polylines(draw_image, [sq], True, (0, 0, 255), 3)
        
        # 숫자 추가
        if recognized_digit is not None:
            label = f"Digit: {recognized_digit}"
            # label_size, baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
            # cv2.rectangle(draw_image, (x, y - label_size[1] - 10), (x + label_size[0], y), (0, 0, 255), cv2.FILLED)
            # cv2.putText(draw_image, label, (x, y - 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

        matched_squares.append((sq, recognized_digit))  # 사각형과 인식된 숫자 저장

    # print("\n")
    # draw_squares(draw_image, matched_squares)
    return matched_squares
