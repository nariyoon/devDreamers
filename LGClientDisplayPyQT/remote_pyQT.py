import sys
import zmq
import threading
import socket
import struct
import cv2
import re
from enum import Enum
import numpy as np
from PyQt5.QtWidgets import QApplication, QMainWindow, QPushButton, QCheckBox, QLabel, QLineEdit, QTextEdit, QVBoxLayout, QGridLayout, QWidget, QMessageBox
from PyQt5.QtGui import QPixmap, QIntValidator, QIcon, QMovie
from PyQt5.QtCore import pyqtSignal, pyqtSlot, Qt, QTimer, QMetaObject, Q_ARG # , qRegisterMetaType
from usermodel.usermodel import UserModel
from tcp_protocol import sendMsgToCannon, set_uimsg_update_callback
from common import common_start
from PyQt5 import uic
from queue import Queue
from image_process_ui import ImageProcessingThread
from image_process import init_image_processing_model
import os
# import qdarktheme // https://pypi.org/project/pyqtdarktheme/
from image_process import get_result_model

# O1 : 192.168.0.224
# S3 : 192.168.0.238

# from sip import qRegisterMetaType  # Import qRegisterMetaType from sip module

# # Register QTextCursor with QMetaType
# qRegisterMetaType(QTextCursor)

# Define robotcontrolsw(RCV) state types
ST_UNKNOWN           = 0x00
ST_SAFE              = 0x01
ST_PREARMED          = 0x02
ST_AUTO_ENGAGE       = 0x04
ST_ARMED_MANUAL      = 0x08
ST_ARMED             = 0x10
ST_FIRING            = 0x20      
ST_LASER_ON          = 0x40
ST_CALIB_ON          = 0x80
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
MT_TARGET_DIFF = 9
MT_SOCKET = 10
MT_COMPLETE = 11
MT_FIRE = 12

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

# Define calibration codes
LT_CAL_COMPLETE = 0x00
LT_DEC_X = 0x01
LT_INC_X = 0x02
LT_DEC_Y = 0x04
LT_INC_Y = 0x08

# Define Socket related code 
SOCKET_SUCCESS = 0
SOCKET_FAIL_TO_CONNECT = 1
SOCKET_CONNECTION_LOST = 2

