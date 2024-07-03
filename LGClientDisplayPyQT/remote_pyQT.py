import sys
import zmq
import threading
import socket
import struct
import cv2
import re
from enum import Enum
import numpy as np
import pyqtgraph as pg
from PyQt5.QtWidgets import QApplication, QMainWindow, QPushButton, QCheckBox, QLabel, QLineEdit, QTextEdit, QVBoxLayout, QGridLayout, QWidget, QMessageBox
from PyQt5.QtGui import QPixmap, QIntValidator, QIcon, QMovie, QTextCursor, QColor
from PyQt5.QtCore import pyqtSignal, pyqtSlot, Qt, QTimer, QMetaObject, Q_ARG, QObject
from usermodel.usermodel import UserModel
from tcp_protocol import sendMsgToCannon, set_uimsg_update_callback, set_fps_update_callback
from common import common_start
from PyQt5 import uic
from queue import Queue
from image_process_ui import ImageProcessingThread
from image_process import init_image_processing_model, init_filter_models
import os
import qdarktheme
from image_process import get_result_model
import time
from cannon_queue import *

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
CT_AUTO_ENGAGE_CANCEL = 0xFF

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

    # currnet_state = State.UNKNOWN
    RcvStateCurr = ST_UNKNOWN

  	# Define Image thread to separate
    image_received = pyqtSignal(bytes) # Sending image bytes
    rcv_state_changed = pyqtSignal(int) # Add a signal to emit RcvStateCurr changes
    model_changed = pyqtSignal(str) # Sending selected model integer value to image_ui
    filter_changed = pyqtSignal(str) # Sending selected image filter integer value to image_ui

    # Define a signal to emit log messages
    log_signal = pyqtSignal(str, str)

    # # Register Disconnect function as pyqtSignal
    disconnectRequested = pyqtSignal()

    # Define a signal that carries a string
    update_fps_signal = pyqtSignal(str)
    # update_fps_datasig = pyqtSignal(float)

    # # Define HeartbeatTimer Start and Stop event from other thread
    # startHeartbeat = pyqtSignal(int)  # 타이머 시작 신호
    # stopHeartbeat = pyqtSignal()      # 타이머 중지 신호

    def __init__(self):
        super().__init__()

        # # Event to signal transmitting disconnect by pyqtSignal because of callback transaction
        self.disconnectRequested.connect(self.handle_disconnect)
        self.update_fps_signal.connect(self.update_fps)
        # self.update_fps_datasig.connect(self.update_fpsdata)

		# Event to signal the threads to shut down
        self.shutdown_event = threading.Event()

        # Define three models to expand extensibility
        self.img_model_global = init_image_processing_model()
        self.selected_model = self.img_model_global[0]

        # Define img filters to expand extensibility
        self.img_filter_global = init_filter_models()
        self.selected_filter = self.img_filter_global[0]
        set_curr_filter(self.selected_filter)
        filter_lenght = len(self.img_filter_global)
        print(f"filter_lenght {filter_lenght}")

        # Starting the Image Processing Thread
        self.image_processing_thread = ImageProcessingThread()
        self.image_processing_thread.image_processed.connect(self.update_picturebox)
        self.image_processing_thread.start()

        # Connect the signal to the slot in the thread
        self.rcv_state_changed.connect(self.image_processing_thread.update_rcv_state)
        self.image_received.connect(self.image_processing_thread.update_image_data)
        self.model_changed.connect(self.image_processing_thread.update_selected_model)
        self.filter_changed.connect(self.image_processing_thread.update_selected_filter)
        
        # Connect the log signal to the log message slot
        self.log_signal.connect(self.append_log_message)
        # Connect the signal to the slot
        # self.comboBox.currentIndexChanged.connect(self.on_combobox_changed)

        # Connecting to Model : user_model is inserted from sub-directory config.ini file
        self.user_model = UserModel()
        print(self.user_model)
		
        # Current file path of script of remote.ui file
        # ui_file = 'new_remote.ui'
        # ui_mainwindow = uic.loadUi(ui_file, self)
        script_dir = os.path.dirname(os.path.realpath(__file__))
        ui_file_path = os.path.join(script_dir, 'new_remote.ui')

        # Load ui of remote.ui
        ui_mainwindow = uic.loadUi(ui_file_path, self)

        # app.setStyleSheet(qdarktheme.load_stylesheet('light'))
        app.setStyleSheet(qdarktheme.load_stylesheet())
        self.initUI()

        # self.HeartbeatTimer = QTimer(self)
        # self.HeartbeatTimer.timeout.connect(self.HeartBeatTimer_event)
        # # Connect signal and slot for HeartTimer
        # self.startHeartbeat.connect(self.start_heartbeat_timer)
        # self.stopHeartbeat.connect(self.HeartbeatTimer.stop)
        self.PrearmedCheckTimer = QTimer(self)
        self.PrearmedCheckTimer.timeout.connect(self.PrearmedCheckTimer_event)
        self.PrearmedCheckTimer.setInterval(1000)  # 1초 (1000 밀리초) 간격으로 타이머 설정

        self.show()

    # def start_heartbeat_timer(self, interval):
    #     self.HeartbeatTimer.start(interval)

    #############################################
    # Update image recognization algorithm model
    #############################################
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
            
    #############################################
    # Update image recognization filter
    #############################################
    def update_filter_combobox(self):
        # Clear existing items
        self.comboBoxChangeFilter.clear()
        
        # Check if filters are loaded
        if self.img_filter_global:
            # Populate the combo box with filter names
            for filter in self.img_filter_global:
                self.comboBoxChangeFilter.addItem(filter.get_name())
            # Set the first item as the default selected item
            self.comboBoxChangeFilter.setCurrentIndex(0)
        else:
            # Optionally handle the case where no filters are loaded
            self.comboBoxChangeFilter.addItem("No img filter available")
            # Set the first item as the default selected item
            self.comboBoxChangeFilter.setCurrentIndex(0)

    def initUI(self):
        # self.print_models()
        intValidator = QIntValidator()
    
        # update combobox of image model
        self.update_model_combobox()
        self.get_img_model() # update to image model of processing image thread

        # update combobox of image filter
        self.update_filter_combobox()
        self.get_img_filter()

        # setValidator
        self.editEngageOrder.setValidator(intValidator)
        self.editTCPPort.setValidator(intValidator)

        # setListener
        self.comboBoxSelectMode.currentIndexChanged.connect(self.on_combobox_changed_mode)
        self.comboBoxChangeAlgorithm.currentIndexChanged.connect(self.on_combobox_changed_algorithm)
        self.comboBoxChangeFilter.currentIndexChanged.connect(self.on_combobox_changed_imgfilter)
        self.buttonConnect.clicked.connect(self.connect)
        self.buttonDisconnect.clicked.connect(self.disconnect)
        self.buttonPreArmEnable.clicked.connect(self.toggle_preArm)
        self.checkBoxLaserEnable.clicked.connect(self.toggle_laser)
        self.buttonCalibrate.clicked.connect(self.toggle_calibrate)
        self.buttonStart.clicked.connect(self.send_autoengage_start)

        # direction buttons
        # Current file path of script of remote.ui file
        # ui_file = 'new_remote.ui'
        # ui_mainwindow = uic.loadUi(ui_file, self)
        # script_dir = os.path.dirname(os.path.realpath(__file__))
        # resources_path = os.path.join(script_dir, 'resources/')
        self.buttonUp.setStyleSheet("border: none;")
        self.buttonUp.clicked.connect(self.clicked_command_up)
        self.buttonDown.setStyleSheet("border: none;")
        self.buttonDown.clicked.connect(self.clicked_command_down)
        self.buttonRight.setStyleSheet("border: none;")
        self.buttonRight.clicked.connect(self.clicked_command_right)
        self.buttonLeft.setStyleSheet("border: none;")
        self.buttonLeft.clicked.connect(self.clicked_command_left)
        self.buttonFire.setStyleSheet("border: none;")
        self.buttonFire.clicked.connect(self.clicked_command_fire)

        self.stackedWidget.setCurrentIndex(0)

        self.log_message("Init Start...")
        self.setInitialValue()
        self.updateSystemState()

        # setCustomValidator
        self.editIPAddress.textChanged.connect(self.validCheckIpAndPort)
        self.editTCPPort.textChanged.connect(self.validCheckIpAndPort)
        self.editPreArmCode.textChanged.connect(self.validCheckPreArmedCode)
        self.editPreArmCode.setEchoMode(QLineEdit.Password)
        self.editEngageOrder.textChanged.connect(self.validCheckEngageOrder)

        # Set focus on the main window
        self.setFocusPolicy(Qt.StrongFocus)
        self.setFocus()

    # def set_recv_callback(self, callback):
    #     self.recv_callback = callback

    # def set_send_command_callback(self, callback):
    #     self.send_command_callback = callback

    def get_img_model(self):
        if self.img_model_global and len(self.img_model_global) > 0:
            # set default
            # self.selected_model = self.img_model_global[0]
            model_name = self.selected_model.get_name()
            self.model_changed.emit(model_name)
            return self.selected_model
        else:
            print("Model list is empty or not initialized.")
            return None
        
    def get_img_filter(self):
        if self.img_filter_global and len(self.img_filter_global) > 0:
            # set default
            filter_name = self.selected_filter.get_name()
            self.filter_changed.emit(filter_name)
            return self.selected_filter
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

        # # Create a plot widget
        # self.plot_widget = pg.PlotWidget()
        # self.layeredQVBox.addWidget(self.plot_widget)
        # # Initialize data
        # self.fps_x = list(range(100))
        # self.fps_y = [0 for _ in range(100)]
        # # Set up the plot
        # self.fps_line = self.plot_widget.plot(self.fps_x, self.fps_y, pen=pg.mkPen(color='b', width=2))

        self.overlayWidget.setLayout(self.layeredQVBox)

    def setHitResult(self, result, targetNumber): 
        if result:
            result_text = 'HIT'
            text_color = 'red'
            history_color = 'red'  # Example color for HIT in history
            font_size = '26px'  # Example font size for HIT in history
            font_weight = 'bold'  # Example font weight for HIT in history
        else:
            result_text = 'MISS'
            text_color = 'green'
            history_color = 'green'  # Example color for MISS in history
            font_size = '24px'  # Example font size for MISS in history
            font_weight = 'normal'  # Example font weight for MISS in history
        

        history_text = f'<font color="{history_color}" style="font-weight: {font_weight};">{targetNumber} >> {result_text}</font>'

        hit_result_text = f'<font color="{history_color}" size="{font_size}" style="font-weight: {font_weight};"> {targetNumber}: {result_text}</font>'

        # self.hitResult.setText(history_text)
        # self.hitResult.setStyleSheet(f'color: {text_color}; font-weight: bold; font-size: 18px;')
        
        # Append to hitResultHistory with colored text
        history_text = f'<font color="{history_color}" style="font-weight: {font_weight};">{targetNumber} >> {result_text}</font>'
        self.hitResultHistory.append(history_text)


    def validCheckIpAndPort(self,text): 
        self.buttonConnect.setEnabled(False)

        ip = self.editIPAddress.text()
        port = self.editTCPPort.text()

        if not ip:
             self.log_message(f'Please enter IP address.', 'Error')
        elif not port:
             self.log_message(f'Please enter port number.', 'Error')
        elif not self.check_ipv4(ip) :
             self.log_message(f'Not match IP Address Pattern.', 'Error')
        elif not self.check_port(port) :
             self.log_message(f'Port must be 0-65535.', 'Error')
        else:
             self.buttonConnect.setEnabled(True)

    def validCheckPreArmedCode(self,code):
        if code:
            self.buttonPreArmEnable.setEnabled(True)
        else:
            self.buttonPreArmEnable.setEnabled(False)
            self.log_message(f"Please enter preArmedCode", 'Error')

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
		
    @pyqtSlot(int)        
    def on_combobox_changed_mode(self, index):
        widgetIndex = 1 if index==2 else 0
        self.stackedWidget.setCurrentIndex(widgetIndex)
        if index == 0:
            # self.currnet_state = self.State.PREARMED
            # self.RcvStateCurr = ST_PREARMED
            self.send_state_change_request_to_server(ST_PREARMED) 
        elif index == 1:
            # self.currnet_state = self.State.ARMED_MANUAL
            # self.RcvStateCurr = ST_ARMED_MANUAL
            self.send_state_change_request_to_server(ST_ARMED_MANUAL)    
        else:
            ###########################################
            ## 1안 : Sequence + AutoEngage Switching ##
            ###########################################
			# nothing to do in the mode change to auto engage
            self.log_message(f"Auto Engage State is Changed", 'Debug') # : {self.editEngageOrder}")
            # print("Auto Engage State is Changed: ", {self.editEngageOrder})
            self.send_state_change_request_to_server(ST_AUTO_ENGAGE)

            # ###########################################
            # ## 2안 : Sequence + AutoEngage Switching ##
            # ###########################################
            # print("Auto Engage State is Changed: ", {self.editEngageOrder})
            # self.send_state_change_request_to_server(ST_AUTO_ENGAGE)   
        self.setAllUIEnabled(True, True) 

    @pyqtSlot()                
    def send_autoengage_start(self):
        # ###########################################
        # ## 1안 : Just Start with Order           ##
        # ###########################################
        # char_array = self.get_char_array_autoengage_from_text(self.editEngageOrder)
        # self.send_target_order_to_server(char_array)
        # print("Auto Engage Fire Started: ", {self.editEngageOrder})
        # self.set_command(CT_FIRE_START)
        # self.send_state_change_request_to_server(ST_AUTO_ENGAGE) 

        ###########################################
        ## 2안 : Switching Start to Stop         ##
        ###########################################
        print("Auto Engage Button Pushed")
        # char_array = self.get_char_array_autoengage_from_text(self.editEngageOrder)
        # self.send_target_order_to_server(char_array)

        current_text = self.buttonStart.text()
        print("Auto Engage Button Pushed : ", current_text)
        if current_text == "Fire":
            self.buttonStart.setText('Stop')  # Update button text to "STOP"
            # self.log_message(f"Auto Engage Fire Started: {self.editEngageOrder}")
            char_array = self.get_char_array_autoengage_from_text(self.editEngageOrder)         ####################3
            self.send_target_order_to_server(char_array)                                        ####################3
            self.log_message(f"Started Auto Engage Fire..", 'Info') # ," ".join(f'0x{byte:02x}' for byte in char_array))
            # self.set_command(CT_FIRE_START)  # Signal to start auto engagement
            
        elif current_text == "Stop":
            self.buttonStart.setText('Fire')  # Update button text back to "START"
            self.log_message(f"Stopped Auto Engage Fire.", 'Info') # : {self.editEngageOrder}")
            self.set_command(CT_AUTO_ENGAGE_CANCEL)  # Signal to stop auto engagement           ####################3
            # self.send_state_change_request_to_server(ST_SAFE)  # Assuming 'ST_SAFE' is the state to return to

    @pyqtSlot(int)
    def on_combobox_changed_algorithm(self, index):
        if 0 <= index < len(self.img_model_global):
            self.selected_model = self.img_model_global[index]
            model_name = self.selected_model.get_name()
            self.model_changed.emit(model_name)
            print(f"Model selected: {self.img_model_global[index].get_name()}")
            # print(f"on_combobox_changed_algorithm... SELECTED: {self.img_model_global[index].get_name()}")
        else:
            print("Invalid index or model list is empty")
            self.selected_model = None
            
    @pyqtSlot(int)
    def on_combobox_changed_imgfilter(self, index):
        if 0 <= index < len(self.img_filter_global):
            self.selected_filter = self.img_filter_global[index]
            filter_name = self.selected_filter.get_name()
            self.filter_changed.emit(filter_name)
            print(f"Img filter selected: {self.img_filter_global[index].get_name()}")
            set_curr_filter(self.selected_filter)
            # # print(f"on_combobox_changed_algorithm... SELECTED: {self.img_model_global[index].get_name()}")
        else:
            print("Invalid index or image filter list is empty")
            self.selected_filter = None

    def toggle_calibrate(self):
        if isinstance(self.RcvStateCurr, bytes):
            state_int = int.from_bytes(self.RcvStateCurr, byteorder='little')
        else:
            state_int = self.RcvStateCurr

        current_text = self.buttonCalibrate.text()
        print("Calibrate Button Pushed : ", current_text)

        if current_text == "Calibrate":
            self.buttonCalibrate.setText('Cal_Off')  # Update button text to "Cal_Off"
            state_int |= ST_CALIB_ON
            print("Current CAL_ON Status : ", state_int)
            self.send_state_change_request_to_server(state_int)
            self.log_message(f"Start Calibration..", 'Info') 
            
        elif current_text == "Cal_Off":
            self.buttonCalibrate.setText('Calibrate')  # Update button text to "Cal_Off"
            # state_int should be 8
            state_int &= ST_CLEAR_CALIB_MASK
            print("Current CAL_OFF Status : ", state_int)
            self.send_state_change_request_to_server(state_int)
            self.log_message(f"Stop Calibration..", 'Info') 

    def toggle_preArm(self):
        current_text = self.buttonPreArmEnable.text()
        if current_text == "Active":
            self.pre_arm_enable()  # PRE-ARMED 상태로 전환하는 함수
            # self.buttonPreArmEnable.setText('SAFE')
            print('Try to enable Pre-Armed mode.')
            self.PrearmedCheckTimer.start()
            
        elif current_text == "Deactive":
            self.send_state_change_request_to_server(ST_SAFE)
            # self.buttonPreArmEnable.setText('PRE-ARMED')
            print('Try to return Safe mode.')

    @pyqtSlot()
    def connect(self):
        ip = self.editIPAddress.text()
        port = int(self.editTCPPort.text())
        self.log_message(f"Connecting to {ip}:{port}", "Info")

        if hasattr(self, 'tcp_thread') and self.tcp_thread.is_alive():
            self.log_message("Already connected, disconnect first.")
            return
        
        # self.shutdown_tcpevent = threading.Event()  # add for shutdown of event
        self.tcp_thread = threading.Thread(target=common_start, args=(ip, port, self.shutdown_event, self)) # modify for shutdown of event
        self.tcp_thread.start()
        self.log_message("Connecting.....")
        
    @pyqtSlot()
    def disconnect(self):
        # self.log_message("Disconnected")
        self.disconnectRequested.emit()

    @pyqtSlot()
    def handle_disconnect(self):
        # Terminate tcp_thread if it has been created
        if hasattr(self, 'tcp_thread') and self.tcp_thread.is_alive():
            print("TCP thread is tried to be closed...")
            self.shutdown_event.set()
            self.tcp_thread.join()  
            print("TCP thread is closed successfully.")
        else:
            print("TCP thread was not active or not created.")
        
        print("All threads are closed successfully.")
        self.log_message("Disconnected")
        # self.currnet_state = self.State.UNKNOWN
        # self.currnet_state = self.State.UNKNOWN
        self.RcvStateCurr = ST_UNKNOWN
        self.setAllUIEnabled(False, False)
        self.updateSystemState()
        self.shutdown_event.clear()

    def setAllUIEnabled(self, connected, preArmed):
        self.updateConnectedUI(connected)
        self.updateModeUI()

    def updateConnectedUI(self, connected):
        self.editIPAddress.setEnabled(False if connected else True)
        self.editTCPPort.setEnabled(False if connected else True)
        self.editPreArmCode.setEnabled(True if connected else False)
        self.buttonConnect.setEnabled(False if connected else True)
        self.buttonDisconnect.setEnabled(True if connected else False)
        # self.buttonPreArmEnable.setEnabled(True if connected else False)
  
    def updateModeUI(self):
        print("updateModeUI self.RcvStateCurr : ", self.RcvStateCurr)
        if (self.RcvStateCurr & ST_CLEAR_LASER_FIRING_ARMED_CALIB_MASK) == ST_SAFE:
        # if self.currnet_state == self.State.SAFE:
            self.comboBoxSelectMode.setEnabled(False)
            # self.comboBoxSelectMode.setCurrentIndex(0)
            self.editPreArmCode.setEnabled(True)
            self.buttonPreArmEnable.setText('Active')
            self.checkBoxLaserEnable.setEnabled(False)
            self.buttonCalibrate.setEnabled(False)
            self.buttonStart.setText("Fire")
        # elif self.currnet_state == self.State.PREARMED:
        elif (self.RcvStateCurr & ST_CLEAR_LASER_FIRING_ARMED_CALIB_MASK) == ST_PREARMED:
            self.comboBoxSelectMode.setEnabled(True)
            # self.comboBoxSelectMode.setCurrentIndex(0)
            self.editPreArmCode.setEnabled(False)
            self.buttonPreArmEnable.setText('Deactive')
            self.checkBoxLaserEnable.setEnabled(False)
            self.buttonCalibrate.setEnabled(False)
            self.buttonStart.setText("Fire")
            self.editEngageOrder.setText("") # For every Pre-armed mode, reset EngageOrder
        # elif self.currnet_state == self.State.ARMED_MANUAL:
        elif (self.RcvStateCurr & ST_CLEAR_LASER_FIRING_ARMED_CALIB_MASK) == ST_ARMED_MANUAL:
            self.comboBoxSelectMode.setEnabled(True)
            self.editPreArmCode.setEnabled(False)
            self.buttonPreArmEnable.setText('Deactive')
            self.checkBoxLaserEnable.setEnabled(True)
            self.buttonCalibrate.setEnabled(True)
            self.buttonStart.setText("Fire")
        # elif self.currnet_state == self.State.AUTO_ENGAGE:
        elif (self.RcvStateCurr & ST_CLEAR_LASER_FIRING_ARMED_CALIB_MASK) == ST_AUTO_ENGAGE:
            self.comboBoxSelectMode.setEnabled(True)
            self.editPreArmCode.setEnabled(False)
            self.buttonPreArmEnable.setText('Deactive')
            self.checkBoxLaserEnable.setEnabled(False)
            self.buttonCalibrate.setEnabled(False)
            # self.buttonStart.setText("Start")
        # elif self.currnet_state == self.State.UNKNOWN:
        else:
            self.comboBoxSelectMode.setEnabled(False)
            # self.comboBoxSelectMode.setCurrentIndex(0)
            self.editPreArmCode.setEnabled(False) 
            self.buttonPreArmEnable.setText('Active')
            self.checkBoxLaserEnable.setEnabled(False)
            self.buttonCalibrate.setEnabled(False)
            self.buttonStart.setText("Fire")
            self.editPreArmCode.setEnabled(False)
            self.buttonPreArmEnable.setEnabled(False)
        # self.comboBoxChangeAlgorithm
        self.labelState.setAlignment(Qt.AlignCenter)

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
        # self.RcvStateCurr = ST_PREARMED
        # self.updateSystemState()
        # self.setAllUIEnabled(True, True)

    @pyqtSlot()
    def toggle_laser(self):
        try:
            # Start Armed Manual 
            self.log_message(f"Laser Enabled: {self.checkBoxLaserEnable.isChecked()}")
            print("Laser Enabled: ", {self.checkBoxLaserEnable.isChecked()})

            if isinstance(self.RcvStateCurr, bytes):
                state_int = int.from_bytes(self.RcvStateCurr, byteorder='little')
            else:
                state_int = self.RcvStateCurr

            if self.checkBoxLaserEnable.isChecked():
                # state_int should be 72
                if (state_int & ST_ARMED_MANUAL) == ST_ARMED_MANUAL:
                    state_int |= ST_LASER_ON
                else:
                    state_int |= (ST_ARMED_MANUAL|ST_LASER_ON)
                print("Current LASER_ON Status : ", state_int)
                self.send_state_change_request_to_server(state_int)
            else:
                # state_int should be 8
                state_int &= ST_CLEAR_LASER_MASK
                print("Current LASER_OFF Status : ", state_int)
                self.send_state_change_request_to_server(state_int)

        except Exception as e:
            self.log_message(f"Error in toggle_laser: {str(e)}")
            print(f"Error in toggle_laser: {str(e)}")
    
    @pyqtSlot()
    def send_calib(self):
        calibrateOn = self.buttonCalibrate.isChecked()
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

    # @pyqtSlot()
    # def toggle_auto_engage(self):
    #     autoEngage = self.comboBoxSelectMode.setCurrentIndex()==1
    #     self.log_message(f"Auto Engage Enabled: {self.checkBoxAutoEngage.isChecked()}")
    #     print("Auto Engage Enabled: ", {autoEngage})
    #     if (autoEngage == True):
    #         engageOrder = self.editEngageOrder.text

    #         if not engageOrder:
    #             self.log_message(f"Please enter engageOrders")
    #             print("Auto Engage Enabled: ", {autoEngage})
    #         else:
    #             char_array = self.get_char_array_autoengage_from_text(self.editEngageOrder)
    #             self.send_target_order_to_server(char_array)
    #             print("Auto Engage Enabled: ", {self.editEngageOrder})
    #             self.send_state_change_request_to_server(ST_AUTO_ENGAGE)
    #     else:
    #         self.send_state_change_request_to_server(ST_PREARMED)  

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
            self.log_message(f"Send calib message: {code}",'Debug')
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
    # @pyqtSlot(str)
    # def append_log_message(self, message):
    #     self.logBox.append(message)
    #     self.logBox.ensureCursorVisible()
    #     QApplication.processEvents()  # Process events to update UI

    @pyqtSlot(str, str)
    def append_log_message(self, message, log_level):

        # Clear any existing formatting
        cursor = self.logBox.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.logBox.setTextCursor(cursor)
        
        # Set color based on log level
        color = None
        if log_level == 'Error':
            color = QColor('#4cf3c1')
        elif log_level == 'Info':
           # color = QColor('blue')
           color = QColor('#949599')
        else:
            color = QColor('white')  # or any other default color
            return
        
        # Apply color to the new message
        cursor.insertHtml(f'<font color="{color.name()}">{message}</font><br>')
        
        # Ensure cursor is visible and update UI
        self.logBox.ensureCursorVisible()
        QApplication.processEvents()    

    def log_message(self, message, logLevel='debug'):
        self.log_signal.emit(message, logLevel)

    # def log_message(self, message):
    #     self.logBox.append(message)
    #     self.logBox.ensureCursorVisible()
    #     QApplication.processEvents()  # Process events to update UI

    ########################################################################
    # Update Current System State
    def updateSystemState(self):
        # self.log_message("Called updateSystemState Function!!_")
        if isinstance(self.RcvStateCurr, bytes):
            state_int = int.from_bytes(self.RcvStateCurr, byteorder='little')
        else:
            state_int = self.RcvStateCurr

        print("updateSystemState(Erase Additional Mode) : ", state_int & ST_CLEAR_LASER_FIRING_ARMED_CALIB_MASK)
        if (state_int & ST_CLEAR_LASER_FIRING_ARMED_CALIB_MASK) == ST_UNKNOWN:
            self.labelState.setText("UNKNOWN")
            self.log_message(f"MT_STATE : UNKNOWN_{state_int}",'Debug')
        elif (state_int & ST_CLEAR_LASER_FIRING_ARMED_CALIB_MASK) == ST_SAFE:
            self.labelState.setText("SAFE")
            self.log_message(f"MT_STATE : SAFE_{state_int}",'Debug')
        elif (state_int & ST_CLEAR_LASER_FIRING_ARMED_CALIB_MASK) == ST_PREARMED:
            self.labelState.setText("PREARMED")
            self.log_message(f"MT_STATE : PREARMED_{state_int}",'Debug')
        elif (state_int & ST_CLEAR_LASER_FIRING_ARMED_CALIB_MASK) == ST_AUTO_ENGAGE:
            self.labelState.setText("AUTO_ENGAGE")
            self.log_message(f"MT_STATE : AUTO_ENGAGE_{state_int}",'Debug')
        elif (state_int & ST_CLEAR_LASER_FIRING_ARMED_CALIB_MASK) == ST_ARMED_MANUAL:
            self.labelState.setText("ARMED_MANUAL")
            self.log_message(f"MT_STATE : ARMED_MANUAL_{state_int}",'Debug')
        elif (state_int & ST_CLEAR_LASER_FIRING_ARMED_CALIB_MASK) == ST_ARMED:
            self.labelState.setText("ARMED") 
            self.log_message(f"MT_STATE : ARMED_{state_int}",'Debug')
        else:
            print("MT_STATE : ", state_int)
            self.labelState.setText("MT_STATE : UNEXPECTED") 
            self.log_message(f"MT_STATE : EXCEPTION_{state_int}",'Debug')
            # self.send_state_change_request_to_server()
        
        # Emit the signal with the new state
        self.rcv_state_changed.emit(state_int)

    ########################################################################
    # Update Socket State due to transaction for SUCCESS, FAIL_TO_CONNECT, CONN_LOST
    def updateSocketState(self, socketstate):
        if socketstate == SOCKET_SUCCESS:
            self.SocketState = SOCKET_SUCCESS
            self.log_message("Robot is connected successfully")
            # self.stopHeartbeat.emit()  # 메인 스레드에서 타이머 중지

            ip = self.editIPAddress.text()
            port = int(self.editTCPPort.text())
            self.user_model.save_to_config(ip, port)
            # self.currnet_state = self.State.SAFE
            self.RcvStateCurr = ST_SAFE
            self.setAllUIEnabled(True, False)
            
        elif socketstate == SOCKET_FAIL_TO_CONNECT:
            self.SocketState = SOCKET_FAIL_TO_CONNECT
            self.setAllUIEnabled(False, False)
            # self.buttonConnect.setEnabled(True)
            # self.buttonDisconnect.setEnabled(False)
            self.log_message("Robot is failed to connect")
            # self.disconnect()
            self.disconnectRequested.emit()

        elif socketstate == SOCKET_CONNECTION_LOST:
            self.SocketState = SOCKET_CONNECTION_LOST
            self.setAllUIEnabled(False, False)
            self.disconnectRequested.emit()
            # self.buttonConnect.setEnabled(True)
            # self.buttonDisconnect.setEnabled(False)
            self.log_message("Robot's connection is lost.")
            # self.log_message("Robot's connection is lost - Starting retry to connect....")
            # self.HeartBeatTimer_event()
            # if not self.HeartbeatTimer.isActive():
            #     # self.HeartbeatTimer.start(10000)
            #     self.startHeartbeat.emit(10000)  # HeartbeatTimer starts

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
            # self.tcp_thread.join(timeout=5)  # 최대 5초 대기
            self.tcp_thread.join()  # 최대 5초 대기
            print("TCP thread is closed successfully.")
        else:
            print("TCP thread was not active or not created.")
        
        print("All threads are closed successfully.")
        # super().closeEvent(event)  # 기본 종료 이벤트 수행

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
            # Buffer to store the received message
            image_data = bytearray(len_msg)
            image_data = message[8:8 + len_msg]

            self.image_received.emit(image_data)
            # Show average FPS to Label
            # getFps()

        # 나머지 MT_MSG 들은 byte 배열이 들어오므로 bit -> little 변환이 필요함, 송신도 마찬가지
        elif type_msg == MT_STATE:
            # MT_STATE prints
            print("MT_STATE Received :", ' '.join(f'0x{byte:02x}' for byte in message))
            rcv_state = struct.unpack(">III", message)[2]

            # When MT_COMPLETE is received, skip transaction
            if (rcv_state & ST_CLEAR_LASER_FIRING_ARMED_CALIB_MASK != MT_COMPLETE):
                self.log_message(f"Received MT_STATE from Robot_{rcv_state}", 'Debug')
                self.RcvStateCurr = rcv_state
                self.updateSystemState()

                # Update UI and Button related to State
                compared_state = rcv_state & ST_CLEAR_LASER_FIRING_ARMED_CALIB_MASK
                if compared_state in (ST_PREARMED, ST_AUTO_ENGAGE, ST_ARMED_MANUAL):
                    # Insert for Exception or Completion of Auto Engagement
                    if compared_state == ST_PREARMED:
                        self.comboBoxSelectMode.setCurrentIndex(0)
                    self.setAllUIEnabled(True, True)
                elif compared_state in (ST_SAFE, ST_UNKNOWN):
                    self.comboBoxSelectMode.setCurrentIndex(0)
                    self.setAllUIEnabled(True, False)
                
        # 나머지 MT_MSG 들은 byte 배열이 들어오므로 bit -> little 변환이 필요함, 송신도 마찬가지
        elif type_msg == MT_TEXT:
            # Buffer to store the received message
            text_data = bytearray(len_msg)
            text_data = message[8:8 + len_msg]
            text_str = ''.join(chr(byte) for byte in text_data if byte < 128)  # 바이트를 ASCII 문자로 변환
            self.log_message(f"{text_str}",'Debug')

        elif type_msg == MT_SOCKET:
            # Reference status : 
            # SOCKET_SUCCESS = 0
            # SOCKET_FAIL_TO_CONNECT = 1
            # SOCKET_CONNECTION_LOST = 2

            # print test
            print("Socket Message Received", type_msg)
            print("MT_SOCKET Received :", ' '.join(f'0x{byte:02x}' for byte in message))

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

    ###################################################################
    # callback_fps : Print fps in MainWnd
    ###################################################################
    def callback_fps(self, rcvfps):
        # print("fps updated : ", rcvfps)
        fps_text = f"Avg FPS : {rcvfps:.2f}"
        # self.fps = rcvfps
        self.update_fps_signal.emit(fps_text)
        # self.update_fps_datasig.emit(rcvfps)

    @pyqtSlot(str)
    def update_fps(self, fps_text):
        self.fps.setText(fps_text)
        
    # @pyqtSlot(float)
    # def update_fpsdata(self, rcvfps):
    #     # Update data
    #     self.fps_x = self.fps_x[1:]  # Remove the first element
    #     self.fps_x.append(self.fps_x[-1] + 1)  # Add a new element

    #     self.fps_y = self.fps_y[1:]  # Remove the first element
    #     self.fps_y.append(rcvfps)  # Add a new random value

    #     # Update the plot
    #     self.fps_line.setData(self.fps_x, self.fps_y)

    # Using heartbeat timer, in order to detect the robot control sw to set abnormal state
    def HeartBeatTimer_event(self):
        self.log_message("Attempting to reconnect...", 'Debug')
        # # if self.check_server(self.editIPAddress.text(), self.editTCPPort.text()):
        # ip = self.editIPAddress.text()
        # port = int(self.editTCPPort.text())
        # if self.check_server(ip, port):
        #     print("Server is up! Stopping the timer.")
        #     self.HeartbeatTimer.stop()
        #     # Theads.settimeout(5)  # 5 seconds timeout
        #     self.connect()
        # else:
        #     print("Server check failed, will retry in 10 seconds.")

    def PrearmedCheckTimer_event(self):
        if self.RcvStateCurr != MT_PREARM:
            self.log_message("Pre-armed password is not correct.")
        self.PrearmedCheckTimer.stop()

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

    def clicked_command_up(self):
        if (self.is_client_connected() and 
            ((self.RcvStateCurr & ST_CLEAR_LASER_FIRING_ARMED_CALIB_MASK) in (ST_ARMED_MANUAL, ST_PREARMED))):
            print("Pressed CT_TILTE_UP_START")
            self.set_command(CT_PAN_UP_START)
        elif (self.is_client_connected() and 
            ((self.RcvStateCurr & ST_CALIB_ON) == ST_CALIB_ON)):
            print("Pressed LT_INC_Y")
            self.set_command(LT_INC_Y)
        else:
            print("Blocking to press CT_TILTE_UP_START")
            self.log_message(f"Moving Cannon to UP..", 'Info')
    def clicked_command_down(self):
        if (self.is_client_connected() and 
            ((self.RcvStateCurr & ST_CLEAR_LASER_FIRING_ARMED_CALIB_MASK) in (ST_ARMED_MANUAL, ST_PREARMED))):
            print("Pressed CT_TILTE_DOWN_START")
            self.set_command(CT_PAN_DOWN_START)
        elif (self.is_client_connected() and 
            ((self.RcvStateCurr & ST_CALIB_ON) == ST_CALIB_ON)):
            print("Pressed LT_DEC_Y")
            self.set_command(LT_DEC_Y)
        else:
            print("Blocking to press CT_TILTE_DOWN_START")
            self.log_message(f"Moving Cannon to Down..", 'Info')
    def clicked_command_right(self):
        if (self.is_client_connected() and 
            ((self.RcvStateCurr & ST_CLEAR_LASER_FIRING_ARMED_CALIB_MASK) in (ST_ARMED_MANUAL, ST_PREARMED))):
            print("Pressed CT_PAN_RIGHT_START")
            self.set_command(CT_PAN_RIGHT_START)
        elif (self.is_client_connected() and 
            ((self.RcvStateCurr & ST_CALIB_ON) == ST_CALIB_ON)):
            print("Pressed LT_INC_X")
            self.set_command(LT_INC_X)
        else:
            print("Blocking to press CT_PAN_UP_START")
            self.log_message(f"Moving Cannon to Right..", 'Info')
    def clicked_command_left(self):
        if (self.is_client_connected() and 
            ((self.RcvStateCurr & ST_CLEAR_LASER_FIRING_ARMED_CALIB_MASK) in (ST_ARMED_MANUAL, ST_PREARMED))):
            print("Pressed CT_PAN_LEFT_START")
            self.set_command(CT_PAN_LEFT_START)
        elif (self.is_client_connected() and 
            ((self.RcvStateCurr & ST_CALIB_ON) == ST_CALIB_ON)):
            print("Pressed LT_DEC_X")
            self.set_command(LT_DEC_X)
        else:
            print("Blocking to press CT_PAN_LEFT_START")
            self.log_message(f"Moving Cannon to Left..", 'Info')
    def clicked_command_fire(self):
        if (self.is_client_connected() and 
            (self.RcvStateCurr & ST_CLEAR_LASER_FIRING_ARMED_CALIB_MASK == ST_ARMED_MANUAL)):
            print("Pressed CT_FIRE_START")
            for _ in range(3):
                self.set_command(CT_FIRE_START)
                time.sleep(0.01)
            self.set_command(CT_FIRE_STOP)
        else:
            print("Blocking to press CT_FIRE")
            self.log_message(f"Fire!!!", 'Info')

    def keyPressEvent(self, event):
        if isinstance(self.RcvStateCurr, bytes):
            state_int = int.from_bytes(self.RcvStateCurr, byteorder='little') & ST_CLEAR_LASER_FIRING_ARMED_CALIB_MASK
        else:
            state_int = self.RcvStateCurr & ST_CLEAR_LASER_FIRING_ARMED_CALIB_MASK

        if isinstance(self.RcvStateCurr, bytes):
            state_cal = int.from_bytes(self.RcvStateCurr, byteorder='little') & ST_CALIB_ON
        else:
            state_cal = self.RcvStateCurr & ST_CALIB_ON

        if state_cal != ST_CALIB_ON:
            if state_int == ST_PREARMED:
                key_map = { Qt.Key_I: CT_PAN_UP_START, Qt.Key_L: CT_PAN_RIGHT_START, Qt.Key_J: CT_PAN_LEFT_START, Qt.Key_M: CT_PAN_DOWN_START }
            elif state_int == ST_ARMED_MANUAL:
                key_map = { Qt.Key_I: CT_PAN_UP_START, Qt.Key_L: CT_PAN_RIGHT_START, Qt.Key_J: CT_PAN_LEFT_START, Qt.Key_M: CT_PAN_DOWN_START, Qt.Key_F: CT_FIRE_START }
            else:
                key_map = {}

            if event.key() in key_map:
                if event.key() == Qt.Key_F: # For Fire, Sending continuous 10 times fire msg
                    for _ in range(3):
                        self.set_command(CT_FIRE_START)
                        time.sleep(0.01)
                    self.set_command(CT_FIRE_STOP)
                else: # For other registered keys                
                    self.set_command(key_map[event.key()])
        elif state_cal == ST_CALIB_ON:
            print("cal keypressed")
            if state_int == ST_ARMED_MANUAL:
                key_map = { Qt.Key_I: LT_INC_Y, Qt.Key_L: LT_INC_X, Qt.Key_J: LT_DEC_X, Qt.Key_M: LT_DEC_Y }
            else:
                key_map = {}

            if event.key() in key_map:
                # For other registered keys                
                self.set_command(key_map[event.key()])

if __name__ == "__main__":
    app = QApplication(sys.argv)
    mainWin = DevWindow()

    # Set the callback function for received message update
    set_uimsg_update_callback(mainWin.callback_msg)
    # Set the callback function for fps update
    set_fps_update_callback(mainWin.callback_fps)


    mainWin.show()
    sys.exit(app.exec_())