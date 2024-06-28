# image_process_ui.py

from PyQt5.QtCore import QThread, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QPixmap, QImage, QPainter, QPen, QColor
import cv2
import numpy as np
from image_process import get_result_model
from image_algo.kalman_filter import KalmanBoxTracker
import time

class ImageProcessingThread(QThread):
    image_processed = pyqtSignal(QPixmap)

    def __init__(self, parent=None):
        super().__init__(parent)
        # self.shutdown_event = shutdown_event
        self.image_data = None
        self.rcv_state_curr = None
        self.running = True
        self.trackers = {}

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
            time.sleep(0.05) # Tunning point
        # while not self.shutdown_event.is_set():
            if self.image_data is not None:
                np_arr = np.frombuffer(self.image_data, np.uint8)
                img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
                
                if img is not None:
                    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                    h, w, ch = img_rgb.shape
                    bytes_per_line = ch * w
                    qt_image = QImage(img_rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
                    pixmap = QPixmap.fromImage(qt_image)

                    # # Add red cross hair in pixmap
                    painter = QPainter(pixmap)
                    pen = QPen(QColor(255, 0, 0), 2)
                    painter.setPen(pen)
                    center_x = w // 2
                    center_y = h // 2
                    half_size = 30  # Change the crosshair size if needed
                    painter.drawLine(center_x - half_size, center_y, center_x + half_size, center_y)
                    painter.drawLine(center_x, center_y - half_size, center_x, center_y + half_size)

                    # Draw boxes from box_info
                    result_data = get_result_model()
                    if result_data and 'box_info' in result_data:
                        box_info_list = result_data['box_info']
                        for i, box_info in enumerate(box_info_list):
                            x1, y1, x2, y2 = box_info['bbox']
                            label = box_info['label']
                            width = x2 - x1
                            height = y2 - y1

                            if label not in self.trackers:
                                self.trackers[label] = KalmanBoxTracker()

                            tracker = self.trackers[label]
                            target_info = result_data['target_info'][i]
                            t_center_x, t_center_y = target_info['center']

                            # Į�� ���� ������Ʈ �� ����
                            tracker.update(np.array([t_center_x, t_center_y]))
                            predicted_center = tracker.predict()

                            px1 = int(predicted_center[0] - width / 2)
                            py1 = int(predicted_center[1] - height / 2)
                            px2 = int(predicted_center[0] + width / 2)
                            py2 = int(predicted_center[1] + height / 2)

                            painter.setPen(QPen(QColor(173, 255, 47), 3))
                            painter.drawRect(px1, py1, px2 - px1, py2 - py1)
                            painter.setPen(QPen(QColor(173, 255, 47), 3))
                            painter.drawText(px1, py1 - 5, label)
                            painter.setPen(QPen(QColor(255, 0, 0), 3))
                            # painter.drawEllipse(int(predicted_center[0]) - 3, int(predicted_center[1]) - 3, 6, 6)
                          
                    painter.end()

                    self.image_processed.emit(pixmap)
                self.image_data = None
                # print("Image processing thread stopped.")

    def update_image_data(self, image_data):
        self.image_data = image_data

    def stop(self):
        self.running = False
        self.wait()
        print("Image processing UI thread is closed successfully.")