# tcp_protocol.py
import socket
import struct
import errno
import cv2
import numpy as np
from image_process import get_result_model, get_init_status, init_model_image, add_image_filter
from queue import Queue, Full
import os
from queue import LifoQueue
import threading
import time
import queue
from cannon_queue import *

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
MT_ERROR = 10
MT_COMPLETE = 11
MT_FIRE = 12
MT_GO_CENTER = 13

# cannon status
UNKNOWN = 0
SAFE = 1  #0x1
PREARMED = 2 #0x2
ENGAGE_AUTO = 4 #0x4
ARMED_MANUAL = 8 #0x8
ARMED = 16 #0x10
FIRING = 32 #0x20
LASER_ON = 64 #0x40
CALIB_ON = 128 #0x80

# error code
ERR_SUCCESS = 0
ERR_FAIL_TO_CONNECT = 1
ERR_CONNECTION_LOST = 2

# target status
TARGET_NONE = 0
TARGET_BEFORE_FIRE = 1
TARGET_AFTER_FIRE = 2
TARGET_FIRING = 3

# image width and height
WIDTH = 960
HEIGHT = 544

# stage by target distance
TARGET_STATGE_1 = 1 # 13 inch / area over 6000
TARGET_STATGE_2 = 2 # 18 inch / area 3500 - 6000
TARGET_STATGE_3 = 3 # 23 - 28 inch / area 1000 - 3500
TARGET_STATGE_4 = 4 # 34 - 35 inch / area 600 - 1000
TARGET_STATGE_5 = 5 # 36 inch / area under 600

# Define message structures
class TMesssageHeader:
    def __init__(self, len_, type_):
        self.Len = len_
        self.Type = type_

# global variables
clientSock = 0
fps = 0
callback_shutdown_event = 0
targetNum = -1
targetStatus = TARGET_NONE
autoEngageStop = False
calibPan = -99.9
calibTilt = -99.9

# Define for updating image to UI
uimsg_update_callback = None
fps_update_callback = None

# Callback function for sending image to UI
def set_uimsg_update_callback(callback):
    # print("Callback function parameter sent.")
    global uimsg_update_callback
    uimsg_update_callback = callback

# Callback function for seding fps to UI
def set_fps_update_callback(callback):
    global fps_update_callback
    fps_update_callback = callback

# frame_queue와 processed_queue를 tcp_protocol.py로 옮김
frame_queue = Queue(maxsize=10)
frame_stack = LifoQueue(maxsize=10)
task_queue = Queue()

