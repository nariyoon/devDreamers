# tcp_protocol.py
import socket
import struct
import errno
import cv2
import numpy as np
import image_process as ip
#from cmd import handle_command

# Define message types
MT_COMMANDS = 1
MT_TARGET_SEQUENCE = 2
MT_IMAGE = 3
MT_TEXT = 4
MT_PREARM = 5
MT_STATE = 6
MT_STATE_CHANGE_REQ = 7
MT_CALIB_COMMANDS = 8

# Define message structures
class TMesssageHeader:
    def __init__(self, len_, type_):
        self.Len = len_
        self.Type = type_

def tcp_ip_thread():
    """
    This thread handles TCP/IP communication with the Raspberry Pi.
    """
    print("start ip thread!!!!!!!!!!!!!!!")
    host = '192.168.0.224'  # Localhost for testing, change to Raspberry Pi IP
    port = 5000             # Port to listen on

    serverAddress = (host, port)
    clientSock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    try:
        clientSock.connect(serverAddress)
    except socket.error as e:
        print("Failed to connect to server:", e)
        exit()

    cv2.namedWindow("camera", cv2.WINDOW_NORMAL)
    while True:
        try:
            # Receive the message header
            header_data = clientSock.recv(8)
            if len(header_data) != struct.calcsize('II'):
                print("Connection lost.")
                break

            # Unpack the message header
            len_, type_ = struct.unpack('II', header_data)
            len_ = socket.ntohl(len_)
            type_ = socket.ntohl(type_)
            print("header len_ ", len_, "header type_ ", type_)

            # Buffer to store the received message
            buffer = bytearray(len_)
            print("buffer lenn ", len(buffer))

            # Receive data into the buffer
            bytes_received = 0
            while bytes_received < len_:
                chunk = clientSock.recv(len_ - bytes_received)
                if not chunk:
                    # Handle error or connection closed
                    break
                buffer[bytes_received:] = chunk
                bytes_received += len(chunk)

            # Check if all expected bytes have been received
            if bytes_received != len_:
                # Handle incomplete message reception
                pass

            # Receive the message body
            #if len(body_data) != len_:
            #    print("Connection lost.")
            #    break

            if type_ == MT_IMAGE:
                # Process the received message based on its typeSsizeof(TMesssageHeader)), cv::IMREAD_COLOR, &ImageIn);
                imageMat = cv2.imdecode(np.frombuffer(buffer, dtype=np.uint8), cv2.IMREAD_COLOR)
                #ip.recvCameraImage(imageMat)
                cv2.imshow('camera', imageMat)
                cv2.waitKey(1)
            else:
                print("bypass to UI")
                #sendToUi

        except socket.error as e:
            if e.errno == errno.ECONNRESET:
                print("Client disconnected.")
            else:
                print("Connection lost:", str(e))
            break

    cv2.destroyAllWindows()
    print("Network Thread Exit")
    return None