from queue import Queue, Full
import queue
from queue import LifoQueue
from queue import Empty

# frame_queue와 processed_queue를 tcp_protocol.py로 옮김
frame_queue = Queue(maxsize=5)
frame_stack = LifoQueue(maxsize=5)
task_queue = Queue()

class OverwritingQueue(Queue):
    def __init__(self, maxsize):
        super().__init__(maxsize)

    def put(self, item, block=True, timeout=None):
        while True:
            try:
                super().put(item, block, timeout)
                break
            except Full:
                # 큐가 가득 차면, 가장 오래된 항목을 제거
                self.get_nowait()

# Save result data
target_queue = OverwritingQueue(maxsize=1)
box_queue = OverwritingQueue(maxsize=1)
fps_queue = OverwritingQueue(maxsize=1)

filter_index = None
def set_curr_filter(data):
    global filter_index
    filter_index = data

def get_curr_filter():
    global filter_index
    return filter_index