def tcp_ip_thread(ip, port, shutdown_event):
    """
    This thread handles TCP/IP communication with the Raspberry Pi.
    """

    # For update fps to ui 
    # fps_info = []   

    print("start receiving image thread: ", ip, "(", port, ")")
    global clientSock
    callback_shutdown_event = 0
    serverAddress = (ip, port)
    clientSock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    try:
        clientSock.connect(serverAddress)
        clientSock.settimeout(1.0)  # 1초 후에 타임아웃
        errorCode = ERR_SUCCESS
        packedData = struct.pack(">IIB", 1, MT_ERROR, errorCode)
        sendMsgToUI(packedData)
    except socket.timeout as e:
        errorCode = ERR_FAIL_TO_CONNECT
        packedData = struct.pack(">IIB", 1, MT_ERROR, errorCode)
        sendMsgToUI(packedData) # ERR_FAIL_TO_CONNECT
        print(f"Network Thread Exit because of connection timed out: {e}")
        # clientSock.close()
        callback_shutdown_event = 1  # Notify all threads to shut down
    except socket.error as e:
        # print("Failed to connect to server:", e)
        errorCode = ERR_FAIL_TO_CONNECT
        packedData = struct.pack(">IIB", 1, MT_ERROR, errorCode)
        sendMsgToUI(packedData) # ERR_FAIL_TO_CONNECT
        print("Network Thread Exit because of connection failure")
        # clientSock.close()
        callback_shutdown_event = 1  # Notify all threads to shut down

    # while True:
    global fps
    global calibPan
    global calibTilt
    frameCnt = 0
    startTime = time.time()
    while not shutdown_event.is_set() and callback_shutdown_event == 0:
        try:
            # Receive the message header
            headerData = clientSock.recv(8)
            # if headerData[0] == 0x68 and headerData[1] == 0x65:
            #     continue
            # elif len(headerData) != struct.calcsize('II'):
            if len(headerData) != struct.calcsize('II'):
                print("Connection lost.")
                callback_shutdown_event = 1  # Notify all threads to shut down
                raise ConnectionError("Connection lost.")
                # print("lost message header ", ' '.join(f'0x{byte:02x}' for byte in headerData))
                # packedData = struct.pack(">IIB", 1, MT_ERROR, ERR_CONNECTION_LOST)
                # sendMsgToUI(packedData)
                # return

            # Unpack the message header
            len_, type_ = struct.unpack('II', headerData)
            len_ = socket.ntohl(len_)
            type_ = socket.ntohl(type_)
            # print("header len_ ", len_, "header type_ ", type_)

            # Buffer to store the received message
            buffer = bytearray(len_)

            # Receive data into the buffer
            bytesReceived = 0
            while bytesReceived < len_:
                chunk = clientSock.recv(len_ - bytesReceived)
                if not chunk:
                    # Handle error or connection closed
                    break
                buffer[bytesReceived:bytesReceived + len(chunk)] = chunk
                bytesReceived += len(chunk)

            # Check if all expected bytes have been received
            if bytesReceived != len_:
                continue

            packedData = struct.pack(f'>II{len(buffer)}s', len_, type_, buffer)

            if type_ == MT_IMAGE:
                image_buffer = buffer.copy()
                # if frame_queue.full():
                #   frame_queue.get()
                # frame_queue.put(image_buffer)                

                if frame_stack.full():
                    frame_stack.get()
                
                frame_stack.put((image_buffer, targetStatus, targetNum))


                # Add Image Filter
                packedData = add_image_filter(buffer)

                # init_model_status = get_init_status()

                # if init_model_status is None:
                #     init_packedData = init_model_image(buffer)
                #     sendMsgToUI(init_packedData)
                # else:
                #     
                sendMsgToUI(packedData)

                # calculate the frame
                time.sleep(0.01)
                frameCnt += 1
                currentTime = time.time()
                elapsedTime = currentTime - startTime
                
                if elapsedTime > 0:
                    fps = frameCnt / elapsedTime
                    sendFpsToUI(fps)
            elif type_ == MT_STATE:
                valueInt = int.from_bytes(buffer, byteorder='big')
                if valueInt == 11:
                    print("set target status to after firing")
                    setTargetStatus(TARGET_AFTER_FIRE)
                else:
                    sendMsgToUI(packedData)
            elif type == MT_CALIB_COMMANDS:
                #print("len_ ", len_, "header type_ ", type_, "data_", buffer)
                #print("buffer: ", buffer)
                panInt = int.from_bytes(buffer[:4], byteorder='big')
                panfloat = struct.pack('>I', panInt)
                calibPan = struct.unpack('>f', panfloat)[0]

                tiltInt = int.from_bytes(buffer[4:], byteorder='big')
                tiltfloat = struct.pack('>I', tiltInt)
                calibTilt = struct.unpack('>f', tiltfloat)[0]
                print(calibPan, " ", calibTilt)
            else:
                #print("len_ ", len_, "header type_ ", type_, "data_", int.from_bytes(buffer, byteorder='big'))
                sendMsgToUI(packedData)

        except socket.timeout:
            # print("At tcp_protocol thread check : ", shutdown_event.is_set())
            continue  # For non-blocking mode when using recv(), we set timeout thus continuing recv()
        except socket.error as e:
            print(f"Network error occurred: {e}")
            packedData = struct.pack(">IIB", 1, MT_ERROR, ERR_CONNECTION_LOST)
            sendMsgToUI(packedData)
            callback_shutdown_event = 1

    clientSock.close()
    callback_shutdown_event = 0 # reset callback_shutdown_event
    print("tcp_ip_thread Thread is closed successfully.")

def sendEmptyMsg(msg):
    global clientSock
    data = bytearray()
    data.extend(struct.pack('>II', 1, msg))
    data.append(255)
    #print("sendEmptyMsg : ", msg)
    clientSock.sendall(data)

def check_label_10(result_data):
    # for box_info in result_data:    
    #     for box in box_info:
    #         if box["label"] == "10":
    #             return True
    return False

