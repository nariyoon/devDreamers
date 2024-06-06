import cv2
import numpy as np

import cv2
import numpy as np

def find_squares(image):
    squares = []

    # down-scale and upscale the image to filter out the noise
    pyr = cv2.pyrDown(image)
    timg = cv2.pyrUp(pyr)

    for c in range(3):  # 각 색상 채널에 대해 사각형을 검출
        gray0 = cv2.split(timg)[c]

        for l in range(2):  # 여러 임계값 레벨을 시도
            if l == 0:
                gray = cv2.Canny(gray0, 0, 50, apertureSize=5)
                gray = cv2.dilate(gray, None)
            else:
                retval, gray = cv2.threshold(gray0, (l + 1) * 255 / 2, 255, cv2.THRESH_BINARY)

            contours, _ = cv2.findContours(gray, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
            for contour in contours:
                contour_length = cv2.arcLength(contour, True)
                approx = cv2.approxPolyDP(contour, 0.02 * contour_length, True)
                area = cv2.contourArea(contour)

                if len(approx) == 4 and cv2.isContourConvex(approx) and area > 1000:  # 면적 조건 추가
                    max_cosine = 0
                    for j in range(2, 5):
                        cosine = abs(angle(approx[j % 4][0], approx[j - 2][0], approx[j - 1][0]))
                        max_cosine = max(max_cosine, cosine)
                    if max_cosine < 0.3:
                        approx = approx.reshape(-1, 2)
                        squares.append(approx)

    # 중복된 사각형 제거
    unique_squares = []
    for sq in squares:
        center = np.mean(sq, axis=0)
        if not any(np.linalg.norm(center - np.mean(uq, axis=0)) < 10 for uq in unique_squares):
            unique_squares.append(sq)

    # 정사각형 조건 강화
    final_squares = []
    for sq in unique_squares:
        side_lengths = [np.linalg.norm(sq[i] - sq[(i + 1) % 4]) for i in range(4)]
        if max(side_lengths) / min(side_lengths) < 1.2:  # 변의 길이가 비슷한 사각형만
            final_squares.append(sq)

    return final_squares

def angle(pt1, pt2, pt0):
    dx1 = pt1[0] - pt0[0]
    dy1 = pt1[1] - pt0[1]
    dx2 = pt2[0] - pt0[0]
    dy2 = pt2[1] - pt0[1]
    return (dx1 * dx2 + dy1 * dy2) / np.sqrt((dx1**2 + dy1**2) * (dx2**2 + dy2**2) + 1e-10)

