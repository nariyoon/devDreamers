# tcp_protocol.py
import socket
import struct
import errno
import cv2
import numpy as np
from image_process import get_result_model
from queue import Queue, Full
import os
from queue import LifoQueue
import threading

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

# Define message structures
class TMesssageHeader:
    def __init__(self, len_, type_):
        self.Len = len_
        self.Type = type_

# global variables
clientSock = 0

# Define for updating image to UI
uimsg_update_callback = None

# Callback function for sending image to UI
def set_uimsg_update_callback(callback):
    # print("Callback function parameter sent.")
    global uimsg_update_callback
    uimsg_update_callback = callback

# frame_queue와 processed_queue를 tcp_protocol.py로 옮김
frame_queue = Queue(maxsize=10)
frame_stack = LifoQueue(maxsize=10)

def tcp_ip_thread(ip, port, shutdown_event):
    """
    This thread handles TCP/IP communication with the Raspberry Pi.
    """

    print("start receiving image thread: ", ip, "(", port, ")")
    global clientSock
    serverAddress = (ip, port)
    clientSock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    try:
        clientSock.connect(serverAddress)
    except socket.error as e:
        print("Failed to connect to server:", e)
        errorCode = ERR_FAIL_TO_CONNECT
        packedData = struct.pack(">IIB", 1, MT_ERROR, errorCode)
        sendMsgToUI(packedData) # ERR_FAIL_TO_CONNECT
        return

    errorCode = ERR_SUCCESS
    packedData = struct.pack(">IIB", 1, MT_ERROR, errorCode)
    sendMsgToUI(packedData)

    # while True:
    while not shutdown_event.is_set():
        try:
            # Receive the message header
            headerData = clientSock.recv(8)
            if len(headerData) != struct.calcsize('II'):
                print("Connection lost.")
                break

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
            sendMsgToUI(packedData)

            if type_ == MT_IMAGE:                
                image_buffer = buffer.copy()
                # if frame_queue.full():
                #         frame_queue.get()
                # frame_queue.put(image_buffer)                

                if frame_stack.full():
                    frame_stack.get()
                frame_stack.put(image_buffer)

            else:
                print("len_ ", len_, "header type_ ", type_, "data_", int.from_bytes(buffer, byteorder='big'))
                #sendMsgToUI(packedData)

        except socket.error as e:
            print("Connection lost:", str(e))
            packedData = struct.pack(">IIB", 9, MT_ERROR, ERR_CONNECTION_LOST)
            sendMsgToUI(packedData)
            break
        pass

    clientSock.close()
    print("Network Thread Exit")

def sendMsgToCannon(msg):
    global clientSock
    global cannonStatus

    type = msg[4:8]
    value = msg[8:]

    typeInt = int.from_bytes(type, byteorder='big')
    print("msg: ", msg, "len: ", len(msg), "type: ", typeInt, "value: ", value)
    if typeInt == MT_TARGET_SEQUENCE:
       print("type is MT_TARGET_SEQUENCE: ", value)
       stopEvent = threading.Event()
       armedThread = threading.Thread(target=buildTagetOrientation, args=(value, stopEvent))
       armedThread.start()
       armedThread.join()
       print("armedThread has stopped.")
    elif typeInt == MT_STATE_CHANGE_REQ:
        print("type is MT_STATE_CHANGE_REQ")
        clientSock.sendall(msg)
    elif typeInt == MT_PREARM:
        print("type is MT_PREARM")
        clientSock.sendall(msg)
    else:
        print("type is MT_ELSE")
        clientSock.sendall(msg)

def sendMsgToUI(msg):
    if uimsg_update_callback:
        uimsg_update_callback(msg)
    else:
        print("No callback function set for image update.")