def buildTagetOrientation(msg):
    print("target sequence: ", msg)

    # get target orientation
    global clientSock
    global autoEngageStop
    global targetNum
    global calibPan
    global calibTilt

    cnt = 0
    buffer = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
    prev_data = []
    for i in msg:
        if i != 0:
            buffer[cnt] = i - 48
            cnt = cnt + 1

    targetLabelData = get_result_model()
    if targetLabelData is not None:
        #print("Target Info")
        for i in range(cnt):
            if autoEngageStop == True:
                print("Stop ongoing fire target")
                break

            #print("target num: ", buffer[i])
            for target in targetLabelData['target_info']:
                if autoEngageStop == True:
                    print("Stop ongoing fire target")
                    break

                label = target.get('label', 'N/A')
                if buffer[i] == int(label):
                    targetNum = buffer[i]
                    detectCnt = 0
                    #lastPan = -99.99
                    #lastTilt = -99.99
                    lastPan = calibPan
                    lastTilt = calibTilt
                    lastX = 0
                    lastY = 0
                    pan = 0
                    tilt = 0
                    sameCoordinateCnt = 0
                    findCnt = 0
                    print("move to target: ", targetNum)
                    while detectCnt < 1:
                        setTargetStatus(TARGET_BEFORE_FIRE)
                        time.sleep(0.01)
                        sendTargetNumToUI(targetNum)
                        if autoEngageStop == True:
                            print("Stop ongoing fire target")
                            break
                        data = bytearray()
                        targetCenterData = get_result_model()
                        findTarget = False
                        for target in targetCenterData['target_info']:
                            label = target.get('label', 'N/A')
                            if buffer[i] == int(label):
                                area = target.get('area', 0)
                                center = target.get('center', [0, 0])
                                #print("center: ", center)
                                findTarget = True
                                findCnt = 0
                                break
                        
                        if findTarget == False:
                            findCnt += 1
                            if findCnt > 100:
                                sendEmptyMsg(MT_GO_CENTER)
                                findCnt = 0
                                lastX = 0
                                lastY = 0
                                continue

                        centerX = 0
                        centerY = 0
                        cnt = 0
                        for value in center:
                            if cnt == 0:
                                centerX = value
                                cnt = 1
                            else:
                                centerY = value

                        if sameCoordinateCnt > 800:
                            print("same coordinate count over 800, move to center")
                            sendEmptyMsg(MT_GO_CENTER)
                            sameCoordinateCnt = 0
                            lastX = 0
                            lastY = 0
                            continue

                        if lastX == centerX and lastY == centerY:
                            sameCoordinateCnt = sameCoordinateCnt + 1
                            #print(center)
                            continue

                        lastX = centerX
                        lastY = centerY

                        data.extend(struct.pack('>II', 8, MT_TARGET_DIFF))

                        if getTargetStage(area) == TARGET_STATGE_1:
                            panError = (centerX - 20) - WIDTH/2
                            tiltError = (centerY - 40) - HEIGHT/2
                        elif getTargetStage(area) == TARGET_STATGE_2:
                            panError = (centerX - 20) - WIDTH/2
                            tiltError = (centerY - 40) - HEIGHT/2
                        elif getTargetStage(area) == TARGET_STATGE_3:
                            panError = (centerX - 10) - WIDTH/2
                            tiltError = (centerY - 50) - HEIGHT/2
                        elif getTargetStage(area) == TARGET_STATGE_4:
                            panError = (centerX + 5) - WIDTH/2
                            tiltError = (centerY - 35) - HEIGHT/2
                        elif getTargetStage(area) == TARGET_STATGE_5:
                            panError = (centerX + 5) - WIDTH/2
                            tiltError = (centerY - 30) - HEIGHT/2
                        else:
                            panError = (centerX - 20) - WIDTH/2
                            tiltError = (centerY - 40) - HEIGHT/2

                        pan = pan - panError/65
                        convertValue = send_float(pan)
                        data.extend(struct.pack('>I', convertValue))

                        tilt = tilt - tiltError/65
                        convertValue = send_float(tilt)
                        data.extend(struct.pack('>I', convertValue))

                        if compareCoordinate(lastPan, lastTilt, pan, tilt) == True:
                            detectCnt = detectCnt + 1
                            print("detectCnt: ", detectCnt)

                        lastPan = pan
                        lastTilt = tilt

                        #print("data: ", data)
                        clientSock.sendall(data)
                        #safe_send_data(data)

                    print("sameCoordinateCnt: ", sameCoordinateCnt)
                    sameCoordinateCnt = 0
                    if autoEngageStop == False:
                        setTargetStatus(TARGET_FIRING)
                        sendEmptyMsg(MT_FIRE)
                        time.sleep(0.1)
                        #sendEmptyMsg(MT_GO_CENTER)
                    break

        sendEmptyMsg(MT_COMPLETE)
        time.sleep(3)
        sendEmptyMsg(MT_GO_CENTER)
        autoEngageStop = False
        setTargetStatus(TARGET_NONE)

