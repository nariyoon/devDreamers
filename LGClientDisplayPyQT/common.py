import threading
from queue import Queue
from tcp_protocol import buildTargetOrientationThread, tcp_ip_thread, frame_queue, frame_stack
from image_process import init_image_processing_model, image_processing_thread
from PyQt5.QtCore import QThread, pyqtSignal

# frame_queue와 processed_queue를 tcp_protocol.py로 옮김

# After connection, running main thread 
def common_start(ip, port, shutdown_event, form_instance):
    # while not shutdown_event.is_set():
    # 스레드 생성 및 시작
    armed_thread = threading.Thread(target=buildTargetOrientationThread, args=(shutdown_event,))
    armed_thread.start()
    # TCP/IP 스레드 실행
    tcp_thread = threading.Thread(target=tcp_ip_thread, args=(ip, port, shutdown_event))
    tcp_thread.start()



    # 이미지 처리 스레드 실행
    processing_thread = threading.Thread(target=image_processing_thread, args=(frame_stack, shutdown_event, form_instance))
    processing_thread.start()

    # 스레드가 완료될 때까지 대기
    armed_thread.join()
    tcp_thread.join()
    frame_stack.put(None)  # 종료 신호
    processing_thread.join()



	# 정리 작업 수행
    print("Common thread is closed successfully.")

