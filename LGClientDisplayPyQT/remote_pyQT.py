import sys
import zmq
import threading
import struct
import cv2
import re
import numpy as np
from PyQt5.QtWidgets import QApplication, QMainWindow, QPushButton, QCheckBox, QLabel, QLineEdit, QTextEdit, QVBoxLayout, QGridLayout, QWidget, QMessageBox
from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtCore import pyqtSlot, Qt, QTimer, QMetaObject, Q_ARG
from PyQt5.QtGui import QIntValidator
from usermodel.usermodel import UserModel
from tcp_protocol import sendMsgToCannon, set_uimsg_update_callback
from common import common_start
from queue import Queue

# Define robotcontrolsw(RCV) state types
ST_UNKNOWN      = 0x00
ST_SAFE         = 0x01
ST_PREARMED     = 0x02
ST_ENGAGE_AUTO  = 0x04
ST_ARMED_MANUAL = 0x08
ST_ARMED        = 0x10
ST_FIRING       = 0x20      
ST_LASER_ON     = 0x40
ST_CALIB_ON     = 0x80
ST_CLEAR_LASER_MASK  = (~ST_LASER_ON)
ST_CLEAR_FIRING_MASK = (~ST_FIRING)
ST_CLEAR_ARMED_MASK  = (~ST_ARMED)
ST_CLEAR_CALIB_MASK  = (~ST_CALIB_ON)
ST_CLEAR_LASER_FIRING_ARMED_CALIB_MASK = (~(ST_LASER_ON|ST_FIRING|ST_ARMED|ST_CALIB_ON))

# Define message types
MT_COMMANDS = 1
MT_TARGET_SEQUENCE = 2
MT_IMAGE = 3
MT_TEXT = 4
MT_PREARM = 5
MT_STATE = 6
MT_STATE_CHANGE_REQ = 7
MT_CALIB_COMMANDS = 8
MT_ERROR = 9
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
CT_SAFE_TEST = 0xFF

