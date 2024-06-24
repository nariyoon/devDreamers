import os
import cv2
import numpy as np
from ultralytics import YOLO

class YOLO_Detector:
    def __init__(self, model_path):
        self.model = YOLO(model_path)
        self.model_name = "YOLOv8"

    def detect(self, image, draw_image, score_threshold=0.5):
        results = self.model.predict(image, imgsz=[960, 544])
        boxes, classes, scores = [], [], []

        for result in results:
            for box in result.boxes:
                score = box.conf[0].cpu().item()
                if score < score_threshold:
                    continue
                coords = box.xyxy[0].cpu().numpy()
                x1, y1, x2, y2 = map(int, coords)
                cls = int(box.cls[0].cpu().item())
                boxes.append((x1, y1, x2, y2))
                classes.append(cls)
                scores.append(score)

        result = self.draw_detections(draw_image, boxes, classes, scores, score_threshold)
        return result, (boxes, classes, scores, len(boxes))

    def draw_detections(self, image, boxes, classes, scores, score_threshold=0.5):
        result = []

        for i in range(len(scores)):
            x1, y1, x2, y2 = boxes[i]
            label = f"{classes[i]}: {int(scores[i] * 100)}%"
            label_size, baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
            cv2.putText(image, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            cv2.rectangle(image, (x1, y1), (x2, y2), (0, 255, 0), 2)
            result.append(([(x1, y1), (x2, y2)], classes[i]))
        return result