def sendMsgToCannon(msg):
    global clientSock
    global autoEngageStop

    type = msg[4:8]
    value = msg[8:]

    typeInt = int.from_bytes(type, byteorder='big')
    #print("msg: ", msg, "len: ", len(msg), "type: ", typeInt, "value: ", value)
    if typeInt == MT_TARGET_SEQUENCE:
        print("type is MT_TARGET_SEQUENCE: ", value)
        task_queue.put(value)
    elif typeInt == MT_COMMANDS:
        valueInt = int.from_bytes(value, byteorder='big')
        if valueInt == 255:
            autoEngageStop = True
        else:
            clientSock.sendall(msg)
    else:
        clientSock.sendall(msg)

def sendMsgToUI(msg):
    if uimsg_update_callback:
        uimsg_update_callback(msg)
    else:
        print("No callback function set for image update.")

def sendFpsToUI(fps):
    if fps_update_callback:
        # print("fps sending... : ", fps)
        fps_update_callback(fps)
    else:
        print("No callback functions set for fps update.")

def sendTargetNumToUI(targetNum):
    buffer = f"Current Target is {targetNum}"
    encoded_buffer = buffer.encode('utf-8')
    len_ = len(buffer)
    type_ = MT_TEXT
    packedData = struct.pack(f'>II{len_}s', len_, type_, encoded_buffer)
    sendMsgToUI(packedData)

def sendTextToUIFoundLabel10():
    buffer = f"Abnormal Target Detected"
    encoded_buffer = buffer.encode('utf-8')
    len_ = len(buffer)
    type_ = MT_TEXT
    packedData = struct.pack(f'>II{len_}s', len_, type_, encoded_buffer)
    sendMsgToUI(packedData)
    
def buildTargetOrientationThread(shutdown_event):
    while not shutdown_event.is_set(): # and callback_shutdown_event == 0:
        try:
            msg = task_queue.get(timeout=1)  # 1초 동안 대기
            buildTagetOrientation(msg)
        except queue.Empty:
            continue
        except task_queue.empty():
            continue
    print("BuildTargetOrientationThread is closed successfully.")

def send_float(number):
    # change float to int by 4byte network order
    packed_float = struct.pack('>f', number)
    uint32_val = struct.unpack('>I', packed_float)[0]
    
    return uint32_val

def compareCoordinate(lastPan, lastTilt, pan, tilt):
    #print(lastPan, " ", pan, " ", lastTilt, " ", tilt)

    x = abs(lastPan - pan)
    y = abs(lastTilt - tilt)

    if  x < 0.3 and y < 0.3:
        return True
    else:
        return False

def getFps():
    global fps
    return fps

def setTargetStatus(status):
    global targetStatus
    targetStatus = status
    #print("target status: ", targetStatus)
 
def getTargetStatus():
    global targetStatus
    return targetStatus

def getTargetNum():
    global targetNum
    return targetNum

def getTargetStage(area):
    # TARGET_STATGE_1 = 1 # 13 inch / area over 6000
    # TARGET_STATGE_2 = 2 # 18 inch / area 3500 - 6000
    # TARGET_STATGE_3 = 3 # 23 - 28 inch / area 1000 - 3500
    # TARGET_STATGE_4 = 4 # 34 - 35 inch / area 600 - 1000
    # TARGET_STATGE_5 = 5 # 36 inch / area under 600
    stage = 0
    if area > 6000:
        stage = TARGET_STATGE_1
    elif area < 6000 and area > 3500:
        stage = TARGET_STATGE_2
    elif area < 3500 and area > 1000:
        stage = TARGET_STATGE_3
    elif area < 1000 and area > 600:
        stage = TARGET_STATGE_4
    elif area < 600:
        stage = TARGET_STATGE_5
    
    #print("## stage ", stage, " ", area)
    return stage

def stopAutoEngageMode():
    global autoEngageStop

    if autoEngageStop == False and getTargetStatus() != TARGET_NONE:
        autoEngageStop = True
        sendTextToUIFoundLabel10()
