import sys
import cv2
import os
import glob
import time
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
import numpy as np
import json
import tabulate

from detect_square import *
from matching_digit import *
from knn_test import *
from tensorflow_test import *
from tesseract_test import *
from yolo_test import *

class Algorithm:
    def run(self, image, draw_image):
        raise NotImplementedError("Subclasses should implement this!")
class OpenCVDefaultAlgorithm(Algorithm):
    def __init__(self, symbols):
        self.symbols = symbols

    def run(self, image, draw_image):
        start_time = time.time()
        squares = find_squares(image)
        squares_time = time.time()
        result = match_digits(image, draw_image, squares, self.symbols)
        end_time = time.time()
        return result, (end_time - start_time), 0

class KNNAlgorithm(Algorithm):
    def __init__(self, model_path):
        self.model = KNNDetector(knn_model_path=model_path)
    def run(self, image, draw_image):
        start_time = time.time()
        squares = find_squares(image)
        squares_time = time.time()
        result = self.model.recognize_digits(image, draw_image, squares)
        end_time = time.time()
        return result, (end_time - start_time), 0

class YOLOAlgorithm(Algorithm):
    def __init__(self, model_path):
        self.model = YOLO_Detector(model_path=model_path)

    def run(self, image, draw_image):
        start_time = time.time()
        result, _ = self.model.detect(image, draw_image)
        end_time = time.time()
        return result, (end_time - start_time), 0


class TFLiteAlgorithm(Algorithm):
    def __init__(self, model_path):
        self.model = ObjectDetector(model_path=model_path)

    def run(self, image, draw_image):
        start_time = time.time()
        result, _ = self.model.detect(image, draw_image)
        end_time = time.time()
        return result, (end_time - start_time), 0
    


class PytesseractAlgorithm(Algorithm):
    def __init__(self):
        self.model = Pytesseract()

    def run(self, image, draw_image):
        start_time = time.time()
        squares = find_squares(image)
        squares_time = time.time()
        result, exec_time = self.model.detect(image, draw_image, squares)
        end_time = time.time()
        return result, (end_time - start_time), (squares_time - start_time)

def save_label_data(image_file, matched_squares, label_file):
    if os.path.exists(label_file):
        with open(label_file, 'r') as f:
            label_data = json.load(f)
    else:
        label_data = {"images": []}

    image_data = {
        "file": image_file,
        "annotations": []
    }

    for sq, recognized_digit in matched_squares:
        if isinstance(sq, list) and len(sq) == 2:
            x, y, w, h = sq[0][0], sq[0][1], sq[1][0] - sq[0][0], sq[1][1] - sq[0][1]
        else:
            x, y, w, h = cv2.boundingRect(sq)
        image_data["annotations"].append({"label": recognized_digit, "bbox": [x, y, x+w, y+h]})

    label_data["images"].append(image_data)

    with open(label_file, 'w') as f:
        json.dump(label_data, f, indent=4)
