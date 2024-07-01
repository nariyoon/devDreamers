import os
import sys
import threading
import time
import cv2
import struct
from image_algo.yolov8_algo import YOLO_Detector
from image_algo.tflite_algo import ObjectDetector
from image_algo.opencv_algo import *
from ultralytics import YOLO
import numpy as np
import os
from datetime import datetime
from filterpy.kalman import KalmanFilter
import copy
import torch

from cannon_queue import *

# Add the parent directory of `image_algo` to sys.path
script_dir = os.path.dirname(os.path.realpath(__file__))
parent_dir = os.path.abspath(os.path.join(script_dir, '..'))
sys.path.append(parent_dir)

CAP_PROP_FRAME_WIDTH = 960
CAP_PROP_FRAME_HEIGHT = 544
INIT_TIME = 5
QUEUE_MAX_SIZE = 10  # 큐의 최대 크기 설정

class YOLOAlgorithm:
    def __init__(self, model_path):
        self.detector = YOLO_Detector(model_path)
        self.model_name = "YOLOv8"

    def detect(self, frame):
        return self.detector.detect(frame)

    def get_name(self):
        return self.model_name

class TFLiteAlgorithm:
    def __init__(self, model_path):
        self.detector = ObjectDetector(model_path)
        self.model_name = "TFLite"

    def detect(self, frame):
        return self.detector.detect(frame)
    
    def get_name(self):
        return self.model_name

class OpenCVDefaultAlgorithm():
    def __init__(self, symbols):
        self.symbols = symbols
        self.model_name = "OpenCV"

    def detect(self, image):
        squares = find_squares(image)
        result = match_digits(image, squares, self.symbols)
        return result
    
    def get_name(self):
        return self.model_name

def apply_custom_sharpening_filter(image):
    kernel = np.array([[0, -0.5, 0],
                       [-0.5, 3, -0.5],
                       [0, -0.5, 0]])
    sharpened_image = cv2.filter2D(image, -1, kernel)
    return sharpened_image

def apply_laplacian_sharpening(image):
    laplacian = cv2.Laplacian(image, cv2.CV_64F)
    sharpened = cv2.convertScaleAbs(image - laplacian)
    return sharpened

def apply_unsharp_mask(image, kernel_size=(3, 3), sigma=1.0, amount=0.3):
    blurred = cv2.GaussianBlur(image, kernel_size, sigma)    
    sharpened = cv2.addWeighted(image, 1 + amount, blurred, -amount, 0)    
    return sharpened

result_data = None

def set_result_model(results):
    global result_data
    result_data = results.copy()
    # print(result_data)
 
def get_result_model():
    global result_data
    return result_data


# def init_image_processing_model():
#     first_init = None

#     # init OpenCV Default
#     ref_image_dir = f"{script_dir}/../Targets/"
#     num_signs = 10  # Define the number of reference images
#     symbols = load_ref_images(ref_image_dir, num_signs)

#     # init Yolo
#     model = YOLO(f"{script_dir}/image_algo/models/best_1.pt")

#     image = cv2.imread(f"{script_dir}/image_algo/models/init.jpg")
#     image = cv2.resize(image, (CAP_PROP_FRAME_WIDTH, CAP_PROP_FRAME_HEIGHT))
#     model.predict(image, imgsz=[960, 544], verbose=False)

#     if first_init is None:
#         first_init = True
#         set_init_status(first_init)

#     return model

# 모델을 GPU로 이동하는 함수
def to_device(model):
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    model.to(device)
    return model

def init_image_processing_model():
    first_init = None
    models = []

    # Initialize all models with a dummy frame
    image = cv2.imread(f"{script_dir}/image_algo/models/init.jpg")
    image = cv2.resize(image, (CAP_PROP_FRAME_WIDTH, CAP_PROP_FRAME_HEIGHT))

    # YOLOv8 model
    yolo_model_path = f"{script_dir}/image_algo/models/best_17.pt"
    yolo_model = YOLOAlgorithm(yolo_model_path)
    yolo_model.detector.model.to(torch.device('cuda' if torch.cuda.is_available() else 'cpu'))
    yolo_model.detect(image)
    models.append(yolo_model)
    model_name = yolo_model.get_name()
    print(f"{model_name} init done")

    # TFLite model
    tflite_model_path = f"{script_dir}/image_algo/models/detect.tflite"
    tflite_model = TFLiteAlgorithm(tflite_model_path)
    tflite_model.detect(image)
    models.append(tflite_model)
    model_name = tflite_model.get_name()
    print(f"{model_name} init done")

    # OpenCV model
    opencv_symbols_path = f"{script_dir}/image_algo/models"
    symbols = load_ref_images(opencv_symbols_path, num_signs=10)
    opencv_model = OpenCVDefaultAlgorithm(symbols)
    opencv_model.detect(image)
    models.append(opencv_model)
    model_name = opencv_model.get_name()
    print(f"{model_name} init done")

    if first_init is None:
        first_init = True
        set_init_status(first_init)

    return models


