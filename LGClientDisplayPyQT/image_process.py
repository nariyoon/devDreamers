import os
import sys
import threading
import time
import cv2
from queue import Queue, Full
from image_algo.yolov8_algo import YOLO_Detector
from image_algo.tflite_algo import ObjectDetector

# Add the parent directory of `image_algo` to sys.path
script_dir = os.path.dirname(os.path.realpath(__file__))
parent_dir = os.path.abspath(os.path.join(script_dir, '..'))
sys.path.append(parent_dir)

CAP_PROP_FRAME_WIDTH = 1920
CAP_PROP_FRAME_HEIGHT = 1080
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

def process_images(algorithms, frame_queue):
    processed_queue = Queue()

    # 첫 번째 이미지를 대기
    first_image = frame_queue.get()
    ready_events = initialize_algorithms(algorithms, first_image)

    img_thread = threading.Thread(target=image_processing_task, args=(frame_queue, processed_queue, algorithms, ready_events))
    img_thread.start()

    frame_cnt = 0
    init_start_time = time.time()

    while True:
        frame = frame_queue.get()

        # height, width = frame.shape()
        # print(f" height {height} width {width}")

        if frame is None:
            break

        # 모든 알고리즘이 초기화되었는지 확인
        all_initialized = all(event.is_set() for event in ready_events)
        elapsed_time = time.time() - init_start_time
        if not all_initialized and elapsed_time < INIT_TIME:
            draw_frame = display_initializing_frame(frame, algorithms, ready_events, elapsed_time)
        else:
            if not all_initialized:
                for event in ready_events:
                    event.set()  # 타임아웃 후 모든 이벤트 설정
            processed_frame = processed_queue.get() if not processed_queue.empty() else frame
            draw_frame = processed_frame.copy()

        center_x, center_y = CAP_PROP_FRAME_WIDTH // 2, CAP_PROP_FRAME_HEIGHT // 2
        cv2.imshow('Frame', draw_frame)

        key = cv2.waitKey(1)
        if key & 0xFF == ord('q'):
            break

        frame_cnt += 1

    frame_queue.put(None)
    processed_queue.put(None)
    cv2.destroyAllWindows()

    img_thread.join()

    return

def start_image_processing(frame_queue):
    algorithms = [
        # TFLiteAlgorithm(f"{script_dir}/image_algo/models/detect.tflite"),
        YOLOAlgorithm(f"{script_dir}/image_algo/models/best.pt"),
    ]
    
    # TCP/IP 스레드가 이미 실행되고 있는 상태에서 frame_queue를 사용한다고 가정
    process_images(algorithms, frame_queue)

if __name__ == "__main__":
    frame_queue = Queue(maxsize=10)
    start_image_processing(frame_queue)
