import cv2
import numpy as np
import tensorflow as tf

class ObjectDetector:
    def __init__(self, model_path):
        self.interpreter = tf.lite.Interpreter(model_path=model_path)
        self.interpreter.allocate_tensors()
 
        # Get input and output tensors.
        self.input_details = self.interpreter.get_input_details()
        self.output_details = self.interpreter.get_output_details()

        self.input_height = self.input_details[0]['shape'][1]
        self.input_width = self.input_details[0]['shape'][2]
        self.input_channels = self.input_details[0]['shape'][3]

    def detect(self, image, score_threshold=0.5):
        input_tensor = cv2.resize(image, (self.input_width, self.input_height))
        input_tensor = cv2.cvtColor(input_tensor, cv2.COLOR_BGR2RGB)
        input_tensor = np.expand_dims(input_tensor, axis=0)
        input_tensor = (np.float32(input_tensor) - 127.5) / 127.5

        self.interpreter.set_tensor(self.input_details[0]['index'], input_tensor)
        self.interpreter.invoke()

        if self.output_details[0]['name'] == 'StatefulPartitionedCall:1':
            boxes = self.interpreter.get_tensor(self.output_details[1]['index'])
            classes = self.interpreter.get_tensor(self.output_details[3]['index'])
            scores = self.interpreter.get_tensor(self.output_details[0]['index'])
            num_detections_tensor = self.interpreter.get_tensor(self.output_details[2]['index'])
        else:
            boxes = self.interpreter.get_tensor(self.output_details[0]['index'])
            classes = self.interpreter.get_tensor(self.output_details[1]['index'])
            scores = self.interpreter.get_tensor(self.output_details[2]['index'])
            num_detections_tensor = self.interpreter.get_tensor(self.output_details[3]['index'])

        num_detections = int(num_detections_tensor[0])

        boxes = boxes[0][:num_detections]
        classes = classes[0][:num_detections].astype(np.int32)
        scores = scores[0][:num_detections]

        height, width, _ = image.shape
        result = []
        for i in range(len(scores)):
            if scores[i] > score_threshold:
                ymin, xmin, ymax, xmax = boxes[i]
                xmin = int(xmin * width)
                xmax = int(xmax * width)
                ymin = int(ymin * height)
                ymax = int(ymax * height)

                # label = f"{classes[i]}: {int(scores[i] * 100)}%"
                # label_size, baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
                # label_ymin = max(ymin, label_size[1] + 10)
                label = f"{classes[i]}"
                result.append(([(xmin, ymin), (xmax, ymax)], label))

        return result