def buildTagetOrientation(msg, stopEvent):
    print("target sequence: ", msg)

    # get target orientation
    global clientSock
    #data = bytearray()
    cnt = 0
    buffer = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
    for i in msg:
        if i != 0:
            buffer[cnt] = i - 48
            cnt = cnt + 1

    # add length and type
    #dataLen = 8 # x coordiate(4byte) + y coordinate(4byte)
    #data.extend(struct.pack('>II', dataLen, MT_TARGET_DIFF))

    # add target amount
    #data.extend(struct.pack('>I', cnt))
    
    targetLabelData = get_result_model()
    if targetLabelData is not None:
        print("Target Info")
        for i in range(cnt):
            print("target num: ", buffer[i])
            for target in targetLabelData['target_info']:
                label = target.get('label', 'N/A')
                #print(f"!! Label: {label}", "label int: ", int(label))
                if buffer[i] == int(label):
                    detectCnt = 0
                    lastPan = -9999.99
                    lastTilt = -9999.99
                    lastX = 0
                    lastY = 0
                    pan = 0
                    tilt = 0
                    print("move to target")
                    while detectCnt < 2:
                        data = bytearray()
                        targetCenterData = get_result_model()
                        for target in targetCenterData['target_info']:
                            label = target.get('label', 'N/A')
                            #print(f"Label: {label}", "label int: ", int(label))
                            if buffer[i] == int(label):
                                center = target.get('center', [0, 0])
                                #print("center: ", center)
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
                        
                        if lastX == centerX and lastY == centerY:
                            #print("last: ", lastX, " ", lastY, "center: ", center)
                            continue

                        lastX = centerX
                        lastY = centerY

                        # length and type
                        data.extend(struct.pack('>II', 8, MT_TARGET_DIFF))

                        # x coordinate
                        panError = (centerX + 70) - WIDTH/2
                        pan = pan - panError/75
                        convertValue = send_float(pan)
                        data.extend(struct.pack('>I', convertValue))

                        # y coordinate
                        tiltError = (centerY - 88) - HEIGHT/2
                        tilt = tilt - tiltError/75
                        convertValue = send_float(tilt)
                        data.extend(struct.pack('>I', convertValue))

                        #print("@@", lastPan, " ", lastTilt, " ", pan, " ", tilt)
                        if compareCoordinate(lastPan, lastTilt, pan, tilt) == True:
                            detectCnt = detectCnt + 1
                            print("detectCnt: ", detectCnt)
                        
                        lastPan = pan
                        lastTilt = tilt

                        # send msg
                        print("data: ", data)
                        clientSock.sendall(data)

                        #print("100ms sleep")
                        #time.sleep(0.1)
                        # count = 0
                        # for value in center:
                        #     if count == 0:
                        #         calValue = (WIDTH / 2 - value) / 46 #24 #12
                        #         count = 1
                        #     else:
                        #         calValue = (HEIGHT / 2 - value) / 7 # 13.6 #6.8
                        #     convertValue = send_float(calValue)
                        #     print(f"calValue: {calValue}, convertValue: {convertValue}")
                        #     data.extend(struct.pack('>I', convertValue))
                
                    data = bytearray()
                    data.extend(struct.pack('>II', 0, MT_FIRE))
                    print("fire: ", data)
                    clientSock.sendall(data)
                    # exit for taget if label is found
                    break
        
        data = bytearray()
        data.extend(struct.pack('>II', 0, MT_COMPLETE))
        print("complete: ", data)
        clientSock.sendall(data)
    else:
        print("no target_info")
    
    stopEvent.set()

def send_float(number):
    # float를 4바이트 네트워크 바이트 순서의 정수로 변환
    packed_float = struct.pack('>f', number)  # '>'는 big-endian을 의미함
    uint32_val = struct.unpack('>I', packed_float)[0]  # 4바이트의 네트워크 순서의 정수로 변환
    
    return uint32_val

def compareCoordinate(centerX, centerY, pan, tilt):
    print(centerX, " ", centerY, " ", pan, " ", tilt)

    x = abs(centerX - pan)
    y = abs(centerY - tilt)

    if  x < 0.5 and y < 0.5:
        return True
    else:
        return False
