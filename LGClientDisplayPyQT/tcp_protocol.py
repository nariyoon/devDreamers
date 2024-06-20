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
# testtest
CAP_PROP_FRAME_WIDTH = 1920
CAP_PROP_FRAME_HEIGHT = 1080

# Define message structures
class TMesssageHeader:
    def __init__(self, len_, type_):
        self.Len = len_
        self.Type = type_

clientSock = 0

# Define for updating image to UI
image_update_callback = None

# Callback function for sending image to UI
def set_image_update_callback(callback):
    # print("Callback function parameter sent.")
    global image_update_callback
    image_update_callback = callback

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
        exit()

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

            if type_ == MT_IMAGE:
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

                # TODO: send image to ui when manual mode
                format_string = f'II{len(buffer)}s'
                msg_len = len_
                msg_type = MT_IMAGE
                packed_data = struct.pack(format_string, msg_len, msg_type, buffer)
                sendMsgToUI(packed_data)

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

                cv2.imshow('camera', imageMat)
                key = cv2.waitKey(1)
                if key & 0xFF == ord('q'):
                    break

            else:
                print("bypass to UI")
                print("len_ ", len_, "header type_ ", type_)
                msg = clientSock.recv(512)
                #msg = clientSock.recv(len_ + len(headerData))
                sendMsgToUI(msg)
                # sendToUi

        except socket.error as e:
            if e.errno == errno.ECONNRESET:
                print("Client disconnected.")
            else:
                print("Connection lost:", str(e))
            break
    cv2.destroyAllWindows()
    clientSock.close()
    print("Network Thread Exit")

def sendMsgToCannon(msg):
    global clientSock
    type = msg[4:8]
    typeInt = int.from_bytes(type, byteorder='big')

    print("recieve the msg. from UI for sending msg. to cannon( ", msg, "len: ", len(msg), "type: ", typeInt, ")")
    if typeInt == MT_TARGET_SEQUENCE:
        # send to image process
        print("type is MT_TARGET_SEQUENCE")
    elif typeInt == MT_COMMANDS:
        # send to command process
        print("type is MT_COMMANDS")
        clientSock.sendall(msg)
    else:
        clientSock.sendall(msg)

def sendMsgToUI(msg):
    print("send command to UI(len: ", len(msg), ")")
    # send callback to UI
    # recv_callback(msg)
    if image_update_callback:
        print("Callback function is called.")
        image_update_callback(msg)
    else:
        print("No callback function set for image update.")
