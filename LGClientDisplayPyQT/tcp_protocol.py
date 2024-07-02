# tcp_protocol.py
import socket
import struct
import errno
import cv2
import numpy as np
from image_process import get_result_model, get_init_status, init_model_image
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

# image width and height
WIDTH = 960
HEIGHT = 544
def print_socket_info():
    global clientSock
    # Get socket family (AF_INET, AF_INET6, ...)
    print(f"Socket family: {clientSock.family}")
    
    # Get socket type (SOCK_STREAM, SOCK_DGRAM, ...)
    print(f"Socket type: {clientSock.type}")
    
    # Get socket protocol (0 if unknown)
    print(f"Socket protocol: {clientSock.proto}")
    
    # Get local address and port
    print(f"Local address: {clientSock.getsockname()}")
    
    # Get remote address and port if connected
    if clientSock.fileno() != -1:  # Check if socket is connected
        print(f"Remote address: {clientSock.getpeername()}")
    else:
        print("Socket is not connected.")

# Define message structures
class TMesssageHeader:
    def __init__(self, len_, type_):
        self.Len = len_
        self.Type = type_

# global variables
clientSock = 0
fps = 0
callback_shutdown_event = 0

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
                frame_stack.put(image_buffer)

                init_model_status = get_init_status()

                if init_model_status is None:
                    init_packedData = init_model_image(buffer)
                    sendMsgToUI(init_packedData)
                else:
                    sendMsgToUI(packedData)

                # calculate the frame
                time.sleep(0.01)
                frameCnt += 1
                currentTime = time.time()
                elapsedTime = currentTime - startTime
                
                if elapsedTime > 0:
                    fps = frameCnt / elapsedTime
                    # #print(f"FPS: {fps:.2f}", end='\r')
                    # fps_info.append({"fps": fps})
                    # fps_queue.put(fps_info)
                    sendFpsToUI(fps)
            else:
                #print("len_ ", len_, "header type_ ", type_, "data_", int.from_bytes(buffer, byteorder='big'))
                sendMsgToUI(packedData)

        except socket.timeout:
            print("At tcp_protocol thread check : ", shutdown_event.is_set())
            continue  # For non-blocking mode when using recv(), we set timeout thus continuing recv()
        except socket.error as e:
            print(f"Network error occurred: {e}")
            packedData = struct.pack(">IIB", 1, MT_ERROR, ERR_CONNECTION_LOST)
            sendMsgToUI(packedData)
            callback_shutdown_event = 1

    clientSock.close()
    callback_shutdown_event = 0 # reset callback_shutdown_event
    print("tcp_ip_thread Thread is closed successfully.")

# Function to check if the socket is connected
def is_socket_connected():
    global clientSock
    try:
        # the following sends zero bytes over the socket
        # this is generally a no-op that should succeed only if the socket is open
        clientSock.sendall(b'', flags=clientSock.MSG_DONTWAIT)
        return True
    except socket.error as e:
        # socket is not open if send raises an error
        # specific errors like EAGAIN or EWOULDBLOCK indicate socket is open but cannot send right now
        return False
    except Exception as e:
        return False

# Function to safely send data
def safe_send_data(data):
    global clientSock
    if is_socket_connected():
        try:
            clientSock.sendall(data)
            print("Data sent successfully.")
        except socket.error as e:
            print(f"Failed to send data: {e}")
    else:
        print("Socket is not connected.")

def sendEmptyMsg(msg):
    global clientSock
    data = bytearray()
    data.extend(struct.pack('>II', 1, msg))
    data.append(255)
    print("sendEmptyMsg : ", msg)
    #safe_send_data(data)
    clientSock.sendall(data)

def buildTagetOrientation(msg):
    print("target sequence: ", msg)

    # get target orientation
    global clientSock
    cnt = 0
    buffer = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
    for i in msg:
        if i != 0:
            buffer[cnt] = i - 48
            cnt = cnt + 1

    targetLabelData = get_result_model()
    if targetLabelData is not None:
        print("Target Info")
        for i in range(cnt):
            print("target num: ", buffer[i])
            for target in targetLabelData['target_info']:
                label = target.get('label', 'N/A')
                if buffer[i] == int(label):
                    print("target is found: ", int(label))
                    detectCnt = 0
                    lastPan = -99.99
                    lastTilt = -99.99
                    lastX = 0
                    lastY = 0
                    pan = 0
                    tilt = 0
                    sameCoordinateCnt = 0
                    print("move to target")
                    while detectCnt < 1:
                        time.sleep(0.01)
                        data = bytearray()
                        targetCenterData = get_result_model()
                        for target in targetCenterData['target_info']:
                            label = target.get('label', 'N/A')
                            if buffer[i] == int(label):
                                center = target.get('center', [0, 0])
                                break

                        centerX = 0
                        centerY = 0
                        cnt = 0
                        for value in center:
                            if cnt == 0:
                                centerX = value
                                cnt = 1
                            else:
                                centerY = value

                        if sameCoordinateCnt > 1000:
                            print("same coordinate count over 500, move to center")
                            sendEmptyMsg(MT_GO_CENTER)
                            sameCoordinateCnt = 0
                            continue

                        if lastX == centerX and lastY == centerY:
                            sameCoordinateCnt = sameCoordinateCnt + 1
                            #print(center)
                            continue

                        lastX = centerX
                        lastY = centerY

                        data.extend(struct.pack('>II', 8, MT_TARGET_DIFF))

                        if centerX > 450: # dectect right side
                            panError = (centerX + 20) - WIDTH/2
                        else:
                            panError = (centerX) - WIDTH/2
                        pan = pan - panError/75
                        convertValue = send_float(pan)
                        data.extend(struct.pack('>I', convertValue))

                        if centerX > 450: # dectect right side
                            tiltError = (centerY - 30) - HEIGHT/2 # 70
                        else:
                            tiltError = (centerY - 40) - HEIGHT/2 # 70
                        tilt = tilt - tiltError/75
                        convertValue = send_float(tilt)
                        data.extend(struct.pack('>I', convertValue))

                        if compareCoordinate(lastPan, lastTilt, pan, tilt) == True:
                            detectCnt = detectCnt + 1
                            print("detectCnt: ", detectCnt)

                        lastPan = pan
                        lastTilt = tilt

                        print("data: ", data)
                        clientSock.sendall(data)
                        #safe_send_data(data)

                    print("sameCoordinateCnt: ", sameCoordinateCnt)
                    sameCoordinateCnt = 0
                    sendEmptyMsg(MT_FIRE)

                    break
                else:
                    print("can not find target")

        sendEmptyMsg(MT_COMPLETE)
	    #Below is sample to let go aim to the center(if it can't find the target)
        time.sleep(3)
        sendEmptyMsg(MT_GO_CENTER)
    else:
        print("no target_info")

def sendMsgToCannon(msg):
    global clientSock

    type = msg[4:8]
    value = msg[8:]

    typeInt = int.from_bytes(type, byteorder='big')
    print("msg: ", msg, "len: ", len(msg), "type: ", typeInt, "value: ", value)
    if typeInt == MT_TARGET_SEQUENCE:
        print("type is MT_TARGET_SEQUENCE: ", value)
        task_queue.put(value)
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
    print(lastPan, " ", pan, " ", lastTilt, " ", tilt)

    x = abs(lastPan - pan)
    y = abs(lastTilt - tilt)

    if  x < 0.3 and y < 0.3:
        return True
    else:
        return False

def getFps():
    global fps

    return fps
