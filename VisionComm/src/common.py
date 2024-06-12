import threading
from image_process import image_processing_thread
from tcp_protocol import tcp_ip_thread

def main():
    # Image processing thread
    img_thread = threading.Thread(target=image_processing_thread)
    # TCP/IP communication thread
    tcp_thread = threading.Thread(target=tcp_ip_thread)

    # Start threads
    img_thread.start()
    tcp_thread.start()

    # Join threads to ensure they complete before main thread exits
    img_thread.join()
    tcp_thread.join()

if __name__ == "__main__":
    main()
