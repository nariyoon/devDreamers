from filterpy.kalman import KalmanFilter
from image_process import get_result_model
import numpy as np

class KalmanBoxTracker:
    def __init__(self):
        self.kf = KalmanFilter(dim_x=4, dim_z=2)
        self.kf.F = np.array([[1, 0, 1, 0],
                              [0, 1, 0, 1],
                              [0, 0, 1, 0],
                              [0, 0, 0, 1]])
        self.kf.H = np.array([[1, 0, 0, 0],
                              [0, 1, 0, 0]])
        self.kf.R[0:, 0:] *= 10.
        self.kf.P[2:, 2:] *= 1000.
        self.kf.P *= 10.
        self.kf.Q[-1, -1] *= 0.01
        self.kf.Q[2:, 2:] *= 0.01

    def predict(self):
        self.kf.predict()
        return self.kf.x[:2]

    def update(self, point):
        self.kf.update(point)