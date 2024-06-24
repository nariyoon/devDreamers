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

def image_processing_task(frame_queue, processed_queue, algorithms, ready_events):
    # 모든 알고리즘이 준비될 때까지 대기
    for event in ready_events:
        event.wait()
        
    while True:
        frame = frame_queue.get()
        if frame is None:
            break

        draw_frame = frame.copy()
        for algorithm in algorithms:
            algorithm.detect(frame, draw_frame)
            cv2.putText(draw_frame, f"{algorithm.model_name}", (draw_frame.shape[1] - 200, 30), 
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 1, cv2.LINE_AA)
        processed_queue.put(draw_frame)

def initialize_algorithms(algorithms, first_image):
    ready_events = [threading.Event() for _ in algorithms]
    for algorithm, ready_event in zip(algorithms, ready_events):
        threading.Thread(target=algorithm.initialize, args=(first_image, ready_event)).start()
    return ready_events

def display_initializing_frame(frame, algorithms, ready_events, elapsed_time):
    # 현재 프레임에 그레이스케일 및 블러 적용
    draw_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    draw_frame = cv2.GaussianBlur(draw_frame, (21, 21), 0)
    draw_frame = cv2.cvtColor(draw_frame, cv2.COLOR_GRAY2BGR)
    for algorithm, ready_event in zip(algorithms, ready_events):
        if not ready_event.is_set():
            cv2.putText(draw_frame, f"{algorithm.model_name} initializing ...", 
                        (50, CAP_PROP_FRAME_HEIGHT // 2), cv2.FONT_HERSHEY_SIMPLEX, 1, 
                        (255, 255, 255), 2, cv2.LINE_AA)
    return draw_frame


result_data = None

def set_result_model(results):
    global result_data
    result_data = results.copy()
    print(result_data)
 
def get_result_model():
    global result_data
    return result_data

def init_image_processing_model():
    model = YOLO(f"{script_dir}/image_algo/models/best_960x544_50_2_final.pt")
    return model

def image_processing_thread(frame_queue, model):
    DATA = {}
    while True:
        frame = frame_queue.get()
        if frame is None:
            break

        imageMat = cv2.imdecode(np.frombuffer(frame, dtype=np.uint8), cv2.IMREAD_COLOR)
        results = model.predict(imageMat, imgsz=[960, 544], verbose=False)

        target_info = []
        box_info = []
        for result in results:
            boxes = result.boxes

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

