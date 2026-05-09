# calibrate.py
import cv2
import numpy as np
import glob, sys

CHECKERBOARD = (7, 7)       # inner corners (cols, rows) — count carefully
SQUARE_MM    = 30.0         # physical square size in mm
IMAGES_NEEDED = 20          # collect at least this many good frames

objp = np.zeros((CHECKERBOARD[0] * CHECKERBOARD[1], 3), np.float32)
objp[:, :2] = np.mgrid[0:CHECKERBOARD[0], 0:CHECKERBOARD[1]].T.reshape(-1, 2)
objp *= SQUARE_MM

obj_points = []   # 3D points in real-world space
img_points = []   # 2D points in image plane

cap = cv2.VideoCapture(1, cv2.CAP_DSHOW if sys.platform == "win32" else cv2.CAP_V4L2)
cap.set(cv2.CAP_PROP_FRAME_WIDTH,  1920)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)

cv2.namedWindow("Calibration", cv2.WINDOW_NORMAL)
print(f"Hold checkerboard in view. SPACE = capture sample. Need {IMAGES_NEEDED}. Q = done.")

while True:
    ret, frame = cap.read()
    if not ret:
        break

    gray    = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    found, corners = cv2.findChessboardCorners(gray, CHECKERBOARD, None)

    display = frame.copy()
    if found:
        cv2.drawChessboardCorners(display, CHECKERBOARD, corners, found)
        cv2.putText(display, f"Board found! SPACE to capture ({len(obj_points)}/{IMAGES_NEEDED})",
                    (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)
    else:
        cv2.putText(display, f"No board detected ({len(obj_points)}/{IMAGES_NEEDED})",
                    (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 2)

    cv2.imshow("Calibration", display)
    key = cv2.waitKey(1) & 0xFF

    if key == ord('q'):
        break
    elif key == ord(' ') and found:
        # Refine corner locations to subpixel accuracy
        corners2 = cv2.cornerSubPix(
            gray, corners, (11, 11), (-1, -1),
            (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
        )
        obj_points.append(objp)
        img_points.append(corners2)
        print(f"  Captured {len(obj_points)}/{IMAGES_NEEDED}")

        if len(obj_points) >= IMAGES_NEEDED:
            print("Enough samples — running calibration...")
            break

cap.release()
cv2.destroyAllWindows()

if len(obj_points) < 4:
    print("Not enough samples to calibrate.")
    sys.exit(1)

print("Calibrating...")
h, w = gray.shape
rms, camera_matrix, dist_coeffs, rvecs, tvecs = cv2.calibrateCamera(
    obj_points, img_points, (w, h), None, None
)

print(f"RMS reprojection error: {rms:.4f}  (good if < 1.0, great if < 0.5)")
print(f"Camera matrix:\n{camera_matrix}")
print(f"Distortion coeffs: {dist_coeffs.ravel()}")

np.savez("camera_calibration.npz",
         camera_matrix=camera_matrix,
         dist_coeffs=dist_coeffs,
         image_size=(w, h))
print("Saved to camera_calibration.npz")