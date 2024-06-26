import os
import sys
import threading
import time
import cv2
import struct
from queue import Queue, Full
from image_algo.yolov8_algo import YOLO_Detector
from image_algo.tflite_algo import ObjectDetector
from ultralytics import YOLO
import numpy as np
import os
from datetime import datetime
from filterpy.kalman import KalmanFilter
import copy


# Add the parent directory of `image_algo` to sys.path
script_dir = os.path.dirname(os.path.realpath(__file__))
parent_dir = os.path.abspath(os.path.join(script_dir, '..'))
sys.path.append(parent_dir)

CAP_PROP_FRAME_WIDTH = 960
CAP_PROP_FRAME_HEIGHT = 544
INIT_TIME = 5
QUEUE_MAX_SIZE = 10  # 큐의 최대 크기 설정

class TFLiteAlgorithm:
    def __init__(self, model_path):
        self.detector = ObjectDetector(model_path)
        self.ready = False
        self.model_name = self.detector.model_name

    def initialize(self, first_frame, ready_event):
        # Dummy initialization logic with the first frame
        self.detector.detect(first_frame, first_frame.copy())
        self.ready = True
        ready_event.set()

    def detect(self, frame, draw_frame):
        if not self.ready:
            return draw_frame, []  # TFLite model is not ready yet, return empty result
        return self.detector.detect(frame, draw_frame)

class YOLOAlgorithm:
    def __init__(self, model_path):
        self.detector = YOLO_Detector(model_path)
        self.ready = False
        self.model_name = self.detector.model_name

    def initialize(self, first_frame, ready_event):
        # Initialize the YOLO model with the first frame
        self.detector.model.predict(first_frame, imgsz=640)
        self.ready = True
        ready_event.set()

    def detect(self, frame, draw_frame):
        if not self.ready:
            return draw_frame, []  # YOLO is not ready yet, return empty result
        return self.detector.detect(frame, draw_frame)

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

def init_image_processing_model():
    first_init = None
    model = YOLO(f"{script_dir}/image_algo/models/best_1.pt")

    image = cv2.imread(f"{script_dir}/image_algo/models/init.jpg")
    image = cv2.resize(image, (CAP_PROP_FRAME_WIDTH, CAP_PROP_FRAME_HEIGHT))
    model.predict(image, imgsz=[960, 544], verbose=False)

    if first_init is None:
        first_init = True
        set_init_status(first_init)

    return model

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
    base_text = "YOLOv8 initializing"
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


def image_processing_thread(QUEUE, shutdown_event, form_instance):
    DATA = {}
    debug_folder = "debug"
    os.makedirs(debug_folder, exist_ok=True)

    # while True:
    while not shutdown_event.is_set():
        if not QUEUE.empty():
            frame = QUEUE.get()
            if frame is None:
                break

            imageMat = cv2.imdecode(np.frombuffer(frame, dtype=np.uint8), cv2.IMREAD_COLOR)
            # h, w, _ = imageMat.shape
            # print(f"width {w}, height {h}")

            # img_model_global 값을 가져오는 예제
            img_model = form_instance.get_img_model()
            if img_model is not None:
                # print("Model is initialized and ready to use.")
                results = img_model.predict(imageMat, imgsz=[960, 544], verbose=False)
            else:
                # print("Model is not initialized yet.")
                continue

            target_info = []
            box_info = []
            for result in results:
                boxes = result.boxes

                if len(boxes) == 0:
                    continue
                for box in boxes:
                    coords = box.xyxy[0].cpu().numpy()
                    score = box.conf[0].cpu().item()
                    if score < 0.5:
                        continue
                    x1, y1, x2, y2 = map(int, coords)
                    width = x2 - x1
                    height = y2 - y1

                    if width < 20 or height < 20 or width > 100 or height > 100:
                        continue

                    # 라벨 번호와 박스 중심점 계산
                    label = f"{int(box.cls[0].cpu().item())}"
                    center_x = (x1 + x2) / 2
                    center_y = (y1 + y2) / 2

                    # 정보를 리스트에 추가
                    target_info.append({
                        "label": label,
                        "center": [center_x, center_y],
                        "size": [width, height]
                    })

                    box_info.append({
                        "label": label,
                        "bbox": [x1, y1, x2, y2]
                    })

            # DATA 딕셔너리에 업데이트
            DATA['target_info'] = target_info
            DATA['box_info'] = box_info
            set_result_model(DATA)
            # cv2.imshow('Detection and Classification Result', imageMat)

            # key = cv2.waitKey(1)
            # if key == ord('q'):
            #     cv2.destroyAllWindows()
            #     break
            # elif key == ord('s'):
            #     # 이미지 파일로 저장
            #     timestamp = datetime.now().strftime("%Y%m%d_%H%M%S%f")
            #     image_filename = os.path.join(debug_folder, f"{timestamp}.jpg")
            #     cv2.imwrite(image_filename, imageMat)
            #     print(f"Image saved: {image_filename}")

    pass
    print("Main Image Process Thread Exit")

