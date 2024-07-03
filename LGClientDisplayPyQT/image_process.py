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
import mediapipe as mp
import psutil
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


class ImageFilter:
    def __init__(self, name):
        self.name = name

    def apply_no_filter(self, image):
        # Do nothing, return the original image
        return image

    def apply_custom_sharpening_filter(self, image):
        # 강한 샤프닝 효과를 주는 커널
        kernel = np.array([[0, -1, 0],
                           [-1, 5, -1],
                           [0, -1, 0]])
        sharpened_image = cv2.filter2D(image, -1, kernel)
        return sharpened_image

    def apply_laplacian_sharpening(self, image):
        laplacian = cv2.Laplacian(image, cv2.CV_64F)
        sharpened = cv2.convertScaleAbs(image - laplacian)
        return sharpened

    def apply_unsharp_mask(self, image, kernel_size=(3, 3), sigma=1.0, amount=0.3):
        blurred = cv2.GaussianBlur(image, kernel_size, sigma)
        sharpened = cv2.addWeighted(image, 1 + amount, blurred, -amount, 0)
        return sharpened

    def adjust_brightness(self, image, beta_value=100):
        # Adjust the brightness by adding the beta_value to all pixels
        brightened_image = cv2.convertScaleAbs(image, alpha=1, beta=beta_value)
        return brightened_image

    def get_name(self):
        return self.name

def init_filter_models():
    models = []

    no_filter = ImageFilter("No Filter")
    models.append(no_filter)
    print(f"{no_filter.get_name()} init done")

    custom_filter = ImageFilter("Custom Sharpening Filter")
    models.append(custom_filter)
    print(f"{custom_filter.get_name()} init done")

    laplacian_filter = ImageFilter("Laplacian Sharpening")
    models.append(laplacian_filter)
    print(f"{laplacian_filter.get_name()} init done")

    unsharp_mask_filter = ImageFilter("Unsharp Mask")
    models.append(unsharp_mask_filter)
    print(f"{unsharp_mask_filter.get_name()} init done")

    brightness_filter = ImageFilter("Brightness Adjustment")
    models.append(brightness_filter)
    print(f"{brightness_filter.get_name()} init done")

    return models

def add_image_filter(image):
    imageMat = cv2.imdecode(np.frombuffer(image, dtype=np.uint8), cv2.IMREAD_COLOR)
    filter_model = get_curr_filter()

    if filter_model.name == "No Filter":
        filtered_image = filter_model.apply_no_filter(imageMat)
    elif filter_model.name == "Custom Sharpening Filter":
        filtered_image = filter_model.apply_custom_sharpening_filter(imageMat)
    elif filter_model.name == "Laplacian Sharpening":
        filtered_image = filter_model.apply_laplacian_sharpening(imageMat)
    elif filter_model.name == "Unsharp Mask":
        filtered_image = filter_model.apply_unsharp_mask(imageMat)
    elif filter_model.name == "Brightness Adjustment":
        filtered_image = filter_model.adjust_brightness(imageMat, beta_value=50)

    _, buffer = cv2.imencode('.jpg', filtered_image)
    buffer = buffer.tobytes()

    len_ = len(buffer)
    type_ = 3
    packedData = struct.pack(f'>II{len_}s', len_, type_, buffer)

    return packedData


result_data = None

def set_result_model(results):
    global result_data
    result_data = results.copy()
    # print(result_data)
 
def get_result_model():
    global result_data
    return result_data

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
    yolo_model_path = f"{script_dir}/image_algo/models/best_18.pt"
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
    os.environ['GLOG_minloglevel'] = '2'

    mp_hands = mp.solutions.hands
    hands = mp_hands.Hands()
    # p = psutil.Process(os.getpid())
    # p.nice(psutil.REALTIME_PRIORITY_CLASS)
    p = psutil.Process(os.getpid())
    # 프로세스 우선 순위 설정 (예: -20이 가장 높은 우선 순위, 19가 가장 낮은 우선 순위)
    # p.nice(-20)  # 이 값을 적절히 조정하세요


    target_status = {}
    disappearance_threshold = 3
    movement_threshold = 5
    direction_threshold = 20

    while not shutdown_event.is_set():
        try:
            imageMat, targetStatus, targetNum = QUEUE.get(timeout=1)

            # print(f"targetStatus {targetStatus} targetNum {targetNum}")

            if targetStatus == 3:
                continue

            imageMat = cv2.imdecode(np.frombuffer(imageMat, dtype=np.uint8), cv2.IMREAD_COLOR)

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
                area = height * height
                # print(f"label {label} area {area}")
                if width < 20 or height < 20 or width > 150 or height > 150:
                    continue

                center_x = (x1 + x2) / 2
                center_y = (y1 + y2) / 2

                target_info.append({
                    "label": label,
                    "center": [center_x, center_y],
                    "bbox": [x1, y1, x2, y2],
                    "size": [width, height],
                    "area" : area
                })

                box_info.append({
                    "label": label,
                    "bbox": [x1, y1, x2, y2],
                    "center": [center_x, center_y],
                })

                if targetStatus == 2 and label == str(targetNum):
                    if label not in target_status:
                        target_status[label] = {
                            'disappearance_count': 0,
                            'last_position': (center_x, center_y),
                            'movement': 'stationary'
                        }
                    elif target_status[label]['movement'] != 'hit':
                        prev_center_x, prev_center_y = target_status[label]['last_position']
                        displacement = np.sqrt((center_x - prev_center_x) ** 2 + (center_y - prev_center_y) ** 2)

                        if displacement > movement_threshold:
                            target_status[label]['movement'] = 'hit'
                        elif abs(center_x - prev_center_x) > direction_threshold or abs(center_y - prev_center_y) > direction_threshold:
                            target_status[label]['movement'] = 'moving'
                        else:
                            target_status[label]['movement'] = 'stationary'

                        target_status[label]['last_position'] = (center_x, center_y)
                        target_status[label]['disappearance_count'] = 0

            if targetStatus == 2:
                if str(targetNum) in target_status:
                    if not any(t['label'] == str(targetNum) for t in target_info):
                        target_status[str(targetNum)]['disappearance_count'] += 1
                        if target_status[str(targetNum)]['disappearance_count'] > disappearance_threshold:
                            target_status[str(targetNum)]['movement'] = 'hit'
                    else:
                        target_status[str(targetNum)]['disappearance_count'] = 0
                    

                    save_target_status(target_status)

            image = cv2.cvtColor(imageMat, cv2.COLOR_BGR2RGB)
            results = hands.process(image)
            if results.multi_hand_landmarks:
                for hand_landmarks in results.multi_hand_landmarks:
                    x_min, y_min = float('inf'), float('inf')
                    x_max, y_max = float('-inf'), float('-inf')
                    for landmark in hand_landmarks.landmark:
                        x, y = int(landmark.x * image.shape[1]), int(landmark.y * image.shape[0])
                        x_min, y_min = min(x_min, x), min(y_min, y)
                        x_max, y_max = max(x_max, x), max(y_max, y)

                    box_info.append({
                        "label": "10",
                        "bbox": [x_min, y_min, x_max, y_max],
                        "center": [(x_min + x_max) / 2, (y_min + y_max) / 2],
                    })

            DATA['target_info'] = target_info

            box_queue.put(box_info)
            set_result_model(DATA)

        except Empty:
            continue

    clean_up_resources()
    flush_queue(QUEUE)
    print("Main Image Process Thread Exit")

def save_target_status(target_status):
    # Implement saving logic here
    print("Saving target status:", target_status)

def clean_up_resources():
    target_info = []
    box_info = []
    print("Cleaning up resoures...")