def manual_label(image, matched_squares):
    def draw_rectangle(event, x, y, flags, param):
        nonlocal drawing, ix, iy, ex, ey, current_rectangle, manual_squares
        if event == cv2.EVENT_LBUTTONDOWN:
            drawing = True
            ix, iy = x, y
        elif event == cv2.EVENT_MOUSEMOVE:
            if drawing:
                ex, ey = x, y
                current_rectangle = [(ix, iy), (ex, ey)]
        elif event == cv2.EVENT_LBUTTONUP:
            drawing = False
            ex, ey = x, y
            current_rectangle = [(ix, iy), (ex, ey)]
            label = input(f"Enter label for the rectangle at ({ix},{iy}) to ({ex},{ey}): ")
            if label.isdigit():
                manual_squares.append((current_rectangle, int(label)))
                cv2.rectangle(image, (ix, iy), (ex, ey), (0, 255, 0), 2)
                cv2.putText(image, label, (ix, iy - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)

    drawing = False
    ix, iy = -1, -1
    ex, ey = -1, -1
    current_rectangle = []
    manual_squares = []

    cv2.namedWindow('Manual Labeling')
    cv2.setMouseCallback('Manual Labeling', draw_rectangle)

    while True:
        temp_image = image.copy()
        if current_rectangle:
            cv2.rectangle(temp_image, current_rectangle[0], current_rectangle[1], (0, 255, 0), 2)
        
        # Draw already detected squares
        for sq, digit in matched_squares:
            x, y, w, h = cv2.boundingRect(sq)
            cv2.rectangle(temp_image, (x, y), (x+w, y+h), (255, 0, 0), 2)
            cv2.putText(temp_image, str(digit), (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 0, 0), 2)

        cv2.imshow('Manual Labeling', temp_image)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('s'):  # Save and exit
            cv2.destroyWindow('Manual Labeling')
            return True, manual_squares
        elif key == ord('q'):  # Quit without saving
            cv2.destroyWindow('Manual Labeling')
            return False, manual_squares

    cv2.destroyAllWindows()

import os
import cv2
import json
from ultralytics import YOLO
import glob

def process_images(algorithms, auto_generate=True, labeling_mode=False):
    script_dir = os.path.dirname(os.path.realpath(__file__))
    image_dir = f"{script_dir}/dataset/NewTrainingRaw/images"
    image_files = sorted(glob.glob(f"{image_dir}/*.jpg"))
    print(f"image_files length {len(image_files)}")

    if labeling_mode:
        label_file = f"{script_dir}/labels.json"
        if os.path.exists(label_file):
            os.remove(label_file)  # 기존 파일 삭제

    times = {alg.__class__.__name__: [] for alg in algorithms}
    counts = {alg.__class__.__name__: [] for alg in algorithms}
    detected_counts = {alg.__class__.__name__: [] for alg in algorithms}
    correct_counts = {alg.__class__.__name__: [] for alg in algorithms}
    error_detect_counts = {alg.__class__.__name__: [] for alg in algorithms}
    error_counts = {alg.__class__.__name__: [] for alg in algorithms}

    frame_cnt = 0

    # Load ground truth labels
    label_file = f"{script_dir}/NewTrainingRaw_labels_updated.json"
    with open(label_file, 'r') as f:
        ground_truth_data = json.load(f)

    def get_ground_truth(image_file):
        file_name = os.path.basename(image_file)
        for image_data in ground_truth_data["images"]:
            if image_data["file"] == file_name:
                return [ann for ann in image_data["annotations"] if ann["label"] != -1]
        return []

    while frame_cnt < len(image_files):
        image_file = image_files[frame_cnt]
        frame_0 = cv2.imread(image_file)
        draw_frame = frame_0.copy()
        if frame_0 is None or frame_0.size == 0:
            print(f"Failed to load {image_files[frame_cnt]}, frame_cnt: {frame_cnt}")
            frame_cnt += 1
            continue

        frame_detected_counts = {alg.__class__.__name__: 0 for alg in algorithms}
        frame_correct_counts = {alg.__class__.__name__: 0 for alg in algorithms}
        frame_error_detect_counts = {alg.__class__.__name__: 0 for alg in algorithms}
        frame_error_counts = {alg.__class__.__name__: 0 for alg in algorithms}

        for algorithm in algorithms:
            result, exec_time, squares_time = algorithm.run(frame_0, draw_frame)
            print(f"ALGO {algorithm.__class__.__name__} time {exec_time}")
            times[algorithm.__class__.__name__].append(exec_time)
            counts[algorithm.__class__.__name__].append(len(result) if not isinstance(result, int) else result)

            # Check detected boxes against ground truth
            ground_truth = get_ground_truth(image_file)
            for sq, digit in result:
                if isinstance(sq, list) and len(sq) == 2:
                    (xmin, ymin), (xmax, ymax) = sq
                else:
                    x, y, w, h = cv2.boundingRect(sq)
                    xmin, ymin, xmax, ymax = x, y, x + w, y + h
                detected_center_x = (xmin + xmax) // 2
                detected_center_y = (ymin + ymax) // 2

                detected = False
                for gt in ground_truth:
                    gt_xmin, gt_ymin, gt_xmax, gt_ymax = gt["bbox"]
                    if (gt_xmin <= detected_center_x <= gt_xmax) and (gt_ymin <= detected_center_y <= gt_ymax):
                        frame_detected_counts[algorithm.__class__.__name__] += 1
                        detected = True
                        if str(digit) == str(gt["label"]):
                            frame_correct_counts[algorithm.__class__.__name__] += 1
                        else:
                            frame_error_counts[algorithm.__class__.__name__] += 1
                        break
                if not detected:
                    frame_error_detect_counts[algorithm.__class__.__name__] += 1

            # Draw detected centers and labels
            for sq, digit in result:
                if isinstance(sq, list) and len(sq) == 2:
                    (xmin, ymin), (xmax, ymax) = sq
                else:
                    x, y, w, h = cv2.boundingRect(sq)
                    xmin, ymin, xmax, ymax = x, y, x + w, y + h
                center_x = (xmin + xmax) // 2
                center_y = (ymin + ymax) // 2
                cv2.circle(draw_frame, (center_x, center_y), 3, (0, 255, 255), -1)
                cv2.putText(draw_frame, str(digit), (xmin, ymin - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 0, 0), 2)

        # Store frame-level counts
        for alg_name in algorithms:
            algorithm_name = alg_name.__class__.__name__
            detected_counts[algorithm_name].append(frame_detected_counts[algorithm_name])
            correct_counts[algorithm_name].append(frame_correct_counts[algorithm_name])
            error_detect_counts[algorithm_name].append(frame_error_detect_counts[algorithm_name])
            error_counts[algorithm_name].append(frame_error_counts[algorithm_name])

        # Draw ground truth centers and labels
        for gt in ground_truth:
            gt_xmin, gt_ymin, gt_xmax, gt_ymax = gt["bbox"]
            cv2.rectangle(draw_frame, (gt_xmin, gt_ymin), (gt_xmax, gt_ymax), (0, 255, 0), 2)
            cv2.putText(draw_frame, str(gt["label"]), (gt_xmin, gt_ymin - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)

        for alg_name in algorithms:
            algorithm_name = alg_name.__class__.__name__
            cv2.putText(draw_frame, f"{algorithm_name}: detected {frame_detected_counts[algorithm_name]}, correct {frame_correct_counts[algorithm_name]}, errors {frame_error_counts[algorithm_name]}, error detect {frame_error_detect_counts[algorithm_name]}", 
                        (10, 30 + 20 * algorithms.index(alg_name)), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

        screen_res = 960, 540
        scale_width = screen_res[0] / draw_frame.shape[1]
        scale_height = screen_res[1] / draw_frame.shape[0]
        scale = min(scale_width, scale_height)
        window_width = int(draw_frame.shape[1] * scale)
        window_height = int(draw_frame.shape[0] * scale)

        cv2.namedWindow('IMAGE', cv2.WINDOW_NORMAL)
        cv2.resizeWindow('IMAGE', window_width, window_height)
        cv2.imshow('IMAGE', draw_frame)

        force_exit = False
        if not auto_generate:
            while True:
                key = cv2.waitKey(0)  # waitKey(0) to wait for key press
                if key & 0xFF == ord('q'):
                    force_exit = True
                    break
                elif key & 0xFF == ord('n'):
                    frame_cnt += 1
                    break
                elif key & 0xFF == ord('b'):
                    frame_cnt = max(0, frame_cnt - 1)  # prevent negative index
                    break
        else:
            cv2.waitKey(1)
            frame_cnt += 1
        
        if force_exit == True:
            break

    cv2.destroyAllWindows()

    return times, counts, detected_counts, correct_counts, error_counts, error_detect_counts



def load_ref_images(image_dir, num_signs, scale=0.50):
    symbols = []
    for i in range(num_signs):
        filename = f"{image_dir}/T{i}.jpg"
        img = cv2.imread(filename, cv2.IMREAD_GRAYSCALE)
        if img is None:
            # print(f"Failed to load {filename}")
            continue
        img = cv2.resize(img, (0, 0), fx=scale, fy=scale)
        _, img = cv2.threshold(img, 100, 255, cv2.THRESH_BINARY)
        symbols.append({"img": img, "name": str(i)})
    return symbols
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
from tabulate import tabulate

def plot_results(times, counts, detected_counts, correct_counts, error_counts, error_detect_counts):
    fig, axs = plt.subplots(2, 1, figsize=(12, 10))
    x = list(range(len(next(iter(times.values())))))

    # Plot processing times
    for alg_name, alg_times in times.items():
        mean_time = np.mean(alg_times)
        std_time = np.std(alg_times)
        axs[0].plot(x, alg_times, label=f'{alg_name} (mean: {mean_time:.2f}s, std: {std_time:.2f}s)')
    axs[0].set_xlabel('Image Index')
    axs[0].set_ylabel('Time (seconds)')
    axs[0].set_title('Processing Time for Different Methods')
    axs[0].legend()
    axs[0].grid(True)
    axs[0].xaxis.set_major_locator(MaxNLocator(integer=True))

    # Plot detected counts
    for alg_name, alg_counts in counts.items():
        mean_count = np.mean(alg_counts)
        std_count = np.std(alg_counts)
        axs[1].plot(x, alg_counts, label=f'{alg_name} (mean: {mean_count:.2f}, std: {std_count:.2f})')
    axs[1].set_xlabel('Image Index')
    axs[1].set_ylabel('Count')
    axs[1].set_title('Detected Counts for Different Methods')
    axs[1].legend()
    axs[1].grid(True)
    axs[1].xaxis.set_major_locator(MaxNLocator(integer=True))

    plt.tight_layout()
    plt.show()

    # Display summary table
    summary_data = []
    total_images = len(x)
    total_gt_labels = total_images * 10  # assuming each image has 10 labels

    for alg_name in correct_counts.keys():
        total_detected = np.sum(detected_counts[alg_name])
        total_correct = np.sum(correct_counts[alg_name])
        total_errors = np.sum(error_counts[alg_name])
        total_error_detect = np.sum(error_detect_counts[alg_name])
        
        detected_percentage = (total_detected / total_gt_labels) * 100
        correct_percentage = (total_correct / total_detected) * 100 if total_detected > 0 else 0
        error_percentage = (total_errors / total_detected) * 100 if total_detected > 0 else 0
        error_detect_percentage = (total_error_detect / total_gt_labels) * 100

        summary_data.append([
            alg_name,
            f"{total_detected}", f"{total_correct}", f"{total_errors}", f"{total_error_detect}",
            f"{detected_percentage:.2f}%", f"{correct_percentage:.2f}%", f"{error_percentage:.2f}%", f"{error_detect_percentage:.2f}%"
        ])

    headers = [
        "Algorithm",
        "Total Detected", "Total Correct", "Total Errors", "Total Error Detect",
        "Detected %", "Correct %", "Errors %", "Error Detect %"
    ]

    print(tabulate(summary_data, headers=headers, tablefmt='pretty'))

    # Create a figure for the table
    fig_table, ax_table = plt.subplots(figsize=(12, 6))
    ax_table.axis('tight')
    ax_table.axis('off')

    # Create table
    table = ax_table.table(cellText=summary_data, colLabels=headers, cellLoc='center', loc='center')
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1.2, 1.2)  # Adjust table scale

    plt.tight_layout()
    plt.show()

# Example usage
# plot_results(times, counts, detected_counts, correct_counts, error_counts, error_detect_counts)


if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.realpath(__file__))
    ref_image_dir = f"{script_dir}/../Targets/"
    num_signs = 10  # Define the number of reference images
    symbols = load_ref_images(ref_image_dir, num_signs)

    algorithms = [
        OpenCVDefaultAlgorithm(symbols),
        # KNNAlgorithm(f"{script_dir}/knn_train_data.pkl"),
        TFLiteAlgorithm(f"{script_dir}/../TfLite-2.17/Data/detect.tflite"),
        YOLOAlgorithm(f"{script_dir}/../VisionComm/src/image_algo/models/best.pt"),
        # PytesseractAlgorithm()
    ]

    auto_generate = True  # True for automatic processing, False for manual processing
    labeling_mode = False  # True for labeling mode
    times, counts, detected_counts, correct_counts, error_counts, error_detect_counts = process_images(algorithms, auto_generate, labeling_mode)
    plot_results(times, counts, detected_counts, correct_counts, error_counts, error_detect_counts)
