# tcp_protocol.py
import socket
import struct
import errno
import cv2
import numpy as np
from image_process import image_processing_handler, get_result_model
from queue import Queue, Full
from message_utils import sendMsgToUI
import os

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


# frame_queue와 processed_queue를 tcp_protocol.py로 옮김
frame_queue = Queue(maxsize=20)
processed_queue = Queue(maxsize=20)


debug_dir = os.path.join(os.getcwd(), 'debug')
os.makedirs(debug_dir, exist_ok=True)



def tcp_ip_thread(ip, port, img_model):
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
    frame_cnt = 0
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

            

                # 이미지를 디코딩
                imageMat = cv2.imdecode(np.frombuffer(buffer, dtype=np.uint8), cv2.IMREAD_COLOR)

                save_path = os.path.join(debug_dir, f"frame_{int(frame_cnt)}.jpg")
                cv2.imwrite(save_path, imageMat)

                frame_queue.put(imageMat)
                results = get_result_model()
                if results != None:
                    # 결과 이미지 그리기
                    for result in results:
                        boxes = result.boxes
                        for box in boxes:
                            if box.conf[0].cpu().item() >= 0.5:  # 확률이 0.5 이상인 경우에만 그리기
                                coords = box.xyxy[0].cpu().numpy()
                                x1, y1, x2, y2 = map(int, coords)
                                label = f"{int(box.cls[0].cpu().item())} {box.conf[0].cpu().item():.2f}"
                                cv2.rectangle(imageMat, (x1, y1), (x2, y2), (0, 255, 0), 2)
                                cv2.putText(imageMat, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)

                    new_buffer = cv2.imencode('.jpg', imageMat)[1].tobytes()
                    msg_len = len(new_buffer)
                    msg_type = 3
                    format_string = f'>II{msg_len}s'
                    packed_data = struct.pack(format_string, msg_len, msg_type, new_buffer)

                    sendMsgToUI(packed_data)
                else:
                    sendMsgToUI(packedData)

                frame_cnt += 1    
                # 이미지 크기 확인 (옵션: 필요에 따라 제한 설정)
                #height, width = imageMat.shape[:2]
                #print(f"height {height} width {width}")

                # 이미지 크기 조정 (다른 곳에서 사용하는 포맷과 동일하게)
                # imageMat = cv2.resize(imageMat, (CAP_PROP_FRAME_WIDTH, CAP_PROP_FRAME_HEIGHT))

                # Put the image into the queue (if image size is valid)
                # try:
                #     frame_queue.put(imageMat, timeout=1)
                # except Full:
                #     print("Queue is full. Discarding oldest frame.")
                #     frame_queue.get()
                #     frame_queue.put(imageMat)
                # image_detect = image_processing_handler(img_model, imageMat)
                # sendMsgToUI(image_detect)

                # 수신한 이미지를 큐에 추가하여 처리하도록 함
                # 원본 이미지를 UI로 바로 전송
                # ui_image = cv2.imencode('.jpg', imageMat)[1].tobytes()
                # msg_len = len(ui_image)
                # msg_type = 3
                # format_string = f'>II{msg_len}s'
                # packed_data = struct.pack(format_string, msg_len, msg_type, ui_image)
                # sendMsgToUI(packed_data)


                #cv2.imshow('camera', imageMat)
                #key = cv2.waitKey(1)
                #if key & 0xFF == ord('q'):
                #    break
            elif MT_STATE:
                global cannonStatus
                valueInt = int.from_bytes(buffer, byteorder='big')
                print("state: ", buffer, " valueInt: ", valueInt)
                cannonStatus = valueInt
                sendMsgToUI(packedData)
            else:
                print("len_ ", len_, "header type_ ", type_, "data_", int.from_bytes(buffer, byteorder='big'))
                sendMsgToUI(packedData)

        except socket.error as e:
            if e.errno == errno.ECONNRESET:
                print("Client disconnected.")
            else:
                print("Connection lost:", str(e))
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

    print("recieve the msg. from UI for sending msg. to cannon( ", msg, "len: ", len(msg), "type: ", typeInt, "value: ", value, "/", valueInt, ")")
    if typeInt == MT_TARGET_SEQUENCE:
        # send to image process
        print("type is MT_TARGET_SEQUENCE")
    elif typeInt == MT_STATE_CHANGE_REQ:
        print("type is MT_STATE_CHANGE_REQ / value: ", valueInt)
        cannonStatus = valueInt
        clientSock.sendall(msg)
    else:
        print("type is MT_ELSE")
        clientSock.sendall(msg)

