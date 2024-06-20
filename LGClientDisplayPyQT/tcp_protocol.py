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

# def tcp_ip_thread(frame_queue):
#     """
#     This thread handles TCP/IP communication with the Raspberry Pi.
#     """
#     print("start receiving image thread")
#     host = '127.0.0.1'  # Localhost for testing, change to Raspberry Pi IP
#     port = 5000  # Port to listen on
#     # host = '192.168.0.224'  # Localhost for testing, change to Raspberry Pi IP
#     # port = 5001  # Port to listen on

#     serverAddress = (host, port)
#     clientSock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

#     try:
#         clientSock.connect(serverAddress)
#     except socket.error as e:
#         print("Failed to connect to server:", e)
#         # # Test Image function call
#         # with open('c:\\test.jpg', 'rb') as f:
#         #     image_data = f.read()
#         # # 포맷 문자열을 정의합니다: 'II'는 두 개의 integer, 'I'는 바이트 배열의 길이를 나타내는 integer, f'{len(byte_array)}s'는 가변 길이의 바이트 배열
#         # format_string = f'II{len(image_data)}s'
#         # # struct.pack을 사용하여 데이터를 패킹합니다.
#         # msg_len = len(image_data)
#         # msg_type = 3  # MT_IMAGE
#         # packed_data = struct.pack(format_string, msg_len, msg_type, image_data)
#         # sendMsgToUI(packed_data)
#         exit()

def tcp_ip_thread(frame_queue, ip, port):
    """
    This thread handles TCP/IP communication with the Raspberry Pi.
    """
    print("start receiving image thread")
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as clientSock:
            clientSock.connect((ip, port))
    except Exception as e:
        print(f"TCP/IP thread encountered an error: {e}")
        
        # Test Image function call
        with open('c:\\test.jpg', 'rb') as f:
            image_data = f.read()
        # 포맷 문자열을 정의합니다: 'II'는 두 개의 integer, 'I'는 바이트 배열의 길이를 나타내는 integer, f'{len(byte_array)}s'는 가변 길이의 바이트 배열
        format_string = f'II{len(image_data)}s'
        # struct.pack을 사용하여 데이터를 패킹합니다.
        msg_len = len(image_data)
        msg_type = 3  # MT_IMAGE
        packed_data = struct.pack(format_string, msg_len, msg_type, image_data)
        sendMsgToUI(packed_data)

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
                # print("buffer lenn ", len(buffer))

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

                # 이미지를 디코딩
                imageMat = cv2.imdecode(np.frombuffer(buffer, dtype=np.uint8), cv2.IMREAD_COLOR)

                # 이미지 크기 확인 (옵션: 필요에 따라 제한 설정)
                height, width = imageMat.shape[:2]
                print(f"height {height} width {width}")

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
                msg = clientSock.recv(512)
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
    print("recieve the msg. from UI for sending msg. to cannon(len: ", len(msg), ")")
    global clientSock
    type = msg[4:7]
    type = int.from_bytes(type, byteorder='little', signed=True)

    if type == MT_TARGET_SEQUENCE:
        # send to image process
        print("type is MT_TARGET_SEQUENCE")
    elif type == MT_COMMANDS:
        # send to command process
        print("type is MT_COMMANDS", type)
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