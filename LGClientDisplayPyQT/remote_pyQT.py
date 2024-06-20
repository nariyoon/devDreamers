import sys
import zmq
import threading
import struct
import cv2
import numpy as np
from PyQt5.QtWidgets import QApplication, QMainWindow, QPushButton, QCheckBox, QLabel, QLineEdit, QTextEdit, QVBoxLayout, QGridLayout, QWidget, QMessageBox
from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtCore import pyqtSlot, Qt, QTimer, QMetaObject, Q_ARG
from usermodel.usermodel import UserModel
from tcp_protocol import sendMsgToCannon, set_image_update_callback
from common import common_start
from queue import Queue

# Define robotcontrolsw(RCV) state types
ST_UNKNOWN = 1
ST_SAFE = 2
ST_PREARMED = 3
ST_MANUALARM = 4
ST_AUTOENGAGE = 5
ST_ALERT = 6

# Define message types
MT_COMMANDS = 1
MT_TARGET_SEQUENCE = 2
MT_IMAGE = 3
MT_TEXT = 4
MT_PREARM = 5
MT_STATE = 6
MT_STATE_CHANGE_REQ = 7
MT_CALIB_COMMANDS = 8
# MT_STATE_UPDATE_REQ = 9

# Define command types
CT_PAN_LEFT_START = 0x01
CT_PAN_RIGHT_START = 0x02
CT_PAN_UP_START = 0x04
CT_PAN_DOWN_START = 0x08
CT_FIRE_START = 0x10
CT_PAN_LEFT_STOP = 0xFE
CT_PAN_RIGHT_STOP = 0xFD
CT_PAN_UP_STOP = 0xFB
CT_PAN_DOWN_STOP = 0xF7
CT_FIRE_STOP = 0xEF


