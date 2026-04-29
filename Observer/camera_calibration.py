import cv2
import numpy as np
import os

CHECKERBOARD = (9, 6)
SAVE_DIR = "./calib_images"
os.makedirs(SAVE_DIR, exist_ok=True)

cap = cv2.VideoCapture(2)  # change index if needed
count = 0

print("Hold a checkerboard in front of the camera.")
print("  SPACE - save current frame as calibration image")
print("  Q     - quit and run calibration")

while True:
    ret, frame = cap.read()
    if not ret:
        break

    display = frame.copy()
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    ret_cb, corners = cv2.findChessboardCorners(gray, CHECKERBOARD, None)
    if ret_cb:
        cv2.drawChessboardCorners(display, CHECKERBOARD, corners, ret_cb)
        cv2.putText(display, "Board detected - press SPACE to save",
                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    else:
        cv2.putText(display, "No board detected",
                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

    cv2.putText(display, f"Saved: {count}/20",
                (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 220, 255), 2)
    cv2.imshow("Calibration Capture", display)

    key = cv2.waitKey(1) & 0xFF
    if key == ord('q'):
        break
    elif key == ord(' ') and ret_cb:
        path = os.path.join(SAVE_DIR, f"calib_{count:03d}.jpg")
        cv2.imwrite(path, frame)
        count += 1
        print(f"Saved {path}")
    elif key == ord(' ') and not ret_cb:
        print("Board not detected in this frame — move it and try again.")

cap.release()
cv2.destroyAllWindows()

# ── calibrate ─────────────────────────────────────────────────────────────────

if count < 10:
    print(f"Only {count} images captured — need at least 10. Run again.")
    exit()

print(f"\nCalibrating from {count} images...")

criteria = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
objp = np.zeros((CHECKERBOARD[0] * CHECKERBOARD[1], 3), np.float32)
objp[:, :2] = np.mgrid[0:CHECKERBOARD[0], 0:CHECKERBOARD[1]].T.reshape(-1, 2)

obj_points, img_points = [], []
import glob
for fname in glob.glob(f"{SAVE_DIR}/*.jpg"):
    img = cv2.imread(fname)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    ret, corners = cv2.findChessboardCorners(gray, CHECKERBOARD, None)
    if ret:
        obj_points.append(objp)
        corners = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)
        img_points.append(corners)

h, w = cv2.imread(glob.glob(f"{SAVE_DIR}/*.jpg")[0]).shape[:2]
rms, K, dist, _, _ = cv2.calibrateCamera(obj_points, img_points, (w, h), None, None)

print(f"RMS reprojection error: {rms:.4f}  (good if < 1.0)")
os.makedirs("./Observer", exist_ok=True)
np.save("./Observer/camera_matrix.npy", K)
np.save("./Observer/dist_coeffs.npy", dist)
print("Saved ./Observer/camera_matrix.npy and ./Observer/dist_coeffs.npy")