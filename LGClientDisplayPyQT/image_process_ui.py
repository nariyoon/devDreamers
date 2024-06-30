# image_process_ui.py

from PyQt5.QtCore import QThread, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QPixmap, QImage, QPainter, QPen, QColor
import cv2
import numpy as np
from image_process import get_result_model
from image_algo.kalman_filter import KalmanBoxTracker
import time
from cannon_queue import *



class ImageProcessingThread(QThread):
    image_processed = pyqtSignal(QPixmap)

    def __init__(self, parent=None):
        super().__init__(parent)
        # self.shutdown_event = shutdown_event
        self.image_data = None
        self.rcv_state_curr = None
        self.running = True
        self.trackers = {}

    def update_image_data(self, image_data):
        self.image_data = image_data

    def update_selected_model(self, img_process_model):
        self.img_process_model = img_process_model

    @pyqtSlot(int)
    def update_rcv_state(self, state):
        self.rcv_state_curr = state

    def save_box_info():
        while True:
            result_data = get_result_model()
            if result_data and 'box_info' in result_data:
                box_info_list = result_data['box_info']
                print("Box Info List:")
                for box_info in box_info_list:
                    print(box_info)
                    # # Save each box_info to a file or use it as needed
                    # with open("box_info.txt", "a") as file:
                    #     file.write(f"{box_info}\n")
            # time.sleep(1)  # Sleep for 1 second before checking again

    
    def run(self):
        while self.running:
            time.sleep(0.01)  # Tuning point
            if self.image_data is not None:
                np_arr = np.frombuffer(self.image_data, np.uint8)
                img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
                
                if img is not None:
                    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                    h, w, ch = img_rgb.shape
                    bytes_per_line = ch * w
                    qt_image = QImage(img_rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
                    pixmap = QPixmap.fromImage(qt_image)

                    # Add red cross hair in pixmap
                    painter = QPainter(pixmap)
                    pen = QPen(QColor(255, 0, 0), 2)
                    painter.setPen(pen)
                    center_x = w // 2
                    center_y = h // 2
                    half_size = 30  # Change the crosshair size if needed
                    painter.drawLine(center_x - half_size, center_y, center_x + half_size, center_y)
                    painter.drawLine(center_x, center_y - half_size, center_x, center_y + half_size)

                    # Draw boxes from box_info
                    try:
                        result_data = box_queue.get_nowait()
                        for box_info in result_data:
                            x1, y1, x2, y2 = box_info['bbox']
                            label = box_info['label']

                            if self.img_process_model == "YOLOv8":
                                pen_color = QColor(173, 255, 47)  # Green
                            elif self.img_process_model == "TFLite":
                                pen_color = QColor(0, 0, 255)  # Blue
                            elif self.img_process_model == "OpenCV":
                                pen_color = QColor(255, 0, 0)  # Red
                            else:
                                pen_color = QColor(173, 255, 47)  # Default Green

                            painter.setPen(QPen(pen_color, 3))
                            painter.drawRect(x1, y1, x2 - x1, y2 - y1)
                            painter.drawText(x1, y1 - 5, label)

                    except Empty:
                        pass

                    painter.end()
                    self.image_processed.emit(pixmap)
                self.image_data = None

    def stop(self):
        self.running = False
        self.wait()
        print("Image processing UI thread is closed successfully.")