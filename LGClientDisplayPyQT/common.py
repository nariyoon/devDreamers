import threading
from queue import Queue
from tcp_protocol import tcp_ip_thread
from image_process import start_image_processing

# frame_queue를 common.py로 옮김
frame_queue = Queue(maxsize=20)

def common_start(ip, port):
    # TCP/IP 스레드 실행
    tcp_thread = threading.Thread(target=tcp_ip_thread, args=(frame_queue, ip, port))
    tcp_thread.start()

    # 이미지 처리 함수 호출
    start_image_processing(frame_queue)

    # 스레드가 완료될 때까지 대기
    tcp_thread.join()


# if __name__ == "__main__":
#     main()