# error code
ERR_SUCCESS = 0
ERR_FAIL_TO_CONNECT = 1
ERR_CONNECTION_LOST = 2

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
    prearm_code = "12345678" # temporarily code
    engage_order = "0123456789" # temporarily order

    def __init__(self):
        super().__init__()

        # Model : user_model is inserted from sub-directory config.ini file
        self.user_model = UserModel()
        print(self.user_model)

        self.setWindowTitle("Form1")
        self.setGeometry(100, 100, 1024, 768)  # Adjusted size to fit more controls

        self.initUI()

        self.recv_callback = None
        self.send_command_callback = None

        # 타이머 설정
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.HeartBeatTimer_event)
        # self.timer.start(1000)  # 1000 밀리초 = 1초

        # # tcp_thread용 frame queue 정의
        # self.frame_queue = Queue(maxsize=20)  # Frame queue

        self.show()

    def initUI(self):
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        layout = QGridLayout()

        intValidator = QIntValidator()

        # Controls
        self.labelIPAddress = QLabel("IP Address:", self)
        self.editIPAddress = QLineEdit(self)
        self.editIPAddress.setText(self.user_model.ip)
        self.editIPAddress.textChanged.connect(self.validCheckIpAndPort)

        self.labelTCPPort = QLabel("TCP Port:", self)
        self.editTCPPort = QLineEdit(self)
        self.editTCPPort.setValidator(intValidator)
        self.editTCPPort.setText(self.user_model.port)
        self.editTCPPort.textChanged.connect(self.validCheckIpAndPort)

        self.buttonConnect = QPushButton("Connect", self)
        self.buttonConnect.setEnabled(False)
        self.buttonDisconnect = QPushButton("Disconnect", self)
        self.buttonDisconnect.setEnabled(False)

        self.labelPreArmCode = QLabel("Pre-Arm Code:", self)
        self.editPreArmCode = QLineEdit(self)
        self.editPreArmCode.setText(self.prearm_code)
        self.editPreArmCode.setEnabled(False)
        # self.editPreArmCode.setFocusPolicy(Qt.NoFocus)  # Prevent focus
        self.editPreArmCode.setValidator(intValidator)
        self.editPreArmCode.textChanged.connect(self.validCheckPreArmedCode)
        self.buttonPreArmEnable = QPushButton("Pre-Arm Enable", self)
        self.buttonPreArmEnable.setEnabled(False)

        self.checkBoxArmedManualEnable = QCheckBox("Armed Manual", self)
        self.checkBoxArmedManualEnable.setEnabled(False)
        self.checkBoxLaserEnable = QCheckBox("Laser Enabled", self)
        self.checkBoxLaserEnable.setEnabled(False)

        self.labelEngageOrder = QLabel("Engage Order:", self)
        self.editEngageOrder = QLineEdit(self)
        self.editEngageOrder.setEnabled(False)
        self.editEngageOrder.setText(self.engage_order)
        #  self.editEngageOrder.setFocusPolicy(Qt.NoFocus)  # Prevent focus
        self.editEngageOrder.setValidator(intValidator)
        self.editEngageOrder.textChanged.connect(self.validCheckEngageOrder)

        self.checkBoxAutoEngage = QCheckBox("Auto Engage", self)
        self.checkBoxAutoEngage.setEnabled(False)
        self.checkBoxCalibrate = QCheckBox("Calibrate", self)
        self.checkBoxCalibrate.setEnabled(False)
        
        self.labelState = QLabel("System State:", self)
        self.editState = QLineEdit(self)
        self.editState.setFocusPolicy(Qt.NoFocus)  # Prevent focus
        # self.editState.setReadOnly(True)
        
        self.pictureBox = QLabel(self)
        self.pictureBox.setFixedSize(720, 540)  # Adjust size to 3/4 of the original

        self.logBox = QTextEdit(self)
        self.logBox.setReadOnly(True)
        self.logBox.setFixedHeight(100)  # Adjust height to fit approximately 5 messages

        # Adding controls to layout
        layout.addWidget(self.labelIPAddress, 0, 0)
        layout.addWidget(self.editIPAddress, 0, 1)
        layout.addWidget(self.labelTCPPort, 0, 2)
        layout.addWidget(self.editTCPPort, 0, 3)
        layout.addWidget(self.buttonConnect, 0, 4)
        layout.addWidget(self.buttonDisconnect, 0, 5)

        layout.addWidget(self.labelPreArmCode, 1, 0)
        layout.addWidget(self.editPreArmCode, 1, 1)
        layout.addWidget(self.buttonPreArmEnable, 1, 2)
        layout.addWidget(self.labelState, 1, 3)
        layout.addWidget(self.editState, 1, 4)

        layout.addWidget(self.checkBoxArmedManualEnable, 2, 0)
        layout.addWidget(self.checkBoxLaserEnable, 2, 1)
        layout.addWidget(self.labelEngageOrder, 2, 2)
        layout.addWidget(self.editEngageOrder, 2, 3)
        layout.addWidget(self.checkBoxAutoEngage, 2, 4)
        layout.addWidget(self.checkBoxCalibrate, 2, 5)
        
        # PictureBox to fill the remaining space
        layout.addWidget(self.pictureBox, 3, 0, 1, 6, alignment=Qt.AlignCenter)
        # LogBox at the bottom
        layout.addWidget(self.logBox, 4, 0, 1, 6)

        self.central_widget.setLayout(layout)

        # Connect buttons to their slots
        self.buttonConnect.clicked.connect(self.connect)
        self.buttonDisconnect.clicked.connect(self.disconnect)
        self.buttonPreArmEnable.clicked.connect(self.pre_arm_enable)
        self.checkBoxLaserEnable.clicked.connect(self.toggle_laser)
        self.checkBoxArmedManualEnable.clicked.connect(self.toggle_armed_manual)
        self.checkBoxCalibrate.clicked.connect(self.toggle_calib)
        self.checkBoxAutoEngage.clicked.connect(self.toggle_auto_engage)
        
        self.log_message("Init Start...")
        self.setInitialValue()
        self.updateSystemState()

        # Set focus on the main window
        self.setFocus()

    # def set_recv_callback(self, callback):
    #     self.recv_callback = callback

    # def set_send_command_callback(self, callback):
    #     self.send_command_callback = callback

    def setInitialValue(self):
        self.setAllUIEnabled(False, False)
        self.editIPAddress.setText(self.user_model.ip)
        self.editTCPPort.setText(self.user_model.port)


    def validCheckIpAndPort(self,text): 
        self.buttonConnect.setEnabled(False)

        ip = self.editIPAddress.text()
        port = self.editTCPPort.text()

        if not ip:
             self.log_message(f'Please enter ip address.')
        elif not port:
             self.log_message(f'Please enter port number.')
        elif not self.check_ipv4(ip) :
             self.log_message(f'Not mache IP Address Pattern.')
        elif not self.check_port(port) :
             self.log_message(f'Port must be 0-65535..')
        else:
             self.buttonConnect.setEnabled(True)


    def validCheckPreArmedCode(self,code):
        if code:
            self.buttonPreArmEnable.setEnabled(True)
        else:
            self.log_message(f"Please enter preArmedCode")

    def validCheckEngageOrder(self,order):
        if order:
            self.checkBoxAutoEngage.setEnabled(True)
        else :
            self.log_message(f"Please enter engageOrders")

    def check_port(self, port):
        pattern = r'^(?:[1-9]\d{0,3}|0)$'
        return bool(re.match(pattern, port))
    

    def check_ipv4(self,ip):
        ipv4_pattern = r'^((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$'
        if re.match(ipv4_pattern, ip):
            return True
        else:
            return False
    
    @pyqtSlot()
    def connect(self):
        ip = self.editIPAddress.text()
        port = int(self.editTCPPort.text())
        self.log_message(f"Connecting to {ip}:{port}")

        if hasattr(self, 'tcp_thread') and self.tcp_thread.is_alive():
            self.log_message("Already connected, disconnect first.")
            return

        self.tcp_thread = threading.Thread(target=common_start, args=(ip, port))
        self.tcp_thread.start()
        self.log_message("Connected")
        
        self.user_model.save_to_config(ip, port)
        self.setAllUIEnabled(True, False)

    def setAllUIEnabled(self, connected, preArmed):
        if not connected:
            self.checkBoxAutoEngage.setChecked(False)
            self.checkBoxCalibrate.setChecked(False)
            self.checkBoxArmedManualEnable.setChecked(False)
            self.checkBoxLaserEnable.setChecked(False)

        self.editIPAddress.setEnabled(False if connected else True)
        self.editTCPPort.setEnabled(False if connected else True)
        self.buttonConnect.setEnabled(False if connected else True)

        self.buttonDisconnect.setEnabled(True if connected else False)
        self.editPreArmCode.setEnabled(True if connected else False)

        self.buttonPreArmEnable.setEnabled(False if preArmed else True)
        self.checkBoxArmedManualEnable.setEnabled(True if preArmed else False)
        self.checkBoxLaserEnable.setEnabled(True if preArmed else False)
        self.editEngageOrder.setEnabled(True if preArmed else False)
        self.checkBoxAutoEngage.setEnabled(True if preArmed else False)
        self.checkBoxCalibrate.setEnabled(True if preArmed else False)

    @pyqtSlot()
    def disconnect(self):
        self.log_message("Disconnected")

        if hasattr(self, 'tcp_thread') and self.tcp_thread.is_alive():
            # self.frame_queue.put(None)  # Signal the thread to stop
            self.tcp_thread.join()
            self.log_message("Disconnected")
        
        self.setAllUIEnabled(False, False)

    @pyqtSlot()
    def pre_arm_enable(self):
        self.log_message("Pre-Arm Enable clicked")
        # self.send_state_change_request_to_server(ST_SAFE)

        if isinstance(self.RcvState_Curr, bytes):
            state_int = int.from_bytes(self.RcvState_Curr, byteorder='little')
        else:
            state_int = self.RcvState_Curr

        print("Current State : ", (state_int & ST_CLEAR_LASER_FIRING_ARMED_CALIB_MASK), " ")

        # if ((state_int & ST_CLEAR_LASER_FIRING_ARMED_CALIB_MASK) == ST_SAFE):
        self.log_message("Send Pre-Arm Enable")
        
        char_array = self.get_char_array_prearmed_from_text(self.editPreArmCode)
        self.send_pre_arm_code_to_server(char_array)
        
        self.RcvState_Curr = MT_PREARM
        self.updateSystemState()

        self.setAllUIEnabled(True, True)

        # else:
        #     self.log_message("Send Pre-Arm Disable")
        #     self.send_state_change_request_to_server(ST_SAFE)

    @pyqtSlot()
    def toggle_laser(self):
        self.log_message(f"Laser Enabled: {self.checkBoxLaserEnable.isChecked()}")
        if (self.checkBoxLaserEnable.isChecked() == True):
            self.RcvState_Curr |= ST_LASER_ON
            self.send_state_change_request_to_server(self.RcvState_Curr)
        else:
            self.RcvState_Curr &= ST_CLEAR_LASER_MASK
            self.send_state_change_request_to_server(ST_SAFE)
    
    @pyqtSlot()
    def toggle_armed_manual(self):
        self.log_message(f"Armed Manual Enabled: {self.checkBoxArmedManualEnable.isChecked()}")
        if (self.checkBoxArmedManualEnable.isChecked() == True):
            self.send_state_change_request_to_server(ST_ARMED_MANUAL)
        else:
            self.send_state_change_request_to_server(ST_PREARMED)   
            
    @pyqtSlot()
    def toggle_auto_engage(self):
        self.log_message(f"Auto Engage Enabled: {self.checkBoxArmedManualEnable.isChecked()}")
        if (self.checkBoxAutoEngage.isChecked() == True):
            engageOrder = self.editEngageOrder.text

            if not engageOrder:
                self.log_message(f"Please enter engageOrders")
            else:
                char_array = self.get_char_array_autoengage_from_text(self.editEngageOrder)
                self.send_target_order_to_server(char_array)

            self.send_state_change_request_to_server(ST_ENGAGE_AUTO)
        else:
            self.send_state_change_request_to_server(ST_PREARMED)  

    @pyqtSlot()
    def toggle_calib(self):
        if(self.checkBoxCalibrate.isChecked() == True):
            RcvState_Curr |= ST_CALIB_ON
            self.sensend_state_change_request_to_server(RcvState_Curr)
            self.updateSystemState()
        else:
            RcvState_Curr &= ST_CLEAR_CALIB_MASK
            self.sensend_state_change_request_to_server(RcvState_Curr)
            self.updateSystemState()
    
    
    ########################################################################
    # MT_COMMANDS 전송
    def set_command(self, command):
        # Define the message length and type
        msg_len = struct.calcsize("B")
        msg_type = MT_COMMANDS  # Example message type : MT_COMMANDS = 1

        # Pack the message using the same structure as C#'s TMessageCommands
        message = struct.pack(">IIB", msg_len, msg_type, command) #make by big
        print("set_command msg ", struct.unpack(">IIB", message)[1])
        # Get only msg_type
        unpacked_msg_type = struct.unpack(">IIB", message)[1] #read by little
        self.log_message(f"msg_type: {unpacked_msg_type}")
        # self.log_message(f"msg_command", struct.unpack(">IIB", message)[2]) #read by little

        # Other class example 
        sendMsgToCannon(message)
        self.log_message(f"Set command: {command}")

    ########################################################################
    # Client Socket 연결상태 전송 (업데이트)
    def is_client_connected(self):
        # 클라이언트 연결 상태를 확인하는 함수
        return True  # 예시로 True 반환, 실제로는 연결 상태를 확인하는 코드 필요

    ########################################################################
    # MT_CALIB_COMMANDS 전송
    def send_calib_to_server(self, code):
        if self.is_client_connected():
            msg_len = struct.calcsize(">II") + struct.calcsize(">B")
            msg = struct.pack(">II", struct.calcsize(">B"), MT_CALIB_COMMANDS)
            msg += struct.pack(">B", code)
            sendMsgToCannon(msg)
            return True
        return False

    ########################################################################
    # MT_TARGET_SEQUENCE 전송
    def get_char_array_autoengage_from_text(self, line_edit):
        text = line_edit.text()[:10]  # 최대 11자까지 자르기
        char_array = bytearray(11)  # 11자 + 널 문자('\0')

        # 문자열을 byte 배열에 복사
        for i, c in enumerate(text):
            char_array[i] = ord(c)

        # 널 문자('\0') 추가
        char_array[len(text)] = 0

        print("get_char_array_autoengage_from_text to cannon", char_array, " ", len(char_array))

        return char_array
    
    ########################################################################
    # MT_TARGET_SEQUENCE 전송
    def send_target_order_to_server(self, target_order):
        if self.is_client_connected():
            msg_len = struct.calcsize(">II") + len(target_order)
            msg = struct.pack(">II", len(target_order) - 1, MT_TARGET_SEQUENCE)  # 길이 조정
            msg = bytearray(msg)  # msg를 bytearray로 변환

            # code의 각 바이트를 msg에 추가
            for byte in target_order:
                msg.append(byte)

            sendMsgToCannon(msg)
            return True
        return False

    ########################################################################
    # MT_PREARM 암호 생성
    def get_char_array_prearmed_from_text(self, line_edit):
        text = line_edit.text()[:8]  # 최대 8자까지 자르기
        char_array = bytearray(9)  # 8자 + 널 문자('\0')

        # 문자열을 byte 배열에 복사
        for i, c in enumerate(text):
            char_array[i] = ord(c)

        # 널 문자('\0') 추가
        char_array[len(text)] = 0

        print("get_char_array_prearmed_from_text to cannon", char_array, " ", len(char_array))
        return char_array
    
    ########################################################################
    # MT_PREARM 암호 전송
    def send_pre_arm_code_to_server(self, code):
        if self.is_client_connected():
            msg_len = struct.calcsize(">II") + len(code)
            msg = struct.pack(">II", len(code) - 1, MT_PREARM)  # 길이 조정
            msg = bytearray(msg)  # msg를 bytearray로 변환

            # code의 각 바이트를 msg에 추가
            for byte in code:
                msg.append(byte)

            # print("send_pre_arm_code_to_server ", msg)
            print("send_pre_arm_code_to_server ", ' '.join(f'0x{byte:02x}' for byte in msg))
            sendMsgToCannon(bytes(msg))
            return True
        return False

    ########################################################################
    # MT_STATE_CHANGE_REQ 전송
    def send_state_change_request_to_server(self, state):
        if self.is_client_connected():
            msg_len = struct.calcsize(">II") + struct.calcsize(">I")
            msg = struct.pack(">II", struct.calcsize(">I"), MT_STATE_CHANGE_REQ) # make by big
            msg += struct.pack(">I", state)
            sendMsgToCannon(msg)
            return True
        return False

    ########################################################################
    # log message textbox 출력
    def log_message(self, message):
        self.logBox.append(message)
        self.logBox.ensureCursorVisible()
        QApplication.processEvents()  # Process events to update UI

    ########################################################################
    # Update Current System State
    def updateSystemState(self):
        self.log_message("Called updateSystemState Function!!")
        if isinstance(self.RcvState_Curr, bytes):
            state_int = int.from_bytes(self.RcvState_Curr, byteorder='little')
        else:
            state_int = self.RcvState_Curr

        if (state_int & ST_CLEAR_LASER_FIRING_ARMED_CALIB_MASK) == ST_UNKNOWN:
            self.editState.setText("UNKNOWN")
            self.log_message("MT_STATE : UNKNOWN")
        elif (state_int & ST_CLEAR_LASER_FIRING_ARMED_CALIB_MASK) == ST_SAFE:
            self.editState.setText("SAFE")
            self.log_message("MT_STATE : SAFE")
        elif (state_int & ST_CLEAR_LASER_FIRING_ARMED_CALIB_MASK) == ST_PREARMED:
            self.editState.setText("PREARMED")
            self.log_message("MT_STATE : PREARMED")
        elif (state_int & ST_CLEAR_LASER_FIRING_ARMED_CALIB_MASK) == ST_ENGAGE_AUTO:
            self.editState.setText("MT_STATE : ENGAGE_AUTO")
            # self.log_message("ENGAGE_AUTO")
        elif (state_int & ST_CLEAR_LASER_FIRING_ARMED_CALIB_MASK) == ST_ARMED_MANUAL:
            self.editState.setText("MT_STATE : ARMED_MANUAL") 
            # self.log_message("ARMED_MANUAL")
        elif (state_int & ST_CLEAR_LASER_FIRING_ARMED_CALIB_MASK) == ST_ARMED:
            self.editState.setText("MT_STATE : ARMED") 
            #  self.log_message("ARMED")
        else:
            self.editState.setText("MT_STATE : GGGG") 
            # self.log_message(f"GGGG")

    ###################################################################
    # callback_msg 처리할때 MT 메시지 종류에 따라 차등 처리 기능 구현
    ###################################################################
    def callback_msg(self, message):
        # # check little and big endians
        # len_, type_, rcv_state_ = struct.unpack('<III', message[:12])
        # # rcv_state = self.process_message_little_endian(message)
        # self.log_message(f"Based on little endian, Received: {len_, type_, rcv_state_}")
        # len_, type_, rcv_state_ = struct.unpack('>III', message[:12])
        # self.log_message(f"Based on big endian, Received: {len_, type_, rcv_state_}")
        # unpacked_msg_type = struct.unpack(">IIB", message)[1] #read by little

        # Unpack the message header
        len = message[0:4]
        len = int.from_bytes(len, byteorder='big')
        type = message[4:8]
        type = int.from_bytes(type, byteorder='big')
        print(f"Message Received, size: {len}")

        # MT_IMAGE는 tcp_protocol에서 직접 보내주므로 little로 변환된 데이터 수신
        if type == MT_IMAGE:
            # print test
            print("MT_IMAGE Received")

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

        # 나머지 MT_MSG 들은 byte 배열이 들어오므로 bit -> little 변환이 필요함, 송신도 마찬가지
        elif type == MT_STATE:
            # print test
            print("MT_STATE Received")

            # Buffer to store the received message
            # rcv_state = bytearray(len)
            # rcv_state = message[8:len+7]
            # rcv_state = int.from_bytes(rcv_state, byteorder='big')
            rcv_state = struct.unpack(">III", message)[2]
            self.RcvState_Curr = rcv_state
            print("MT_STATE Received as", self.RcvState_Curr, " ", rcv_state)
            self.updateSystemState()
            if self.RcvState_Curr != self.RcvState_Prev:
                self.RcvState_Prev = self.RcvState_Curr

        elif type == MT_ERROR:
            # print test
            print("MT_ERROR Received", type)

    # ###################################################################
    # # callback 함수를 통해 수신받은 메시지의 endian 구조를 파악
    # ###################################################################
    # def process_message_little_endian(message):
    #     if len(message) != 12:
    #         raise ValueError("Message must be 12 bytes long")

    #     # 4바이트 len, 4바이트 type, 4바이트 rcv_state를 little endian 방식으로 해석
    #     len_, type_, rcv_state = struct.unpack('<III', message[:12])

    #     if type_ == MT_STATE:
    #         # rcv_state를 저장
    #         print(f"Received state (little endian): {rcv_state}")
    #         return rcv_state
    #     else:
    #         print("Received non-state message")
    #         return None

    # def process_message_big_endian(message):
    #     if len(message) != 12:
    #         raise ValueError("Message must be 12 bytes long")

    #     # 4바이트 len, 4바이트 type, 4바이트 rcv_state를 big endian 방식으로 해석
    #     len_, type_, rcv_state = struct.unpack('>III', message[:12])

    #     if type_ == MT_STATE:
    #         # rcv_state를 저장
    #         print(f"Received state (big endian): {rcv_state}")
    #         return rcv_state
    #     else:
    #         print("Received non-state message")
    #         return None

    # Using heartbeat timer, in order to detect the robot control sw to set abnormal state
    def HeartBeatTimer_event(self):
        self.log_message("Timer event: sending message to cannon")

    def keyPressEvent(self, event):
        key_map = {
            Qt.Key_I: CT_PAN_UP_START,
            Qt.Key_Up: CT_PAN_UP_START,
            Qt.Key_L: CT_PAN_RIGHT_START,
            Qt.Key_Right: CT_PAN_RIGHT_START,
            Qt.Key_J: CT_PAN_LEFT_START,
            Qt.Key_Left: CT_PAN_LEFT_START,
            Qt.Key_M: CT_PAN_DOWN_START,
            Qt.Key_Down: CT_PAN_DOWN_START,
            Qt.Key_F: CT_FIRE_START,
            Qt.Key_Return: CT_FIRE_START,
            Qt.Key_S: CT_SAFE_TEST
        }

        # if self.RcvState_Curr == ST_ARMED_MANUAL: 
        if event.key() in key_map:
            if key_map[event.key()] != CT_SAFE_TEST:
                self.set_command(key_map[event.key()])
            elif key_map[event.key()] == CT_SAFE_TEST:
                self.send_state_change_request_to_server(ST_SAFE)

    def keyReleaseEvent(self, event):
        key_map = {
            Qt.Key_I: CT_PAN_UP_STOP,
            Qt.Key_Up: CT_PAN_UP_STOP,
            Qt.Key_L: CT_PAN_RIGHT_STOP,
            Qt.Key_Right: CT_PAN_RIGHT_STOP,
            Qt.Key_J: CT_PAN_LEFT_STOP,
            Qt.Key_Left: CT_PAN_LEFT_STOP,
            Qt.Key_M: CT_PAN_DOWN_STOP,
            Qt.Key_Down: CT_PAN_DOWN_STOP,
            Qt.Key_F: CT_FIRE_STOP,
            Qt.Key_Return: CT_FIRE_STOP
        }

        # if self.RcvState_Curr == ST_ARMED_MANUAL: 
        if event.key() in key_map:
            self.set_command(key_map[event.key()])

if __name__ == "__main__":
    app = QApplication(sys.argv)
    mainWin = Form1()

    # Set the callback function for image update
    set_uimsg_update_callback(mainWin.callback_msg)

    mainWin.show()
    sys.exit(app.exec_())