# image_process_ui.py

from PyQt5.QtCore import QThread, pyqtSignal, QPoint, pyqtSlot, Qt
from PyQt5.QtGui import QPixmap, QImage, QPainter, QPen, QColor, QFont
import cv2
import numpy as np
import time
from queue import Empty
from cannon_queue import box_queue


class ImageProcessingThread(QThread):
    image_processed = pyqtSignal(QPixmap)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.image_data = None
        self.rcv_state_curr = None
        self.running = True
        self.trackers = {}
        self.prev_data = []

    def update_image_data(self, image_data):
        self.image_data = image_data

    def update_selected_model(self, img_process_model):
        # print(f"update_selected_model {img_process_model}")
        self.img_process_model = img_process_model

    @pyqtSlot(int)
    def update_rcv_state(self, state):
        self.rcv_state_curr = state

    def run(self):
        while self.running:
            time.sleep(0.015)  # Tuning point
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
                    if self.img_process_model == "YOLOv8":
                        pen_color = QColor(173, 255, 47)  # Green
                    elif self.img_process_model == "TFLite":
                        pen_color = QColor(0, 0, 255)  # Blue
                    elif self.img_process_model == "OpenCV":
                        pen_color = QColor(255, 0, 0)  # Red
                    else:
                        pen_color = QColor(173, 255, 47)  # Default Green
                    # Draw boxes from box_info
                    try:                      
                        result_data = box_queue.get_nowait()
                        self.prev_data = result_data.copy()
                    except Empty:
                        result_data = self.prev_data

                    for box_info in result_data:
                        x1, y1, x2, y2 = box_info['bbox']
                        label = box_info['label']
                        if label == "10":
                            pen_color = QColor(255, 0, 0)  # Red for hand
                            label_text = "hand"
                            painter.setPen(QPen(pen_color, 3))
                        else:
                            label_text = label
                            painter.setPen(QPen(pen_color, 2))

                        # Draw the bounding box
                        painter.drawRect(x1, y1, x2 - x1, y2 - y1)

                        # Set font for the label
                        font = QFont()
                        font.setBold(True)
                        font.setPixelSize(12)
                        painter.setFont(font)

                        # Draw label background
                        label_size = painter.fontMetrics().size(0, label_text)
                        painter.setBrush(QColor(255, 255, 255))
                        painter.drawRect(x1, y1 - label_size.height() - 4, label_size.width() + 4, label_size.height() + 4)
                        painter.setBrush(Qt.NoBrush)  # Reset brush to no brush

                        # Draw label text
                        painter.setPen(QColor(0, 0, 0))  # Black text
                        painter.drawText(x1 + 2, y1 - 2, label_text)
                    painter.end()
                    self.image_processed.emit(pixmap)

                self.image_data = None

    def stop(self):
        self.running = False
        self.wait()
        print("Image processing UI thread is closed successfully.")


