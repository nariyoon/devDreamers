import cv2
import numpy as np


def load_ref_images(image_dir, num_signs, scale=0.50):
    symbols = []
    for i in range(num_signs):
        filename = f"{image_dir}/T{i}.jpg"
        img = cv2.imread(filename, cv2.IMREAD_GRAYSCALE)
        if img is None:
            # print(f"Failed to load {filename}")
            continue
        img = cv2.resize(img, (0, 0), fx=scale, fy=scale)
        # _, img = cv2.threshold(img, 100, 255, cv2.THRESH_BINARY)
        symbols.append({"img": img, "name": str(i)})
    return symbols


def match_digits(image, squares, ref_images):
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
            label = f"{recognized_digit}"
            matched_squares.append(([(x, y), (x+w, y+h)], label))

    # print("\n")
    # draw_squares(draw_image, matched_squares)
    return matched_squares


def angle(pt1, pt2, pt0):
    dx1, dy1 = pt1[0] - pt0[0], pt1[1] - pt0[1]
    dx2, dy2 = pt2[0] - pt0[0], pt2[1] - pt0[1]
    dot_product = dx1 * dx2 + dy1 * dy2
    norm1 = dx1**2 + dy1**2
    norm2 = dx2**2 + dy2**2
    norm_product = np.sqrt(norm1 * norm2 + 1e-10)  # Avoid division by zero
    return dot_product / norm_product

def find_squares(image):
    squares = []

    # down-scale and upscale the image to filter out the noise
    pyr = cv2.pyrDown(image)
    timg = cv2.pyrUp(pyr)

    channels = cv2.split(timg)
    for c in range(3):  # 각 색상 채널에 대해 사각형을 검출
        gray0 = channels[c]

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

                # 면적 조건 추가 (1000 < area < 11000)
                if len(approx) == 4 and cv2.isContourConvex(approx) and 1000 < area < 11000:
                    max_cosine = 0
                    for j in range(2, 5):
                        cosine = abs(angle(approx[j % 4][0], approx[j - 2][0], approx[j - 1][0]))
                        max_cosine = max(max_cosine, cosine)
                    if max_cosine < 0.3:
                        squares.append(approx.reshape(-1, 2))

    # 중복된 사각형 제거
    centers = [np.mean(sq, axis=0) for sq in squares]
    unique_squares = []
    added_centers = []

    for i, sq in enumerate(squares):
        center = centers[i]
        if not any(np.linalg.norm(center - ac) < 10 for ac in added_centers):
            unique_squares.append(sq)
            added_centers.append(center)

    # 정사각형 조건 강화
    final_squares = []
    for sq in unique_squares:
        side_lengths = [np.linalg.norm(sq[i] - sq[(i + 1) % 4]) for i in range(4)]
        if max(side_lengths) / min(side_lengths) < 1.2:  # 변의 길이가 비슷한 사각형만
            final_squares.append(sq)

    return final_squares
