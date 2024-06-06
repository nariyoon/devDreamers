import cv2
import os
import glob
from detect_square import *
from matching_digit import *
from common import *


if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.realpath(__file__))
    image_dir = f"{script_dir}/dataset/NewTrainingRaw/images"
    image_files = sorted(glob.glob(f"{image_dir}/*.jpg"))
    print(f"image_files length {len(image_files)}")
    
    ref_image_dir = f"{script_dir}/../Targets/"
    num_signs = 10  # Define the number of reference images
    symbols = load_ref_images(ref_image_dir, num_signs)
    
    frame_cnt = 0

    while True:
        if frame_cnt >= len(image_files):
            break
        frame_0 = cv2.imread(image_files[frame_cnt])
        if frame_0 is None or frame_0.size == 0:
            print(f"Failed to load {image_files[frame_cnt]}, frame_cnt: {frame_cnt}")
            frame_cnt += 1
            continue

        # 여기서 사각형을 찾는다.
        squares = find_squares(frame_0)

        '''
            1. matching default
        '''
        matched_squares = match_digits(frame_0, squares, symbols)


        '''
            2. opencv api
        '''

        '''
            3. tflite
        '''

        # 찾은 사각형을 그린다.
        draw_squares(frame_0, matched_squares)

        # 이미지 표시
        screen_res = 1920, 1080
        scale_width = screen_res[0] / frame_0.shape[1]
        scale_height = screen_res[1] / frame_0.shape[0]
        scale = min(scale_width, scale_height)
        window_width = int(frame_0.shape[1] * scale)
        window_height = int(frame_0.shape[0] * scale)

        cv2.namedWindow('IMAGE', cv2.WINDOW_NORMAL)
        cv2.resizeWindow('IMAGE', window_width, window_height)
        cv2.imshow('IMAGE', frame_0)
        
        key = cv2.waitKey(0)  # waitKey(0) to wait for key press
        if key & 0xFF == ord('q'):
            break
        elif key & 0xFF == ord('n'):
            frame_cnt += 1
        elif key & 0xFF == ord('b'):
            frame_cnt = max(0, frame_cnt - 1)  # prevent negative index

    cv2.destroyAllWindows()