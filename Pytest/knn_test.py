
import cv2
import numpy as np
import os
import pickle

class KNNDetector:
    def __init__(self, knn_model_path=None, knn_image_size=(28, 28), k=5):
        self.knn_image_size = knn_image_size
        self.k = k
        self.knn_model = None
        if knn_model_path:
            self.load_knn_model(knn_model_path)

    def augment_image(self, img):
        augmented_images = [img]

        # 다양한 변형 적용
        rows, cols = img.shape

        # 회전
        for angle in range(-10, 11, 5):
            M = cv2.getRotationMatrix2D((cols / 2, rows / 2), angle, 1)
            dst = cv2.warpAffine(img, M, (cols, rows))
            augmented_images.append(dst)

        # 이동
        for tx in range(-3, 4, 3):
            for ty in range(-3, 4, 3):
                M = np.float32([[1, 0, tx], [0, 1, ty]])
                dst = cv2.warpAffine(img, M, (cols, rows))
                augmented_images.append(dst)

        return augmented_images

    def load_knn_images(self, image_dir, num_signs):
        symbols = []
        knn_images = []
        knn_labels = []
        for i in range(num_signs):
            filename = f"{image_dir}/T{i}.jpg"
            img = cv2.imread(filename, cv2.IMREAD_GRAYSCALE)
            if img is None:
                continue

            _, bin_img = cv2.threshold(img, 100, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            symbols.append({"img": bin_img, "name": str(i)})

            # 증강된 이미지를 사용하여 학습 데이터 생성
            augmented_images = self.augment_image(bin_img)
            for aug_img in augmented_images:
                knn_img = cv2.resize(aug_img, self.knn_image_size)
                knn_images.append(knn_img.reshape(-1, np.prod(self.knn_image_size)).astype(np.float32))
                knn_labels.append(int(i))
        
        knn_images = np.array(knn_images).reshape(-1, np.prod(self.knn_image_size)).astype(np.float32)
        knn_labels = np.array(knn_labels).astype(np.int32)
        
        return symbols, knn_images, knn_labels

    def train_knn(self, knn_images, knn_labels):
        knn = cv2.ml.KNearest_create()
        knn.setDefaultK(self.k)
        knn.train(knn_images, cv2.ml.ROW_SAMPLE, knn_labels)
        self.knn_model = knn

    def recognize_digits(self, image, draw_image, squares):
        recognized_digits = []
        for sq in squares:
            x, y, w, h = cv2.boundingRect(sq)
            roi = image[y:y+h, x:x+w]
            roi_gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            roi_gray = cv2.GaussianBlur(roi_gray, (5, 5), 0)
            roi_gray = cv2.resize(roi_gray, self.knn_image_size)
            _, roi_gray = cv2.threshold(roi_gray, 100, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            roi_gray = roi_gray.reshape(-1, np.prod(self.knn_image_size)).astype(np.float32)

            ret, result, neighbours, dist = self.knn_model.findNearest(roi_gray, k=5)
            recognized_digit = int(result[0][0])
            recognized_digits.append((sq, recognized_digit))

            # 사각형 그리기
            # cv2.polylines(draw_image, [sq], True, (0, 255, 0), 2)
            label = f"Digit: {recognized_digit}"
            label_size, baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
            # cv2.rectangle(draw_image, (x, y - label_size[1] - 10), (x + label_size[0], y), (0, 255, 0), cv2.FILLED)
            cv2.putText(draw_image, label, (x, y - 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

        return recognized_digits

    def save_knn_model(self, knn_images, knn_labels, filename='knn_train_data.pkl'):
        with open(filename, 'wb') as f:
            pickle.dump((knn_images, knn_labels), f)

    def load_knn_model(self, filename='knn_train_data.pkl'):
        with open(filename, 'rb') as f:
            knn_images, knn_labels = pickle.load(f)
        self.train_knn(knn_images, knn_labels)