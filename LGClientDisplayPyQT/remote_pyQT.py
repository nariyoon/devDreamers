import sys
import zmq
import threading
import struct
import cv2
import numpy as np
from PyQt5.QtWidgets import QApplication, QMainWindow, QPushButton, QCheckBox, QLabel, QLineEdit, QTextEdit, QVBoxLayout, QWidget, QMessageBox
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import pyqtSlot, Qt
from PIL import Image, ImageQt
from tcp_protocol import sendMsgToCannon
from common import common_start

class Form1(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Form1")
        self.setGeometry(100, 100, 620, 600)

        self.initUI()

        self.recv_callback = None
        self.send_command_callback = None

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

        self.buttonConnect.clicked.connect(self.connect)
        self.buttonDisconnect.clicked.connect(self.disconnect)
        self.buttonPreArmSafe.clicked.connect(self.pre_arm_safe)

        self.btnUpIncY.clicked.connect(lambda: self.set_command(0x04))
        self.btnLeftDecX.clicked.connect(lambda: self.set_command(0x01))
        self.btnDownDecY.clicked.connect(lambda: self.set_command(0x08))
        self.btnRightIncX.clicked.connect(lambda: self.set_command(0x02))
        self.btnFire.clicked.connect(lambda: self.set_command(0x10))
        self.btnFireCancel.clicked.connect(lambda: self.set_command(0xEF))

        # For Test
        self.log_message("Init Start...")
        # lambda: self.set_command(0x01)
        common_thread = threading.Thread(target=common_start, args=())
        common_thread.start()

    def set_recv_callback(self, callback):
        self.recv_callback = callback

    def set_send_command_callback(self, callback):
        self.send_command_callback = callback

    @pyqtSlot()
    def connect(self):
        self.log_message("Connected")

    @pyqtSlot()
    def disconnect(self):
        self.log_message("Disconnected")

    @pyqtSlot()
    def pre_arm_safe(self):
        QMessageBox.information(self, "Info", "Pre-Arm Safe button clicked.")

    def set_command(self, command):
        if self.send_command_callback:
            self.send_command_callback(command)

        # def create_message(command):
        # Define the message length and type
        msg_len = struct.calcsize("B")
        msg_type = 1  # Example message type : MT_COMMANDS = 1

        # Pack the message using the same structure as C#'s TMessageCommands
        message = struct.pack("IIB", msg_len, msg_type, command)
        # msg_type만 얻기
        unpacked_msg_type = struct.unpack("IIB", message)[1]
        self.log_message(f"msg_type: {unpacked_msg_type}")

        # Other class example 
        sendMsgToCannon(message)
        self.log_message(f"Set command: {command}")

    def log_message(self, message):
        self.logBox.append(message)
        self.logBox.ensureCursorVisible()

    def update_image(self, image_data):
        np_arr = np.frombuffer(image_data, np.uint8)
        img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        if img is not None:
            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            qt_image = ImageQt.ImageQt(Image.fromarray(img_rgb))
            pixmap = QPixmap.fromImage(qt_image)
            self.pictureBox.setPixmap(pixmap)
            self.pictureBox.setScaledContents(True)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    mainWin = Form1()

    # Example callback functions
    def recv_callback(data):
        mainWin.update_image(data)

    def send_command_callback(command):

        mainWin.log_message(f"Command to send: {command}")

    # Set the callback functions
    mainWin.set_recv_callback(recv_callback)
    mainWin.set_send_command_callback(send_command_callback)

    mainWin.show()
    sys.exit(app.exec_())
