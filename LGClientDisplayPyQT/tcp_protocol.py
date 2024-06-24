# tcp_protocol.py
import socket
import struct
import errno
import cv2
import numpy as np
import image_process as ip
from queue import Queue, Full
#from cmd import handle_command
# from RemoteUIPyQT_sendCmd import recv_callback
# from tcp_protocol import tcp_ip_thread

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

# testtest
CAP_PROP_FRAME_WIDTH = 1920
CAP_PROP_FRAME_HEIGHT = 1080

# Define message structures
class TMesssageHeader:
    def __init__(self, len_, type_):
        self.Len = len_
        self.Type = type_

# global variables
clientSock = 0
cannonStatus = UNKNOWN

# Define for updating image to UI
uimsg_update_callback = None

# Callback function for sending image to UI
def set_uimsg_update_callback(callback):
    # print("Callback function parameter sent.")
    global uimsg_update_callback
    uimsg_update_callback = callback

def tcp_ip_thread(frame_queue, ip, port):
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
        exit()

    errorCode = ERR_SUCCESS
    packedData = struct.pack(">IIB", 1, MT_ERROR, errorCode)
    sendMsgToUI(packedData)

    while True:
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

            if type_ == MT_IMAGE:
                # TODO: send image to ui when state is not auto-engage mode (if cannonState != ENGAGE_AUTO)
                sendMsgToUI(packedData)

                # 이미지를 디코딩
                imageMat = cv2.imdecode(np.frombuffer(buffer, dtype=np.uint8), cv2.IMREAD_COLOR)

                # 이미지 크기 확인 (옵션: 필요에 따라 제한 설정)
                #height, width = imageMat.shape[:2]
                #print(f"height {height} width {width}")

                # 이미지 크기 조정 (다른 곳에서 사용하는 포맷과 동일하게)
                imageMat = cv2.resize(imageMat, (CAP_PROP_FRAME_WIDTH, CAP_PROP_FRAME_HEIGHT))

                # Put the image into the queue (if image size is valid)
                try:
                    frame_queue.put(imageMat, timeout=2)
                except Full:
                    print("Queue is full. Discarding oldest frame.")
                    frame_queue.get()
                    frame_queue.put(imageMat)

                #cv2.imshow('camera', imageMat)
                #key = cv2.waitKey(1)
                #if key & 0xFF == ord('q'):
                #    break

            elif type_ == MT_STATE:
                global cannonStatus
                valueInt = int.from_bytes(buffer, byteorder='big')
                print("state: ", buffer, " valueInt: ", valueInt)
                cannonStatus = valueInt
                sendMsgToUI(packedData)
                
            else:
                print("len_ ", len_, "header type_ ", type_, "data_", int.from_bytes(buffer, byteorder='big'))
                sendMsgToUI(packedData)

        except socket.error as e:
            errorCode = ERR_CONNECTION_LOST
            if e.errno == errno.ETIMEDOUT or e.errno == errno.ECONNREFUSED:
                print("fail to connect.")
                errorCode = ERR_FAIL_TO_CONNECT
            else:
                print("Connection lost:", str(e))

            # send error code to UI
            packedData = struct.pack(">IIB", 9, MT_ERROR, errorCode)
            sendMsgToUI(packedData)
            break

    #cv2.destroyAllWindows()
    clientSock.close()
    print("Network Thread Exit")

def sendMsgToCannon(msg):
    global clientSock
    global cannonStatus

    type = msg[4:8]
    value = msg[8:]

    typeInt = int.from_bytes(type, byteorder='big')
    valueInt = int.from_bytes(value, byteorder='big')

    # print("recieve the msg. from UI for sending msg. to cannon( ", msg, "len: ", len(msg), "type: ", typeInt, "value: ", value, "/", valueInt, ")")
    if typeInt == MT_TARGET_SEQUENCE:
        # send to image process
        print("type is MT_TARGET_SEQUENCE")
        clientSock.sendall(msg)
    elif typeInt == MT_STATE_CHANGE_REQ:
        print("type is MT_STATE_CHANGE_REQ / value: ", valueInt)
        cannonStatus = valueInt
        clientSock.sendall(msg)
    elif typeInt == MT_PREARM:
        print("type is MT_PREARM")
        clientSock.sendall(msg)
    else:
        print("type is MT_ELSE")
        clientSock.sendall(msg)

def sendMsgToUI(msg):
    # print("send command to UI(len: ", len(msg), ")")
    # send callback to UI
    
    # recv_callback(msg)
    if uimsg_update_callback:
        print("Callback function is called.")
        uimsg_update_callback(msg)
    else:
        print("No callback function set for image update.")
