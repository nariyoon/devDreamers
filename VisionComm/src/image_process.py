# image_process.py

from image_algo.tensorflow_algo import process_with_tensorflow
from image_algo.opencv_algo import process_with_opencv

def image_processing_thread():
    """
    This thread handles image processing.
    OpenCV and TensorFlow are used for different image processing tasks.
    """
    while True:
        # Call the appropriate processing functions
        process_with_opencv()
        process_with_tensorflow()
        # Add any required synchronization or communication here
        pass
