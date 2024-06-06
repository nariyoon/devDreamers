import cv2

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



def draw_squares(img, squares):
    for square, digit in squares:
        cv2.polylines(img, [square], True, (0, 0, 255), 3)
        # x, y = np.mean(square, axis=0).astype(int)
        # cv2.putText(img, digit, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)