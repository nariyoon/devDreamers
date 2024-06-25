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

# Add the parent directory of `image_algo` to sys.path
script_dir = os.path.dirname(os.path.realpath(__file__))
parent_dir = os.path.abspath(os.path.join(script_dir, '..'))
sys.path.append(parent_dir)

CAP_PROP_FRAME_WIDTH = 960
CAP_PROP_FRAME_HEIGHT = 540
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
    model = YOLO(f"{script_dir}/image_algo/models/best.pt")
    return model

def image_processing_thread(QUEUE, model, shutdown_event):
    DATA = {}
    # while True:
    while not shutdown_event.is_set():
        if not QUEUE.empty():
            frame = QUEUE.get()
            if frame is None:
                break

            imageMat = cv2.imdecode(np.frombuffer(frame, dtype=np.uint8), cv2.IMREAD_COLOR)
            results = model.predict(imageMat, imgsz=[960, 544], verbose=False)

            target_info = []
            box_info = []
            for result in results:
                boxes = result.boxes

                if len(boxes) == 0:
                    continue
                score = boxes.conf[0].cpu().item()
                if score < 0.5:
                    continue

                for box in boxes:
                    coords = box.xyxy[0].cpu().numpy()
                    score = box.conf[0].cpu().item()
                    if score < 0.5:
                        continue
                    x1, y1, x2, y2 = map(int, coords)

                    # 라벨 번호와 박스 중심점 계산
                    label = f"{int(box.cls[0].cpu().item())}"
                    center_x = (x1 + x2) / 2
                    center_y = (y1 + y2) / 2

                    # 정보를 리스트에 추가
                    target_info.append({
                        "label": label,
                        "center": [round(center_x, 1), round(center_y, 1)]
                    })

                    box_info.append({
                        "label": label,
                        "bbox": [x1, y1, x2, y2]
                    })

                    # 박스와 라벨 그리기
                    cv2.rectangle(imageMat, (x1, y1), (x2, y2), (0, 255, 0), 1)
                    cv2.putText(imageMat, label, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 255, 0), 2)

                    # 중심점 빨간색 점 그리기
                    cv2.circle(imageMat, (int(center_x), int(center_y)), 3, (0, 0, 255), -1)


            # DATA 딕셔너리에 업데이트
            DATA['target_info'] = target_info
            DATA['box_info'] = box_info
            set_result_model(DATA)
            cv2.imshow('Detection and Classification Result', imageMat)

            key = cv2.waitKey(1)
            if key == ord('q'):
                cv2.destroyAllWindows()
                break
    pass
    print("Main Image Process Thread Exit")

