import os
import cv2
import numpy as np
from ultralytics import YOLO

class YOLO_Detector:
    def __init__(self, model_path):
        self.model = YOLO(model_path)

    def detect(self, image, score_threshold=0.5):
        # img_model.predict(imageMat, imgsz=[960, 544], verbose=False)
        results = self.model.predict(image, imgsz=[960, 544], verbose=False)
        ret_array = []
        for result in results:
            for box in result.boxes:
                score = box.conf[0].cpu().item()
                label = f"{int(box.cls[0].cpu().item())}"
                if score < score_threshold:
                    continue
                coords = box.xyxy[0].cpu().numpy()
                x1, y1, x2, y2 = map(int, coords)
                ret_array.append(([(x1, y1), (x2, y2)], label))

        return ret_array
