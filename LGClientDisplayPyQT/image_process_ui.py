# image_process_ui.py

from PyQt5.QtCore import QThread, pyqtSignal, QPoint, pyqtSlot
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

    def run(self):
        while self.running:
            time.sleep(0.01)  # Tuning point
            if self.image_data is not None:
                np_arr = np.frombuffer(self.image_data, np.uint8)
                img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
                
                if img is not None:
                    X_correct = 490  # Tuning Point compared to Laser
                    Y_correct = 310  # Tuning Point compared to Laser
                    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                    h, w, ch = img_rgb.shape
                    bytes_per_line = ch * w
                    qt_image = QImage(img_rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
                    pixmap = QPixmap.fromImage(qt_image)

                    # Create painter to draw on pixmap
                    painter = QPainter(pixmap)
                    pen = QPen(QColor(255, 0, 0), 2)
                    painter.setPen(pen)
                    crosshair_size = 30  # Size of the crosshair

                    # Draw the crosshair at the specified offset position
                    painter.drawLine(X_correct - crosshair_size, Y_correct, X_correct + crosshair_size, Y_correct)
                    painter.drawLine(X_correct, Y_correct - crosshair_size, X_correct, Y_correct + crosshair_size)

                    # # Crop and resize the image around the new crosshair center
                    # crop_size = 200  # Define the size of the crop area
                    # x1 = max(0, X_correct - crop_size // 2)
                    # y1 = max(0, Y_correct - crop_size // 2)
                    # x2 = min(w, X_correct + crop_size // 2)
                    # y2 = min(h, Y_correct + crop_size // 2)
                    # cropped_img = img[y1:y2, x1:x2]
                    # cropped_img = cv2.resize(cropped_img, (w, h))  # Resize to the original size

                    # Convert the cropped and resized image back to QImage and QPixmap
                    # cropped_rgb = cv2.cvtColor(cropped_img, cv2.COLOR_BGR2RGB)
                    # cropped_qt_image = QImage(cropped_rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
                    # cropped_pixmap = QPixmap.fromImage(cropped_qt_image)

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

                    # # Create a FPS Text to modify the QPixmap
                    # # painter = QPainter(pixmap)
                    # try:
                    #     fps_data = fps_queue.get_nowait()
                    #     for fps_info in fps_data:
                    #         rt_fps = fps_info['fps']
                    #     # Set the pen color to black and make the text bold
                    #     pen = QPen(QColor(0, 0, 0))  # Black color
                    #     painter.setPen(pen)
                    #     font = painter.font()
                    #     font.setPixelSize(20)  # Adjust font size
                    #     font.setBold(True)  # Set the font to be bold
                    #     painter.setFont(font)

                    #     # Text to display
                    #     display_text = f"AVG FPS : {rt_fps:.2f}" 
                    #     text_position = QPoint(10, h - 30)  # Adjust coordinates for the bottom left

                    #     # Draw text at specified position
                    #     painter.drawText(text_position, display_text)

                    # except Empty:
                    #     pass

                    painter.end()
                    self.image_processed.emit(pixmap)

                self.image_data = None

    def stop(self):
        self.running = False
        self.wait()
        print("Image processing UI thread is closed successfully.")