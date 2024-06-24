import threading
from queue import Queue
from tcp_protocol import tcp_ip_thread, frame_queue, processed_queue
from image_process import init_image_processing_model, image_processing_thread,send_image_to_ui_thread

# frame_queue와 processed_queue를 tcp_protocol.py로 옮김

def common_start(ip, port):
    # 이미지 처리 모델 초기화
    img_model = init_image_processing_model()

    # TCP/IP 스레드 실행
    tcp_thread = threading.Thread(target=tcp_ip_thread, args=(ip, port, img_model))
    tcp_thread.start()

    # 이미지 처리 스레드 실행
    processing_thread = threading.Thread(target=image_processing_thread, args=(frame_queue, processed_queue, img_model))
    processing_thread.start()

    # UI 전송 스레드 실행
    ui_thread = threading.Thread(target=send_image_to_ui_thread, args=(processed_queue,))
    ui_thread.start()

    # 스레드가 완료될 때까지 대기
    tcp_thread.join()
    frame_queue.put(None)  # 종료 신호
    processing_thread.join()
    processed_queue.put(None)  # 종료 신호
    ui_thread.join()
