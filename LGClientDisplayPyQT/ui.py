import sys
import socket
import threading
import struct
import cv2
from PyQt5.QtWidgets import QApplication, QMainWindow, QPushButton, QCheckBox, QLabel, QLineEdit, QTextEdit, QVBoxLayout, QWidget, QMessageBox
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import pyqtSlot, Qt
from PIL import Image, ImageQt

class Form1(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Form1")
        self.setGeometry(100, 100, 620, 600)

        self.initUI()

        self.client = None
        self.client_thread = None
        self.end_client_event = threading.Event()

        self.remote_address = "192.168.0.224"
        self.remote_addr_port = 5000

    def initUI(self):
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        layout = QVBoxLayout()

        self.pictureBox = QLabel(self)
        self.pictureBox.setFixedSize(480, 360)

        self.buttonConnect = QPushButton("Connect", self)
        self.buttonDisconnect = QPushButton("Disconnect", self)
        self.buttonPreArmSafe = QPushButton("Pre-Arm Safe", self)

        self.checkBoxArmedManual = QCheckBox("Armed Manual", self)
        self.checkBoxLaserEnable = QCheckBox("Laser Enable", self)
        self.checkBoxAutoEngage = QCheckBox("Auto Engage", self)
        self.checkBoxCalibrate = QCheckBox("Calibrate", self)

        self.labelEngageOrder = QLabel("Engage Order:", self)
        self.editEngageOrder = QLineEdit(self)

        self.labelPreArmCode = QLabel("Pre-Arm Code:", self)
        self.editPreArmCode = QLineEdit(self)

        self.btnUpIncY = QPushButton("Up", self)
        self.btnLeftDecX = QPushButton("Left", self)
        self.btnDownDecY = QPushButton("Down", self)
        self.btnRightIncX = QPushButton("Right", self)
        self.btnFire = QPushButton("Fire", self)
        self.btnFireCancel = QPushButton("Cancel Fire", self)

        self.logBox = QTextEdit(self)
        self.logBox.setReadOnly(True)

        layout.addWidget(self.pictureBox)
        layout.addWidget(self.buttonConnect)
        layout.addWidget(self.buttonDisconnect)
        layout.addWidget(self.buttonPreArmSafe)
        layout.addWidget(self.checkBoxArmedManual)
        layout.addWidget(self.checkBoxLaserEnable)
        layout.addWidget(self.checkBoxAutoEngage)
        layout.addWidget(self.checkBoxCalibrate)
        layout.addWidget(self.labelEngageOrder)
        layout.addWidget(self.editEngageOrder)
        layout.addWidget(self.labelPreArmCode)
        layout.addWidget(self.editPreArmCode)
        layout.addWidget(self.btnUpIncY)
        layout.addWidget(self.btnLeftDecX)
        layout.addWidget(self.btnDownDecY)
        layout.addWidget(self.btnRightIncX)
        layout.addWidget(self.btnFire)
        layout.addWidget(self.btnFireCancel)
        layout.addWidget(self.logBox)

        self.central_widget.setLayout(layout)

        self.buttonConnect.clicked.connect(self.start_client)
        self.buttonDisconnect.clicked.connect(self.stop_client)
        self.buttonPreArmSafe.clicked.connect(self.pre_arm_safe)

        self.btnUpIncY.clicked.connect(lambda: self.send_command(0x04))
        self.btnLeftDecX.clicked.connect(lambda: self.send_command(0x01))
        self.btnDownDecY.clicked.connect(lambda: self.send_command(0x08))
        self.btnRightIncX.clicked.connect(lambda: self.send_command(0x02))
        self.btnFire.clicked.connect(lambda: self.send_command(0x10))
        self.btnFireCancel.clicked.connect(lambda: self.send_command(0xEF))

    @pyqtSlot()
    def start_client(self):
        self.log_message("Client started")
        self.end_client_event.clear()
        self.client_thread = threading.Thread(target=self.client_thread_proc)
        self.client_thread.start()

    @pyqtSlot()
    def stop_client(self):
        self.log_message("Client stopped")
        self.end_client_event.set()
        if self.client_thread:
            self.client_thread.join()
            self.client_thread = None
        self.client_cleanup()

    @pyqtSlot()
    def pre_arm_safe(self):
        QMessageBox.information(self, "Info", "Pre-Arm Safe button clicked.")

    def send_command(self, command):
        if self.client and self.client.fileno() != -1:
            msg = struct.pack("IIB", 7, 1, command)  # Message length, type, command
            self.client.send(msg)
            self.log_message(f"Sent command: {command}")

    def client_cleanup(self):
        if self.client:
            self.client.shutdown(socket.SHUT_RDWR)
            self.client.close()
            self.client = None

    def client_thread_proc(self):
        try:
            self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client.connect((self.remote_address, self.remote_addr_port))
            while not self.end_client_event.is_set():
                data = self.client.recv(1024)
                if data:
                    self.process_data(data)
        except Exception as e:
            self.log_message(f"Client thread error: {e}")
        finally:
            self.client_cleanup()

    def process_data(self, data):
        header = struct.unpack("II", data[:8])
        msg_type = header[1]
        if msg_type == 3:  # Image
            self.process_image(data[8:])

    def process_image(self, data):
        np_arr = np.frombuffer(data, np.uint8)
        image = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        if image is not None:
            qt_image = ImageQt.ImageQt(Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB)))
            pixmap = QPixmap.fromImage(qt_image)
            self.pictureBox.setPixmap(pixmap)

    def log_message(self, message):
        self.logBox.append(message)
        self.logBox.ensureCursorVisible()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    mainWin = Form1()
    mainWin.show()
    sys.exit(app.exec_())