init_status = None
def set_init_status(init):
    global init_status
    init_status = copy.deepcopy(init)
    

def get_init_status():
    global init_status
    return init_status


progress_state = 0  # 전역 변수를 사용하여 상태를 저장

def init_model_image(frame):
    global progress_state

    imageMat = cv2.imdecode(np.frombuffer(frame, dtype=np.uint8), cv2.IMREAD_COLOR)

    # 이미지를 회색으로 변환
    gray_image = cv2.cvtColor(imageMat, cv2.COLOR_BGR2GRAY)
    gray_image_colored = cv2.cvtColor(gray_image, cv2.COLOR_GRAY2BGR)

    # 블러링 적용
    blurred_image = cv2.GaussianBlur(gray_image_colored, (15, 15), 0)

    # 프로그레스 바 텍스트 설정
    dots = ['.', '..', '...']
    base_text = "Detection Models initializing"
    text = f"{base_text}{dots[progress_state]}"

    # 다음 상태로 전환
    progress_state = (progress_state + 1) % len(dots)

    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.7
    thickness = 1
    # 고정된 텍스트 크기 계산
    fixed_text_size = cv2.getTextSize(base_text + "...", font, font_scale, thickness)[0]
    text_x = blurred_image.shape[1] - fixed_text_size[0] - 10  # 10은 우측 여백
    text_y = blurred_image.shape[0] - 10  # 10은 하단 여백
    cv2.putText(blurred_image, text, (text_x, text_y), font, font_scale, (255, 255, 255), thickness)

    _, buffer = cv2.imencode('.jpg', blurred_image)
    buffer_bytes = buffer.tobytes()  # numpy 배열을 bytes 객체로 변환
    packedData = struct.pack(f'>II{len(buffer_bytes)}s', len(buffer_bytes), 3, buffer_bytes)
    return packedData

def flush_queue(q):
    while not q.empty():
        try:
            item = q.get_nowait()  # 아이템을 즉시 꺼냄
        except:
            break  # 큐가 비어있으면 반복 종료 Queue.empty()

def image_processing_thread(QUEUE, shutdown_event, form_instance):
    DATA = {}
    debug_folder = "debug"
    os.makedirs(debug_folder, exist_ok=True)

    # if shutdown_event.is_set() == True:
    #     print("shutdown_event already set in image_processing")

    while not shutdown_event.is_set():
        try:
            # time.sleep(0.01)  # Tuning point
            frame = QUEUE.get(timeout=1)
            
            # if frame is None:  # 종료 신호로 None 사용 가능
            #     print("Queue is zero")
            #     break

            # if not QUEUE.empty():
            imageMat = cv2.imdecode(np.frombuffer(frame, dtype=np.uint8), cv2.IMREAD_COLOR)
            # h, w, _ = imageMat.shape
            # print(f"width {w}, height {h}")

            # img_model_global 값을 가져오는 예제
            # img_model = form_instance.get_img_model()
            # if img_model is not None:
            #     # print("Model is initialized and ready to use.")
            #     results = img_model.predict(imageMat, imgsz=[960, 544], verbose=False)
            # else:
            #     # print("Model is not initialized yet.")
            #     continue

            models = form_instance.get_img_model()
            if models is None:
                continue

            target_info = []
            box_info = []

            results = models.detect(imageMat)
            for result in results:
                coords, label = result
                (x1, y1), (x2, y2) = coords

                width = x2 - x1
                height = y2 - y1
                if width < 20 or height < 20 or width > 100 or height > 100:
                    continue

                center_x = (x1 + x2) / 2
                center_y = (y1 + y2) / 2

                target_info.append({
                    "label": label,
                    "center": [center_x, center_y],
                    "bbox": [x1, y1, x2, y2],
                    "size": [width, height]
                })

                box_info.append({
                    "label": label,
                    "bbox": [x1, y1, x2, y2],
                    "center": [center_x, center_y],
                })

                # # 박스와 라벨을 이미지에 그림
                # cv2.rectangle(imageMat, (x1, y1), (x2, y2), (255, 0, 0), 2)
                # cv2.putText(imageMat, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)


            # DATA 딕셔너리에 업데이트
            DATA['target_info'] = target_info
            # DATA['box_info'] = box_info


            # target_queue.put(target_info)
            box_queue.put(box_info)
            # target_queue.put(target_info)
            set_result_model(DATA)

            # cv2.imshow('Detection and Classification Result', imageMat)

            # key = cv2.waitKey(1) & 0xFF
            # if key == ord('q'):  # Quit without saving
            #     cv2.destroyWindow('Manual Labeling')
        except Empty:
            continue
        # process_frame(frame)
    
    clean_up_resources() # clean up resources
    flush_queue(QUEUE)   # flush QUEUE instance
    print("Main Image Process Thread Exit")

def clean_up_resources():
    target_info = []
    box_info = []
    print("Cleaning up resoures...")