import os
import cv2
import threading
import random
import time
from queue import Queue, Full
import glob
import numpy as np
from yolov8_algo import YOLO_Detector
from tflite_algo import ObjectDetector  # 추가된 import

CAP_PROP_FRAME_WIDTH = 1920
CAP_PROP_FRAME_HEIGHT = 1080
INIT_TIME = 4
QUEUE_MAX_SIZE = 10  # 큐의 최대 크기 설정

class ImageStream:
    def __init__(self, frame_queue, image_files):
        self.frame_queue = frame_queue
        self.stopped = False
        self.image_files = image_files
        self.file_index = 0

    def update(self):
        while not self.stopped:
            if self.file_index >= len(self.image_files):
                self.file_index = 0  # Loop through the images

            image_file = self.image_files[self.file_index]
            frame = cv2.imread(image_file)
            frame = cv2.resize(frame, (CAP_PROP_FRAME_WIDTH, CAP_PROP_FRAME_HEIGHT))

            try:
                self.frame_queue.put(frame, timeout=1)
            except Full:
                print("Queue is full. Discarding oldest frame.")
                self.frame_queue.get()
                self.frame_queue.put(frame)

            self.file_index += 1

            # Simulate random network delay
            delay = random.uniform(0.1, 0.5)
            print(f"Simulating network delay: {delay:.2f} seconds")
            time.sleep(delay)

    def start(self):
        threading.Thread(target=self.update, args=()).start()
    
    def stop(self):
        self.stopped = True

def image_processing_task(frame_queue, processed_queue, algorithms, ready_events):
    # Wait for all algorithms to be ready
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
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2, cv2.LINE_AA)
        processed_queue.put(draw_frame)

def load_ref_images(ref_image_dir, num_signs):
    # Dummy function to load reference images
    # Replace with actual loading code
    return []

class OpenCVDefaultAlgorithm:
    def __init__(self, symbols):
        self.ready = False
        self.model_name = "OpenCV Default"

    def initialize(self, first_frame, ready_event):
        # Dummy initialization logic
        time.sleep(3)  # Simulate initialization time
        self.ready = True
        ready_event.set()

    def detect(self, frame, draw_frame):
        pass

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

def process_images(algorithms):
    script_dir = os.path.dirname(os.path.realpath(__file__))
    image_dir = f"{script_dir}/../../../Pytest/dataset/NewTrainingRaw/images"
    image_files = sorted(glob.glob(f"{image_dir}/*.jpg"))
    print(f"image_files length {len(image_files)}")

    frame_queue = Queue(maxsize=QUEUE_MAX_SIZE)
    processed_queue = Queue()

    image_stream = ImageStream(frame_queue, image_files)
    image_stream.start()

    ready_events = [threading.Event() for _ in algorithms]

    # Initialize all algorithms with the first image
    first_image = cv2.imread(image_files[0])
    first_image = cv2.resize(first_image, (CAP_PROP_FRAME_WIDTH, CAP_PROP_FRAME_HEIGHT))
    for algorithm, ready_event in zip(algorithms, ready_events):
        threading.Thread(target=algorithm.initialize, args=(first_image, ready_event)).start()

    img_thread = threading.Thread(target=image_processing_task, args=(frame_queue, processed_queue, algorithms, ready_events))
    img_thread.start()

    frame_cnt = 0
    init_start_time = time.time()

    while True:
        frame = frame_queue.get()
        if frame is None:
            break

        # Check if all algorithms have initialized
        all_initialized = all(event.is_set() for event in ready_events)
        elapsed_time = time.time() - init_start_time
        if not all_initialized and elapsed_time < INIT_TIME:
            # Apply grayscale and blur to the current frame
            draw_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            draw_frame = cv2.GaussianBlur(draw_frame, (21, 21), 0)
            draw_frame = cv2.cvtColor(draw_frame, cv2.COLOR_GRAY2BGR)
            for algorithm, ready_event in zip(algorithms, ready_events):
                if not ready_event.is_set():
                    cv2.putText(draw_frame, f"{algorithm.model_name} initializing ...", 
                                (50, CAP_PROP_FRAME_HEIGHT // 2), cv2.FONT_HERSHEY_SIMPLEX, 1, 
                                (255, 255, 255), 2, cv2.LINE_AA)
        else:
            if not all_initialized:
                for event in ready_events:
                    event.set()  # Ensure all events are set after timeout
            processed_frame = processed_queue.get() if not processed_queue.empty() else frame
            draw_frame = processed_frame.copy()

        center_x, center_y = CAP_PROP_FRAME_WIDTH // 2, CAP_PROP_FRAME_HEIGHT // 2
        cv2.line(draw_frame, (0, center_y), (CAP_PROP_FRAME_WIDTH, center_y), (255, 255, 255), 1)
        cv2.line(draw_frame, (center_x, 0), (center_x, CAP_PROP_FRAME_HEIGHT), (255, 255, 255), 1)
        cv2.putText(draw_frame, f"frame_cnt {frame_cnt}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

        cv2.imshow('Frame', draw_frame)

        key = cv2.waitKey(1)
        if key & 0xFF == ord('q'):
            break

        frame_cnt += 1

    frame_queue.put(None)
    processed_queue.put(None)
    cv2.destroyAllWindows()

    image_stream.stop()
    img_thread.join()

    return

if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.realpath(__file__))
    ref_image_dir = f"{script_dir}/../Targets/"
    num_signs = 10  # Define the number of reference images
    symbols = load_ref_images(ref_image_dir, num_signs)

    algorithms = [
        # OpenCVDefaultAlgorithm(symbols),
        # TFLiteAlgorithm(f"{script_dir}/models/detect.tflite"),
        YOLOAlgorithm(f"{script_dir}/models/best.pt"),
    ]

    process_images(algorithms)