class DevWindow(QMainWindow):
    # Model : SocketState
    SocketState = SOCKET_CONNECTION_LOST
    
    # Model : RcsState
    RcvStateCurr = ST_UNKNOWN
    # RcvStatePrev = ST_UNKNOWN
    # RcvStateRequested = ST_UNKNOWN

    # Model : Prev. RecvMsg (Received total msg stored including TMessageHeader)
    RecvMsg_Command = '0x0'
    RecvMsg_Image = '0x0'
    RecvMsg_State = '0x0'

    # Model : user_model
    user_model = ""
    prearm_code = "12345678" # temporarily code
    engage_order = "0123456789" # temporarily order

    # Model : Counter of sent to Robot messages
    CountSentCmdMsg = 0
    CountSentCalibMsg = 0

    # # 기존코드 중복, 수석님 코드로 변경필요.
    # class State(Enum):
    #     UNKNOWN = 0
    #     CONNECTED = 1
    #     SAFE = 2
    #     PREARMED = 3
    #     ARMED_MANUAL = 4
    #     AUTO_ENGAGE = 5

    # currnet_state = State.UNKNOWN
    RcvStateCurr = ST_UNKNOWN

  	# Define Image thread to separate
    image_received = pyqtSignal(bytes)
    
    # Add a signal to emit RcvStateCurr changes
    rcv_state_changed = pyqtSignal(int)

    # Define a signal to emit log messages
    log_signal = pyqtSignal(str)

    # Define HeartbeatTimer Start and Stop event from other thread
    startHeartbeat = pyqtSignal(int)  # 타이머 시작 신호
    stopHeartbeat = pyqtSignal()      # 타이머 중지 신호

    def __init__(self):
        super().__init__()
        # # Define thread shutdown event repository
        # self.threads = []  # 스레드 목록을 저장할 리스트
        # self.shutdown_events = []  # 각 스레드 종료를 위한 이벤트 목록
        # # self.thread_shutdown_events = {}  # 스레드 이름을 키로 하고 종료 이벤트를 값으로 하는 ARRAY

		# Event to signal the threads to shut down
        self.shutdown_event = threading.Event()        

        # Define three models to expand extensibility
        self.img_model_global = init_image_processing_model()
        self.selected_model = None

        # Starting the Image Processing Thread
        self.image_processing_thread = ImageProcessingThread()
        self.image_processing_thread.image_processed.connect(self.update_picturebox)
        self.image_processing_thread.start()

        # Connect the signal to the slot in the thread
        self.rcv_state_changed.connect(self.image_processing_thread.update_rcv_state)
        self.image_received.connect(self.image_processing_thread.update_image_data)
        
        # Connect the log signal to the log message slot
        self.log_signal.connect(self.append_log_message)
        # Connect the signal to the slot
        # self.comboBox.currentIndexChanged.connect(self.on_combobox_changed)

        # Connecting to Model : user_model is inserted from sub-directory config.ini file
        self.user_model = UserModel()
        print(self.user_model)
		
        ui_file = 'new_remote.ui'
        ui_mainwindow = uic.loadUi(ui_file, self)

        # app.setStyleSheet(qdarktheme.load_stylesheet())
        self.initUI()

        self.recv_callback = None
        self.send_command_callback = None

        # # Socket related 타이머 설정
        self.HeartbeatTimer = QTimer(self)
        self.HeartbeatTimer.timeout.connect(self.HeartBeatTimer_event)
        # self.HeartbeatTimer = QTimer(self)
        # self.HeartbeatTimer.timeout.connect(self.HeartBeatTimer_event)
        # self.HeartbeatTimer.start(1000)  # 1000 밀리초 = 1초
        # Connect signal and slot for HeartTimer
        self.startHeartbeat.connect(self.HeartbeatTimer.start)
        self.stopHeartbeat.connect(self.HeartbeatTimer.stop)

        # Key Message Event 관련 타이머 설정
        self.key_event_timer_command = QTimer(self)
        self.key_event_timer_command.setInterval(100)  # 100밀리초 간격
        self.key_event_timer_command.timeout.connect(self.process_command_key_event)
        self.key_event_timer_command.setSingleShot(True)
        self.key_event_timer_calibration = QTimer(self)
        self.key_event_timer_calibration.setInterval(100)  # 100밀리초 간격
        self.key_event_timer_calibration.timeout.connect(self.process_calibration_key_event)
        self.key_event_timer_calibration.setSingleShot(True)
        self.last_key_event = None

        # # tcp_thread용 frame queue 정의
        # self.frame_queue = Queue(maxsize=20)  # Frame queue
        
        self.show()

    # def print_models(self):
    #     # img_model_global에 저장된 모델 정보 출력
    #     if self.img_model_global:
    #         for model in self.img_model_global:
    #             print(f"Model loaded: {model.get_name()}")
    #     else:
    #         print("No models are loaded.")
    def update_model_combobox(self):
        # Clear existing items
        self.comboBoxChangeAlgorithm.clear()
        
        # Check if models are loaded
        if self.img_model_global:
            # Populate the combo box with model names
            for model in self.img_model_global:
                self.comboBoxChangeAlgorithm.addItem(model.get_name())
            # Set the first item as the default selected item
            self.comboBoxChangeAlgorithm.setCurrentIndex(0)
        else:
            # Optionally handle the case where no models are loaded
            self.comboBoxChangeAlgorithm.addItem("No models available")
            # Set the first item as the default selected item
            self.comboBoxChangeAlgorithm.setCurrentIndex(0)

    def initUI(self):
        # self.print_models()
        intValidator = QIntValidator()
    
        # update combobox of image model
        self.update_model_combobox()

        # setValidator
        self.editEngageOrder.setValidator(intValidator)
        self.editTCPPort.setValidator(intValidator)

        # setCustomValidator
        self.editIPAddress.textChanged.connect(self.validCheckIpAndPort)
        self.editTCPPort.textChanged.connect(self.validCheckIpAndPort)
        self.editPreArmCode.textChanged.connect(self.validCheckPreArmedCode)
        self.editEngageOrder.textChanged.connect(self.validCheckEngageOrder)

        # setListener
        self.comboBoxSelectMode.currentIndexChanged.connect(self.on_combobox_changed_mode)
        self.comboBoxChangeAlgorithm.currentIndexChanged.connect(self.on_combobox_changed_algorithm)
        self.buttonConnect.clicked.connect(self.connect)
        self.buttonDisconnect.clicked.connect(self.disconnect)
        self.buttonPreArmEnable.clicked.connect(self.toggle_preArm)
        self.checkBoxLaserEnable.clicked.connect(self.toggle_laser)
        self.buttonCalibrate.clicked.connect(self.toggle_calibrate)
        self.buttonStart.clicked.connect(self.autoengagestart)

        # direction buttons
        self.buttonUp.setIcon(QIcon('resources/arrow_up.png'))
        self.buttonUp.setStyleSheet("border: none;")

        self.buttonDown.setIcon(QIcon('resources/arrow_down.png'))
        self.buttonDown.setStyleSheet("border: none;")
        self.buttonRight.setIcon(QIcon('resources/arrow_right.png'))
        self.buttonRight.setStyleSheet("border: none;")
        self.buttonLeft.setIcon(QIcon('resources/arrow_left.png'))
        self.buttonLeft.setStyleSheet("border: none;")
        self.buttonFire.setIcon(QIcon('resources/exit.png'))
        self.buttonFire.setStyleSheet("border: none;")

        self.stackedWidget.setCurrentIndex(0)

        self.log_message("Init Start...")
        self.setInitialValue()
        self.updateSystemState()

        # Set focus on the main window
        self.setFocus()

    # def set_recv_callback(self, callback):
    #     self.recv_callback = callback

    # def set_send_command_callback(self, callback):
    #     self.send_command_callback = callback

    def get_img_model(self):
        if self.img_model_global and len(self.img_model_global) > 0:
            self.selected_model = self.img_model_global[0]  # Assign the first model in the list to selected_model
            return self.selected_model
        else:
            print("Model list is empty or not initialized.")
            return None

    def setInitialValue(self):
        self.setAllUIEnabled(False, False)
        self.editIPAddress.setText(self.user_model.ip)
        self.editTCPPort.setText(self.user_model.port)
        self.initRecordLayeredViews()
        self.setHitResult(True, 1)
        self.setHitResult(False, 2)
    
    def initRecordLayeredViews(self):
        self.layeredQVBox = QVBoxLayout()

        # background
        # bg_label = QLabel(self)
        # # bg_label.setFixedSize(960, 544)
        # bg = QPixmap(960, 544)  # QPixmap 객체 생성 및 사이즈 설정
        # bg.fill(Qt.black)  # 배경색을 검은색으로 채움
        # bg_label.setPixmap(bg)
        # self.layeredQVBox.addWidget(bg_label)


        # mv_label = QLabel(self)
        # movie = QMovie('resources/load_dreamer.gif')  # QMovie 객체 생성 및 GIF 파일 경로 설정
        # mv_label.setMovie(movie)
        # movie.start()  # GIF 재생 시작
        # self.layeredQVBox.addWidget(mv_label)

        self.pictureBox = QLabel(self)
        self.pictureBox.setFixedSize(960, 544)  # Set size to match sending original image
        self.pictureBox.setAlignment(Qt.AlignCenter)
        self.layeredQVBox.addWidget(self.pictureBox)

        # fps 
        self.fps = QLabel("FPSFPSFPS", self)
        self.layeredQVBox.addWidget(self.fps)

        self.overlayWidget.setLayout(self.layeredQVBox)


    def setHitResult(self, result, targetNumber): 
        result = 'HIT!!' if result else 'MISS'
        self.hitResult.setText(result)
        self.hitResultHistory.append(f'{targetNumber}: {result}')


    def validCheckIpAndPort(self,text): 
        self.buttonConnect.setEnabled(False)

        ip = self.editIPAddress.text()
        port = self.editTCPPort.text()

        if not ip:
             self.log_message(f'Please enter IP address.')
        elif not port:
             self.log_message(f'Please enter port number.')
        elif not self.check_ipv4(ip) :
             self.log_message(f'Not match IP Address Pattern.')
        elif not self.check_port(port) :
             self.log_message(f'Port must be 0-65535.')
        else:
             self.buttonConnect.setEnabled(True)

    def validCheckPreArmedCode(self,code):
        if code:
            self.buttonPreArmEnable.setEnabled(True)
        else:
            self.buttonPreArmEnable.setEnabled(False)
            self.log_message(f"Please enter preArmedCode")

    def validCheckEngageOrder(self,order):
        if order:
            self.buttonStart.setEnabled(True)
        else :
            self.buttonStart.setEnabled(False)
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
        
    @pyqtSlot(QPixmap)
    def update_picturebox(self, pixmap):
        self.pictureBox.setPixmap(pixmap)
        self.pictureBox.setScaledContents(True)
		
    def on_combobox_changed_mode(self, index):
        widgetIndex = 1 if index==2 else 0
        self.stackedWidget.setCurrentIndex(widgetIndex)
        if index == 0:
            # self.currnet_state = self.State.PREARMED
            self.RcvStateCurr = ST_PREARMED
            self.send_state_change_request_to_server(ST_PREARMED) 
        elif index ==1:
            # self.currnet_state = self.State.ARMED_MANUAL
            self.RcvStateCurr = ST_ARMED_MANUAL
            self.send_state_change_request_to_server(ST_ARMED_MANUAL)    
        else:
            # self.currnet_state = self.State.AUTO_ENGAGE
            self.RcvStateCurr = ST_AUTO_ENGAGE
            char_array = self.get_char_array_autoengage_from_text(self.editEngageOrder)
            self.send_target_order_to_server(char_array)
            self.log_message(f"Auto Engage State is Changed: {self.editEngageOrder}")
            print("Auto Engage State is Changed: ", {self.editEngageOrder})
            self.send_state_change_request_to_server(ST_AUTO_ENGAGE)   

        self.setAllUIEnabled(True, True) 

        # if 'Auto Engage' == self.comboBoxSelectMode.currentText():
        #     self.current_mode = self.Mode.AUTO_ENGAGE
        # else:
        #     self.current_mode = self.Mode.ARAMED_MANUAL

        # self.setAllUIEnabled(True, True)    
    
    def on_combobox_changed_algorithm(self, index):
        # print(f"on_combobox_changed_algorithm... index: {index}")
        # self.selected_model = self.img_model_global(index)
        # print(f"on_combobox_changed_algorithm... SELECTED: {self.img_model_global(index)}")
        # print(f"on_combobox_changed_algorithm... index: {index}")
        if 0 <= index < len(self.img_model_global):
            self.selected_model = self.img_model_global[index]
            print(f"on_combobox_changed_algorithm... SELECTED: {self.img_model_global[index].get_name()}")
        else:
            print("Invalid index or model list is empty")
            self.selected_model = None

        # if index == 0 :
        #     self.changeToYolo()
        # elif index == 1:
        #     self.changeToOpenCV()
        # else:
        #     self.changeToTensorFlow()
            
    def toggle_calibrate(self):
        if self.buttonCalibrate.isChecked():
            # TODO
            self.send_calib()
            self.buttonCalibrate.setText('OFF')
        else:
            self.send_calib()
            self.buttonCalibrate.setText('ON')

    def toggle_preArm(self):
        if self.buttonPreArmEnable.isChecked():
            self.pre_arm_enable()
        else:
            # TODO
            # change To SAFEMODE
            print('Disconnecting...')

    
    @pyqtSlot()
    def connect(self):
        ip = self.editIPAddress.text()
        port = int(self.editTCPPort.text())
        self.log_message(f"Connecting to {ip}:{port}")

        if hasattr(self, 'tcp_thread') and self.tcp_thread.is_alive():
            self.log_message("Already connected, disconnect first.")
            return
        
        # self.shutdown_tcpevent = threading.Event()  # add for shutdown of event
        self.tcp_thread = threading.Thread(target=common_start, args=(ip, port, self.shutdown_event, self)) # modify for shutdown of event
        self.tcp_thread.start()
        self.log_message("Connecting.....")
        
        self.user_model.save_to_config(ip, port)
        # self.currnet_state = self.State.SAFE
        self.RcvStateCurr = ST_SAFE
        self.setAllUIEnabled(True, False)

    def reconnect(self):
        ip = self.editIPAddress.text()
        port = int(self.editTCPPort.text())
        self.log_message(f"Reconnecting to {ip}:{port}")

        # 아직 tcp_thread가 살아있는 경우 제거하고 다시 접속 필요
        if hasattr(self, 'tcp_thread') and self.tcp_thread.is_alive():
            self.shutdown_event.set()       # Signal the thread to stop
            self.tcp_thread.join()
            self.shutdown_event.clear()
        
        # self.shutdown_tcpevent = threading.Event()  # add for shutdown of event
        self.tcp_thread = threading.Thread(target=common_start, args=(ip, port, self.shutdown_event, self)) # modify for shutdown of event
        self.tcp_thread.start()
        self.log_message("Connecting.....")
        
        self.user_model.save_to_config(ip, port)
        self.setAllUIEnabled(True, False)

    def setAllUIEnabled(self, connected, preArmed):
        self.updateConnectedUI(connected)
        self.updateModeUI()

    def updateConnectedUI(self, connected):
        self.editIPAddress.setEnabled(False if connected else True)
        self.editTCPPort.setEnabled(False if connected else True)
        self.editPreArmCode.setEnabled(True if connected else False)
        self.buttonConnect.setEnabled(False if connected else True)
        self.buttonDisconnect.setEnabled(True if connected else False)
        self.buttonPreArmEnable.setEnabled(True if connected else False)
  
    def updateModeUI(self):

        if self.RcvStateCurr == ST_SAFE:
        # if self.currnet_state == self.State.SAFE:
            self.comboBoxSelectMode.setEnabled(False)
            self.editPreArmCode.setEnabled(True)
            self.buttonPreArmEnable.setText('Ready to Pre-Armed')
            self.checkBoxLaserEnable.setEnabled(False)
            self.buttonCalibrate.setEnabled(False)
        # elif self.currnet_state == self.State.PREARMED:
        elif self.RcvStateCurr == ST_PREARMED:
            self.comboBoxSelectMode.setEnabled(True)
            self.editPreArmCode.setEnabled(False)
            self.buttonPreArmEnable.setText('Relase Pre-Armed')
            self.checkBoxLaserEnable.setEnabled(False)
            self.buttonCalibrate.setEnabled(False)
        # elif self.currnet_state == self.State.ARMED_MANUAL:
        elif self.RcvStateCurr == ST_ARMED_MANUAL:
            self.comboBoxSelectMode.setEnabled(True)
            self.editPreArmCode.setEnabled(False)
            self.buttonPreArmEnable.setText('Relase Pre-Armed')
            self.checkBoxLaserEnable.setEnabled(True)
            self.buttonCalibrate.setEnabled(True)
        # elif self.currnet_state == self.State.AUTO_ENGAGE:
        elif self.RcvStateCurr == ST_AUTO_ENGAGE:
            self.comboBoxSelectMode.setEnabled(True)
            self.editPreArmCode.setEnabled(False)
            self.buttonPreArmEnable.setText('Relase Pre-Armed')
            self.checkBoxLaserEnable.setEnabled(False)
            self.buttonCalibrate.setEnabled(False)
        else:
            self.comboBoxSelectMode.setEnabled(False)
            self.editPreArmCode.setEnabled(True) 
            self.buttonPreArmEnable.setText('Ready to Pre-Armed')
            self.checkBoxLaserEnable.setEnabled(False)
            self.buttonCalibrate.setEnabled(False)
        # self.comboBoxChangeAlgorithm

    @pyqtSlot()
    def disconnect(self):
        # self.log_message("Disconnected")

        if hasattr(self, 'tcp_thread') and self.tcp_thread.is_alive():
            # self.frame_queue.put(None)  # Signal the thread to stop
            self.shutdown_event.set()       # Signal the thread to stop
            self.tcp_thread.join()
        
        self.log_message("Disconnected")
        # self.currnet_state = self.State.UNKNOWN
        # self.currnet_state = self.State.UNKNOWN
        self.RcvStateCurr = ST_UNKNOWN
        self.setAllUIEnabled(False, False)
        self.shutdown_event.clear()

    @pyqtSlot()
    def pre_arm_enable(self):
        self.log_message("Pre-Arm Enable clicked")
        # self.send_state_change_request_to_server(ST_SAFE)

        if isinstance(self.RcvStateCurr, bytes):
            state_int = int.from_bytes(self.RcvStateCurr, byteorder='little')
        else:
            state_int = self.RcvStateCurr

        print("Current State : ", (state_int & ST_CLEAR_LASER_FIRING_ARMED_CALIB_MASK), " ")

        # if ((state_int & ST_CLEAR_LASER_FIRING_ARMED_CALIB_MASK) == ST_SAFE):
        self.log_message("Send Pre-Arm Enable")
        print("Send Pre-Arm Enable")
        
        char_array = self.get_char_array_prearmed_from_text(self.editPreArmCode)
        self.send_pre_arm_code_to_server(char_array)
        
        # Update Current State 
        self.RcvStateCurr = ST_PREARMED
        # self.RcvStateRequested = ST_PREARMED
        # self.currnet_state = self.State.PREARMED
        self.updateSystemState()
        self.setAllUIEnabled(True, True)

    @pyqtSlot()
    def toggle_armed_manual(self):
        armedManual = self.comboBoxSelectMode.setCurrentIndex()==2
        self.log_message(f"Armed Manual Enabled: {armedManual}")
        print("Armed Manual Enabled: ", {armedManual})
        if (self.checkBoxArmedManualEnable.isChecked() == True):
            self.send_state_change_request_to_server(ST_ARMED_MANUAL) 
        else:
            self.send_state_change_request_to_server(ST_PREARMED)   
		#TODO current State update필요
		#self.currnet_state = self.State.ARMED_MANUAL


    @pyqtSlot()
    def toggle_laser(self):
        # Start Armed Manual 
        self.log_message(f"Laser Enabled: {self.checkBoxLaserEnable.isChecked()}")
        print("Laser Enabled: ", {self.checkBoxLaserEnable.isChecked()})

        if isinstance(self.RcvStateCurr, bytes):
            state_int = int.from_bytes(self.RcvStateCurr, byteorder='little')
        else:
            state_int = self.RcvStateCurr

        if (self.checkBoxLaserEnable.isChecked() == True):
            # state_int should be 72
            if (state_int & ST_ARMED_MANUAL) == ST_ARMED_MANUAL:
                state_int |= ST_LASER_ON
            else:
                state_int |= (ST_ARMED_MANUAL|ST_LASER_ON)
            self.send_state_change_request_to_server(state_int)
        else:
            # state_int should be 8
            state_int &= ST_CLEAR_LASER_MASK
            self.send_state_change_request_to_server(state_int)
    
    @pyqtSlot()
    def send_calib(self):
        self.log_message(f"Calibration Enabled: {self.buttonCalibrate.isChecked()}")
        print("Calibration Enabled: ", {self.buttonCalibrate.isChecked()})

        if isinstance(self.RcvStateCurr, bytes):
            state_int = int.from_bytes(self.RcvStateCurr, byteorder='little')
        else:
            state_int = self.RcvStateCurr

        if(self.buttonCalibrate.isChecked() == True):
            if (state_int & ST_ARMED_MANUAL) == ST_ARMED_MANUAL:
                state_int |= ST_CALIB_ON
            else:
                state_int |= (ST_ARMED_MANUAL|ST_CALIB_ON)
            self.send_state_change_request_to_server(state_int)
        else:
            # send calibration complete message to robot
            self.send_calib_to_server(LT_CAL_COMPLETE)

            # state_int should be 8
            state_int &= ST_CLEAR_CALIB_MASK
            self.send_state_change_request_to_server(state_int)
                    
    def autoengagestart(self):
        char_array = self.get_char_array_autoengage_from_text(self.editEngageOrder)
        self.send_target_order_to_server(char_array)
        print("Auto Engage Fire Started: ", {self.editEngageOrder})
        self.set_command(CT_FIRE_START)
        # self.send_state_change_request_to_server(ST_AUTO_ENGAGE)

    @pyqtSlot()
    def toggle_auto_engage(self):
        autoEngage = self.comboBoxSelectMode.setCurrentIndex()==1
        self.log_message(f"Auto Engage Enabled: {self.checkBoxAutoEngage.isChecked()}")
        print("Auto Engage Enabled: ", {autoEngage})
        if (autoEngage == True):
            engageOrder = self.editEngageOrder.text

            if not engageOrder:
                self.log_message(f"Please enter engageOrders")
                print("Auto Engage Enabled: ", {autoEngage})
            else:
                char_array = self.get_char_array_autoengage_from_text(self.editEngageOrder)
                self.send_target_order_to_server(char_array)
                print("Auto Engage Enabled: ", {self.editEngageOrder})
                self.send_state_change_request_to_server(ST_AUTO_ENGAGE)
        else:
            self.send_state_change_request_to_server(ST_PREARMED)  

    ########################################################################
    # MT_COMMANDS 전송
    def set_command(self, command):
        if self.is_client_connected():
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
            return True
        return False
    ########################################################################
    # Client Socket 연결상태 전송 (업데이트)
    def is_client_connected(self):
        # 클라이언트 연결 상태를 확인하는 함수
        if self.SocketState == SOCKET_SUCCESS:
            return True  # 예시로 True 반환, 실제로는 연결 상태를 확인하는 코드 필요
        else:
            return False  # 예시로 True 반환, 실제로는 연결 상태를 확인하는 코드 필요

    ########################################################################
    # MT_CALIB_COMMANDS 전송
    def send_calib_to_server(self, code):
        if self.is_client_connected():
            # msg_len = struct.calcsize(">II") + struct.calcsize(">B")
            msg = struct.pack(">II", struct.calcsize(">B"), MT_CALIB_COMMANDS)
            msg += struct.pack(">B", code)
            sendMsgToCannon(msg)
            self.log_message(f"Send calib message: {code}")
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

        # print("get_char_array_prearmed_from_text to cannon", char_array, " ", len(char_array))
        return char_array
    
    ########################################################################
    # MT_PREARM 암호 전송
    def send_pre_arm_code_to_server(self, code):
        if self.is_client_connected():
            msg_len = struct.calcsize(">II") + len(code)
            msg = struct.pack(">II", len(code), MT_PREARM)  # 길이 조정
            msg = bytearray(msg)  # msg를 bytearray로 변환

            # code의 각 바이트를 msg에 추가
            for byte in code:
                msg.append(byte)

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

            print("send_state_change_request_to_server ", ' '.join(f'0x{byte:02x}' for byte in msg))
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
        # print("get_char_array_autoengage_from_text to cannon", char_array, " ", len(char_array))

        return char_array
    
    ########################################################################
    # MT_TARGET_SEQUENCE 전송
    def send_target_order_to_server(self, target_order):
        if self.is_client_connected():
            msg_len = struct.calcsize(">II") + len(target_order)
            msg = struct.pack(">II", len(target_order), MT_TARGET_SEQUENCE)  # 길이 조정
            msg = bytearray(msg)  # msg를 bytearray로 변환

            # code의 각 바이트를 msg에 추가
            for byte in target_order:
                msg.append(byte)

            print("send_target_order_to_server ", ' '.join(f'0x{byte:02x}' for byte in msg))
            sendMsgToCannon(msg)
            return True
        return False

    ########################################################################
    # log message textbox 출력 - Invoke 처리 완료
    @pyqtSlot(str)
    def append_log_message(self, message):
        self.logBox.append(message)
        self.logBox.ensureCursorVisible()
        QApplication.processEvents()  # Process events to update UI

    def log_message(self, message):
        self.log_signal.emit(message)

    # def log_message(self, message):
    #     self.logBox.append(message)
    #     self.logBox.ensureCursorVisible()
    #     QApplication.processEvents()  # Process events to update UI

    ########################################################################
    # Update Current System State
    def updateSystemState(self):
        # self.log_message("Called updateSystemState Function!!_", self.RcvStateCurr)
        self.log_message("Called updateSystemState Function!!_")
        if isinstance(self.RcvStateCurr, bytes):
            state_int = int.from_bytes(self.RcvStateCurr, byteorder='little')
        else:
            state_int = self.RcvStateCurr

        if (state_int & ST_CLEAR_LASER_FIRING_ARMED_CALIB_MASK) == ST_UNKNOWN:
            self.labelState.setText("UNKNOWN")
            self.log_message(f"MT_STATE : UNKNOWN_{state_int}")
        elif (state_int & ST_CLEAR_LASER_FIRING_ARMED_CALIB_MASK) == ST_SAFE:
            self.labelState.setText("SAFE")
            self.log_message(f"MT_STATE : SAFE_{state_int}")
        elif (state_int & ST_CLEAR_LASER_FIRING_ARMED_CALIB_MASK) == ST_PREARMED:
            self.labelState.setText("PREARMED")
            self.log_message(f"MT_STATE : PREARMED_{state_int}")
        elif (state_int & ST_CLEAR_LASER_FIRING_ARMED_CALIB_MASK) == ST_AUTO_ENGAGE:
            self.labelState.setText("AUTO_ENGAGE")
            self.log_message(f"MT_STATE : AUTO_ENGAGE_{state_int}")
        elif (state_int & ST_CLEAR_LASER_FIRING_ARMED_CALIB_MASK) == ST_ARMED_MANUAL:
            self.labelState.setText("ARMED_MANUAL")
            self.log_message(f"MT_STATE : ARMED_MANUAL_{state_int}")
        elif (state_int & ST_CLEAR_LASER_FIRING_ARMED_CALIB_MASK) == ST_ARMED:
            self.labelState.setText("ARMED") 
            self.log_message(f"MT_STATE : ARMED_{state_int}")
        else:
            print("MT_STATE : ", state_int)
            self.labelState.setText("MT_STATE : UNEXPECTED") 
            self.log_message(f"MT_STATE : EXCEPTION_{state_int}")
            # self.send_state_change_request_to_server()
        
        # Emit the signal with the new state
        self.rcv_state_changed.emit(state_int)

    def updateSocketState(self, socketstate):
        if socketstate == SOCKET_SUCCESS:
            self.SocketState = SOCKET_SUCCESS
            self.log_message("Robot is connected successfully")
            self.stopHeartbeat.emit()  # 메인 스레드에서 타이머 중지

        elif socketstate == SOCKET_FAIL_TO_CONNECT:
            self.SocketState = SOCKET_FAIL_TO_CONNECT
            self.setAllUIEnabled(False, False)
            # self.buttonConnect.setEnabled(True)
            # self.buttonDisconnect.setEnabled(False)
            self.log_message("Robot is failed to connect")
            self.disconnect()

        elif socketstate == SOCKET_CONNECTION_LOST:
            self.SocketState = SOCKET_CONNECTION_LOST
            self.setAllUIEnabled(False, False)
            # self.buttonConnect.setEnabled(True)
            # self.buttonDisconnect.setEnabled(False)
            self.log_message("Robot's connection is lost - Starting retry to connect....")
            # self.HeartBeatTimer_event()
            if not self.HeartbeatTimer.isActive():
                # self.HeartbeatTimer.start(10000)
                self.startHeartbeat.emit(10000)  # HeartbeatTimer starts

    ###################################################################
    # Image presentation showing thread close
    ###################################################################
    def closeEvent(self, event):
        # QThread of image_processing_thread stop event
        self.image_processing_thread.stop()
        event.accept()

        # Terminate tcp_thread if it has been created
        if hasattr(self, 'tcp_thread') and self.tcp_thread.is_alive():
            print("TCP thread is tried to be closed...")
            self.shutdown_event.set()
            self.tcp_thread.join(timeout=5)  # 최대 5초 대기
            print("TCP thread is closed successfully.")
        else:
            print("TCP thread was not active or not created.")
        
        print("All threads are closed successfully.")
        super().closeEvent(event)  # 기본 종료 이벤트 수행

    ###################################################################
    # callback_msg 처리할때 MT 메시지 종류에 따라 차등 처리 기능 구현
    ###################################################################
    def callback_msg(self, message):
        # For double check
        len_ = len(message) - 8
        # Unpack the message header
        len_msg = message[0:4]
        len_msg = int.from_bytes(len_msg, byteorder='big')
        type_msg = message[4:8]
        type_msg = int.from_bytes(type_msg, byteorder='big')
        # print(f"Message Received, size: {len_msg}, {len_}")

        # MT_IMAGE는 tcp_protocol에서 직접 보내주므로 little로 변환된 데이터 수신
        if type_msg == MT_IMAGE:
            # print test
            # print("MT_IMAGE Received")

            # Buffer to store the received message
            image_data = bytearray(len_msg)
            image_data = message[8:8 + len_msg]

            self.image_received.emit(image_data)

            # # Show the received image to picturebox
            # np_arr = np.frombuffer(image_data, np.uint8)
            # img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
            # if img is not None:
            #     img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            #     h, w, ch = img_rgb.shape
            #     bytes_per_line = ch * w
            #     qt_image = QImage(img_rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
            #     pixmap = QPixmap.fromImage(qt_image)

            #     # Add red cross hair in pixmap
            #     painter = QPainter(pixmap)
            #     pen = QPen(QColor(255, 0, 0), 2)
            #     painter.setPen(pen)
                
            #     # Calculate the center of the image
            #     center_x = w // 2 # self.pictureBox.width() // 2
            #     center_y = h // 2 # self.pictureBox.height() // 2

            #     self.crosshair_size = 60
            #     half_size = self.crosshair_size // 2

            #     painter.drawLine(center_x - half_size, center_y, center_x + half_size, center_y)
            #     painter.drawLine(center_x, center_y - half_size, center_x, center_y + half_size)

            #     painter.end()

            #     self.pictureBox.setPixmap(pixmap)
            #     self.pictureBox.setScaledContents(True)

        # 나머지 MT_MSG 들은 byte 배열이 들어오므로 bit -> little 변환이 필요함, 송신도 마찬가지
        elif type_msg == MT_STATE:
            # print test
            print("MT_STATE Received :", ' '.join(f'0x{byte:02x}' for byte in message))
            rcv_state = struct.unpack(">III", message)[2]
            self.RcvStateCurr = rcv_state
            # print("MT_STATE Received as", self.RcvStateCurr, " ", rcv_state)
            self.updateSystemState()

            # if self.RcvStateCurr != self.RcvStatePrev:
            #     self.RcvStatePrev = self.RcvStateCurr
            
        # 나머지 MT_MSG 들은 byte 배열이 들어오므로 bit -> little 변환이 필요함, 송신도 마찬가지
        elif type_msg == MT_TEXT:
            # print MT_TEXT            
            # Buffer to store the received message
            text_data = bytearray(len_msg)
            text_data = message[8:8 + len_msg]
            text_str = text_data.decode('utf-8')  # 'ascii' 대신 'utf-8'을 사용해도 됩니다.
            self.log_message(f"TEXT Received : {text_str}")

        elif type_msg == MT_SOCKET:
            # print test
            print("Socket Message Received", type_msg)
            print("MT_SOCKET Received :", ' '.join(f'0x{byte:02x}' for byte in message))

            # SOCKET_SUCCESS = 0
            # SOCKET_FAIL_TO_CONNECT = 1
            # SOCKET_CONNECTION_LOST = 2

            socket_state = struct.unpack(">IIB", message)[2]
            socket_state = int(socket_state)
            # self.SocketState = socket_state
            # print("MT_STATE Received as", self.RcvStateCurr, " ", rcv_state)
            print("Socket State Received", socket_state)
            self.updateSocketState(socket_state)
        else:
            # print test
            print("Exception Message Received", type_msg)
            print("MT_EXCEPTION Received :", ' '.join(f'0x{byte:02x}' for byte in message))

    # Using heartbeat timer, in order to detect the robot control sw to set abnormal state
    def HeartBeatTimer_event(self):
        self.log_message("Attempting to reconnect...")
        # if self.check_server(self.editIPAddress.text(), self.editTCPPort.text()):
        ip = self.editIPAddress.text()
        port = int(self.editTCPPort.text())
        if self.check_server(ip, port):
            print("Server is up! Stopping the timer.")
            self.HeartbeatTimer.stop()
            # Theads.settimeout(5)  # 5 seconds timeout
            self.reconnect()
        else:
            print("Server check failed, will retry in 10 seconds.")
        self.connect()

    def check_server(self, ip, port):
        # Simple TCP socket to check the server
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(5)  # 5 seconds timeout
            try:
                # 서버에 연결 시도
                serverAddress = (ip, port)
                sock.connect(serverAddress)
                return True
            except socket.error as e:
                print(f"Failed to connect to {ip}:{port}, error: {e}")
                return False
            


    def keyPressEvent(self, event):
        if (self.RcvStateCurr & ST_CALIB_ON) == ST_CALIB_ON :
            key_map = {
                Qt.Key_I: LT_INC_Y,
                Qt.Key_L: LT_INC_X,
                Qt.Key_J: LT_DEC_X,
                Qt.Key_M: LT_DEC_Y,
            }
            # if self.RcvStateCurr == ST_CALIB_ON: 
            if event.key() in key_map:
                print(f"cal_key_send")
                self.last_key_event = key_map[event.key()]
                if not self.key_event_timer_calibration.isActive():
                    self.process_calibration_key_event()
                    self.key_event_timer_calibration.start()

        else:
            if isinstance(self.RcvStateCurr, bytes):
                state_int = int.from_bytes(self.RcvStateCurr, byteorder='little') & ST_CLEAR_LASER_FIRING_ARMED_CALIB_MASK
            else:
                state_int = self.RcvStateCurr & ST_CLEAR_LASER_FIRING_ARMED_CALIB_MASK

            if state_int == ST_PREARMED:
                key_map = {
                    Qt.Key_I: CT_PAN_UP_START,
                    # Qt.Key_Up: CT_PAN_UP_START,
                    Qt.Key_L: CT_PAN_RIGHT_START,
                    # Qt.Key_Right: CT_PAN_RIGHT_START,
                    Qt.Key_J: CT_PAN_LEFT_START,
                    # Qt.Key_Left: CT_PAN_LEFT_START,
                    Qt.Key_M: CT_PAN_DOWN_START,
                    # Qt.Key_Down: CT_PAN_DOWN_START,
                }
            elif state_int == ST_ARMED_MANUAL:
                key_map = {
                    Qt.Key_I: CT_PAN_UP_START,
                    # Qt.Key_Up: CT_PAN_UP_START,
                    Qt.Key_L: CT_PAN_RIGHT_START,
                    # Qt.Key_Right: CT_PAN_RIGHT_START,
                    Qt.Key_J: CT_PAN_LEFT_START,
                    # Qt.Key_Left: CT_PAN_LEFT_START,
                    Qt.Key_M: CT_PAN_DOWN_START,
                    # Qt.Key_Down: CT_PAN_DOWN_START,
                    Qt.Key_F: CT_FIRE_START,
                    # Qt.Key_Return: CT_FIRE_START,
                }
            else:
                key_map = {}
                if event.key() in key_map:
                    # self.set_command(key_map[event.key()])
                    # self.CountSentCmdMsg += 1
                    # print("Count Sent Command Key Event : ", self.CountSentCmdMsg)
                    print(f"command_key_send")
                    self.last_key_event = key_map[event.key()]
                    if not self.key_event_timer_command.isActive():
                        self.process_command_key_event()
                        self.key_event_timer_command.start()

    def keyReleaseEvent(self, event):
        if isinstance(self.RcvStateCurr, bytes):
            state_int = int.from_bytes(self.RcvStateCurr, byteorder='little') & ST_CLEAR_LASER_FIRING_ARMED_CALIB_MASK 
        else:
            state_int = self.RcvStateCurr & ST_CLEAR_LASER_FIRING_ARMED_CALIB_MASK
            
        if state_int == ST_ARMED_MANUAL:
            key_map = {
                Qt.Key_F: CT_FIRE_STOP,
                # Qt.Key_Return: CT_FIRE_STOP
            }
        else:
            key_map = {}

        # if self.RcvStateCurr == ST_ARMED_MANUAL: 
        if event.key() in key_map:
            # self.set_command(key_map[event.key()])
            print(f"command_key_release")
            self.last_key_event = key_map[event.key()]
            if not self.key_event_timer_command.isActive():
                self.process_command_key_event()
                self.key_event_timer_command.start()
    
    def process_calibration_key_event(self):
        if self.last_key_event is not None:
            self.send_calib_to_server(self.last_key_event)
            self.CountSentCalibMsg += 1
            print("Count Sent Calibration Key Event : ", self.CountSentCalibMsg)
            self.last_key_event = None

    def process_command_key_event(self):
        if self.last_key_event is not None:
            self.set_command(self.last_key_event)
            self.CountSentCmdMsg += 1
            print("Count Sent Command Key Event : ", self.CountSentCmdMsg)
            self.last_key_event = None

if __name__ == "__main__":
    app = QApplication(sys.argv)
    mainWin = DevWindow()

    # Set the callback function for image update
    set_uimsg_update_callback(mainWin.callback_msg)

    mainWin.show()
    sys.exit(app.exec_())