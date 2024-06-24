# image_process_ui.py

from PyQt5.QtCore import QThread, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QPixmap, QImage, QPainter, QPen, QColor
import cv2
import numpy as np

class ImageProcessingThread(QThread):
    image_processed = pyqtSignal(QPixmap)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.image_data = None
        self.running = True

    def run(self):
        while self.running:
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
                    painter.end()

                    self.image_processed.emit(pixmap)
                self.image_data = None

    def update_image_data(self, image_data):
        self.image_data = image_data

    def stop(self):
        self.running = False
        self.wait()