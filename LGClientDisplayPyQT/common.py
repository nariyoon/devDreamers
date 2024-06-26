import threading
from queue import Queue
from tcp_protocol import tcp_ip_thread, frame_queue, frame_stack
from image_process import init_image_processing_model, image_processing_thread

# frame_queue와 processed_queue를 tcp_protocol.py로 옮김

# Separate common_init() for implementation of Disconnect and Re-connection 
def common_init():
    # 이미지 처리 모델 초기화
    global img_model
    img_model = init_image_processing_model()

# After connection, running main thread 
def common_start(ip, port, shutdown_event):
    # while not shutdown_event.is_set():
    # TCP/IP 스레드 실행
    tcp_thread = threading.Thread(target=tcp_ip_thread, args=(ip, port, shutdown_event))
    tcp_thread.start()

    # 이미지 처리 스레드 실행
    processing_thread = threading.Thread(target=image_processing_thread, args=(frame_stack, img_model, shutdown_event))
    processing_thread.start()

    # 스레드가 완료될 때까지 대기
    tcp_thread.join()
    frame_queue.put(None)  # 종료 신호
    processing_thread.join()
	# 정리 작업 수행
    print("Common thread is closed successfully.")

