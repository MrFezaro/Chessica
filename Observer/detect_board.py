import cv2
import numpy as np
import math

# =========================
# Chessboard configuration
# =========================
board_size = (7, 7)  # inner corners (cols, rows)

# =========================
# Open camera
# =========================
cap = cv2.VideoCapture(1)

cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

criteria = (
    cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER,
    30,
    0.001
)

while True:
    ret, frame = cap.read()
    if not ret:
        break

    h, w = frame.shape[:2]
    cam_center = np.array([w // 2, h // 2])

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    found, corners = cv2.findChessboardCorners(
        gray,
        board_size,
        cv2.CALIB_CB_ADAPTIVE_THRESH + cv2.CALIB_CB_NORMALIZE_IMAGE
    )

    if found:
        corners = cv2.cornerSubPix(
            gray,
            corners,
            (11, 11),
            (-1, -1),
            criteria
        )

        cv2.drawChessboardCorners(frame, board_size, corners, found)

        # =========================
        # Middle corner position
        # =========================
        mid_index = (board_size[0] * board_size[1]) // 2
        mid_pt = corners[mid_index].ravel()

        # Position difference (pixels)
        pos_error = mid_pt - cam_center

        # Draw center & middle point
        cv2.circle(frame, tuple(cam_center), 5, (255, 0, 0), -1)
        cv2.circle(frame, tuple(mid_pt.astype(int)), 5, (0, 0, 255), -1)
        cv2.line(frame, tuple(cam_center), tuple(mid_pt.astype(int)), (0, 255, 0), 2)

        # =========================
        # Rotation estimation (2D yaw)
        # =========================
        # Use first and last corner in top row
        p0 = corners[0].ravel()
        p1 = corners[board_size[0] - 1].ravel()

        dx = p1[0] - p0[0]
        dy = p1[1] - p0[1]

        yaw_error = math.degrees(math.atan2(dy, dx))

        # =========================
        # Display text
        # =========================
        cv2.putText(
            frame,
            f"Pos error (px): X={pos_error[0]:.1f}, Y={pos_error[1]:.1f}",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 255, 0),
            2
        )

        cv2.putText(
            frame,
            f"Yaw error (deg): {yaw_error:.2f}",
            (10, 60),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 255, 0),
            2
        )

    cv2.imshow("Chessboard Center Error", frame)

    if cv2.waitKey(1) & 0xFF == 27:
        break

cap.release()
cv2.destroyAllWindows()