class Form1(QMainWindow):
    # Model : RcsState
    RcvState_Curr = ST_UNKNOWN
    RcvState_Prev = ST_UNKNOWN

    # Model : Prev. RecvMsg (Received total msg stored including TMessageHeader)
    RecvMsg_Command = '0x0'
    RecvMsg_Image = '0x0'
    RecvMsg_State = '0x0'

    # Model : user_model
    user_model = ""

    def __init__(self):
        super().__init__()

        # Model : user_model is inserted from sub-directory config.ini file
        self.user_model = UserModel()
        print(self.user_model)

        self.setWindowTitle("Form1")
        self.setGeometry(100, 100, 1000, 800)  # Adjusted size to fit more controls

        self.initUI()

        self.recv_callback = None
        self.send_command_callback = None

        # 타이머 설정
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.HeartBeatTimer_event)
        # self.timer.start(1000)  # 1000 밀리초 = 1초

        # tcp_thread용 frame queue 정의
        self.frame_queue = Queue(maxsize=20)  # Frame queue

    def initUI(self):
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        layout = QGridLayout()

        # Controls
        self.labelIPAddress = QLabel("IP Address:", self)
        self.editIPAddress = QLineEdit(self)
        self.editIPAddress.setText(self.user_model.ip)

        self.labelTCPPort = QLabel("TCP Port:", self)
        self.editTCPPort = QLineEdit(self)
        self.editTCPPort.setText(self.user_model.port)

        self.buttonConnect = QPushButton("Connect", self)
        self.labelState = QLabel("State:", self)
        self.editState = QLineEdit(self)
        self.editState.setReadOnly(True)

        self.checkBoxLaserEnable = QCheckBox("Laser Enabled", self)
        self.checkBoxCalibrate = QCheckBox("Calibrate", self)
        self.checkBoxAutoEngage = QCheckBox("Auto Engage", self)

        self.labelEngageOrder = QLabel("Engage Order:", self)
        self.editEngageOrder = QLineEdit(self)

        self.pictureBox = QLabel(self)

        self.logBox = QTextEdit(self)
        self.logBox.setReadOnly(True)
        self.logBox.setFixedHeight(100)  # Adjust height to fit approximately 5 messages

        # Adding controls to layout
        layout.addWidget(self.labelIPAddress, 0, 0)
        layout.addWidget(self.editIPAddress, 0, 1)
        layout.addWidget(self.labelTCPPort, 0, 2)
        layout.addWidget(self.editTCPPort, 0, 3)
        layout.addWidget(self.buttonConnect, 0, 4)
        layout.addWidget(self.labelState, 0, 5)
        layout.addWidget(self.editState, 0, 6)
        layout.addWidget(self.checkBoxLaserEnable, 0, 8)

        layout.addWidget(self.checkBoxCalibrate, 1, 8)
        layout.addWidget(self.checkBoxAutoEngage, 2, 8)
        layout.addWidget(self.labelEngageOrder, 3, 8)
        layout.addWidget(self.editEngageOrder, 4, 8)

        # Control buttons in a grid layout
        self.btnUp = QPushButton("Up", self)
        self.btnRight = QPushButton("Right", self)
        self.btnDown = QPushButton("Down", self)
        self.btnLeft = QPushButton("Left", self)
        self.btnFire = QPushButton("Fire", self)
        self.btnFireCancel = QPushButton("Fire Cancel", self)

        layout.addWidget(self.btnUp, 5, 7)
        layout.addWidget(self.btnRight, 6, 8)
        layout.addWidget(self.btnDown, 7, 7)
        layout.addWidget(self.btnLeft, 6, 6)
        layout.addWidget(self.btnFire, 6, 7)
        layout.addWidget(self.btnFireCancel, 8, 7)

        # PictureBox to fill the remaining space
        layout.addWidget(self.pictureBox, 1, 0, 4, 6)
        
        # LogBox at the bottom
        layout.addWidget(self.logBox, 9, 0, 1, 10)

        self.central_widget.setLayout(layout)

        # Connect buttons to their slots
        self.buttonConnect.clicked.connect(self.connect)
        self.checkBoxLaserEnable.clicked.connect(self.toggle_laser)

        self.btnUp.clicked.connect(lambda: self.set_command(CT_PAN_UP_START))
        self.btnRight.clicked.connect(lambda: self.set_command(CT_PAN_RIGHT_START))
        self.btnDown.clicked.connect(lambda: self.set_command(CT_PAN_DOWN_START))
        self.btnLeft.clicked.connect(lambda: self.set_command(CT_PAN_LEFT_START))
        self.btnFire.clicked.connect(lambda: self.set_command(CT_FIRE_START))
        self.btnFireCancel.clicked.connect(lambda: self.set_command(CT_FIRE_STOP))

        self.log_message("Init Start...")

        # # lambda: self.set_command(0x01)
        # common_thread = threading.Thread(target=common_start, args=())
        # common_thread.start()

    def set_recv_callback(self, callback):
        self.recv_callback = callback

    def set_send_command_callback(self, callback):
        self.send_command_callback = callback

    @pyqtSlot()
    def connect(self):
        ip = self.editIPAddress.text()
        port = int(self.editTCPPort.text())
        self.log_message(f"Connecting to {ip}:{port}")

        if hasattr(self, 'tcp_thread') and self.tcp_thread.is_alive():
            self.log_message("Already connected, disconnect first.")
            return

        self.tcp_thread = threading.Thread(target=common_start, args=(self.frame_queue, ip, port))
        self.tcp_thread.start()
        self.log_message("Connected")

    @pyqtSlot()
    def disconnect(self):
        self.log_message("Disconnected")

        if hasattr(self, 'tcp_thread') and self.tcp_thread.is_alive():
            self.frame_queue.put(None)  # Signal the thread to stop
            self.tcp_thread.join()
            self.log_message("Disconnected")

    @pyqtSlot()
    def pre_arm_safe(self):
        QMessageBox.information(self, "Info", "Pre-Arm Safe button clicked.")

    @pyqtSlot()
    def toggle_laser(self):
        self.log_message(f"Laser Enabled: {self.checkBoxLaserEnable.isChecked()}")

    def set_command(self, command):
        # if self.send_command_callback:
        #     self.send_command_callback(command)

        # def create_message(command):
        # Define the message length and type
        msg_len = struct.calcsize("B")
        msg_type = MT_COMMANDS  # Example message type : MT_COMMANDS = 1

        # Pack the message using the same structure as C#'s TMessageCommands
        message = struct.pack(">IIB", msg_len, msg_type, command)
        # Get only msg_type
        unpacked_msg_type = struct.unpack(">IIB", message)[1]
        self.log_message(f"msg_type: {unpacked_msg_type}")
        print("msg_command", struct.unpack(">IIB", message)[2])

        # Other class example 
        sendMsgToCannon(message)
        self.log_message(f"Set command: {command}")

    def log_message(self, message):
        self.logBox.append(message)
        self.logBox.ensureCursorVisible()
        # QMetaObject.invokeMethod(self.logBox, "append", Qt.QueuedConnection, Q_ARG(str, message))
        # QMetaObject.invokeMethod(self.logBox, "ensureCursorVisible", Qt.QueuedConnection)
        QApplication.processEvents()  # Process events to update UI

    def update_image(self, message):
        # Unpack the message header
        len = message[0:4]
        len = int.from_bytes(len, byteorder='little')
        type = message[4:8]
        type = int.from_bytes(type, byteorder='little')
        # self.log_message(f"msg_type: ", type, "msg_len:", len, "")
        self.log_message(f"Imag Received, size: {len}")

        if type == MT_IMAGE:
            # Buffer to store the received message
            image_data = bytearray(len)
            image_data = message[8:len+7]

            # Show the received image to picturebox
            np_arr = np.frombuffer(image_data, np.uint8)
            img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
            if img is not None:
                img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                h, w, ch = img_rgb.shape
                bytes_per_line = ch * w
                qt_image = QImage(img_rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
                pixmap = QPixmap.fromImage(qt_image)
                self.pictureBox.setPixmap(pixmap)
                self.pictureBox.setScaledContents(True)
                # QMetaObject.invokeMethod(self.pictureBox, "setPixmap", Qt.QueuedConnection, Q_ARG(QPixmap, pixmap))
                # QMetaObject.invokeMethod(self.pictureBox, "setScaledContents", Qt.QueuedConnection, Q_ARG(bool, True))

        elif type == MT_STATE:
            # Buffer to store the received message
            rcv_state = bytearray(len)
            rcv_state = message[8:len+7]
            self.RcvState_Curr = rcv_state
            if self.RcvState_Curr != self.RcvState_Prev:
                self.RcvState_Prev = self.RcvState_Curr

    # Using heartbeat timer, in order to detect the robot control sw to set abnormal state
    def HeartBeatTimer_event(self):
        # 1초에 한 번씩 호출되는 함수
        self.log_message("Timer event: sending message to cannon")
        # # 예제 메시지
        # msg_len = struct.calcsize("B")
        # msg_type = MT_STATE_CHANGE_REQ  # Example message type : MT_COMMANDS = 1
        # command = 0x00  # 예제 명령어
        # message = struct.pack("IIB", msg_len, msg_type, command)
        # # sendMsgToCannon(message)  # To Be Updated

if __name__ == "__main__":
    app = QApplication(sys.argv)
    mainWin = Form1()

    # Set the callback function for image update
    set_image_update_callback(mainWin.update_image)

    # # Example callback functions
    # def recv_callback(data):
    #     mainWin.update_image(data)

    # def send_command_callback(command):
    #     mainWin.log_message(f"Command to send: {command}")

    # # Set the callback functions
    # mainWin.set_recv_callback(recv_callback)
    # mainWin.set_send_command_callback(send_command_callback)

    mainWin.show()
    sys.exit(app.exec_())
