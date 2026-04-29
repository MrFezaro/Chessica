#!/usr/bin/env python3
import cv2
import sys
from pupil_apriltags import Detector

FOCUS_STEP       = 1
FOCUS_MIN        = 0
FOCUS_MAX        = 255
DECISION_MARGIN  = 5  # raise to reduce false positives (0–100+)

def apply_manual_camera_settings(cap):
    cap.set(cv2.CAP_PROP_AUTOFOCUS,        0)
    cap.set(cv2.CAP_PROP_AUTO_EXPOSURE,    1)
    cap.set(cv2.CAP_PROP_EXPOSURE,        -6)
    cap.set(cv2.CAP_PROP_AUTO_WB,          0)
    cap.set(cv2.CAP_PROP_WB_TEMPERATURE, 4600)
    cap.set(cv2.CAP_PROP_GAIN,             0)

def draw_overlay(frame, focus, num_tags):
    overlay = frame.copy()
    w = frame.shape[1]
    cv2.rectangle(overlay, (0, 0), (w, 40), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.5, frame, 0.5, 0, frame)
    cv2.putText(frame,
                f"Focus: {focus} (W/S)  |  SPACE = capture  |  Q = quit  |  Tags found: {num_tags}",
                (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

def detect_and_draw(frame, detector):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    tags = detector.detect(gray)

    # Filter low-confidence detections
    tags = [t for t in tags if t.decision_margin >= DECISION_MARGIN]

    for tag in tags:
        corners = tag.corners.astype(int)
        for j in range(4):
            cv2.line(frame, tuple(corners[j]), tuple(corners[(j + 1) % 4]),
                     (0, 255, 0), 2)
        cx, cy = int(tag.center[0]), int(tag.center[1])
        cv2.putText(frame, f"ID {tag.tag_id}  m={tag.decision_margin:.0f}",
                    (cx - 30, cy - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        print(f"  Tag ID {tag.tag_id} at ({cx}, {cy})  margin={tag.decision_margin:.1f}")

    return frame, len(tags)

def main():
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Error: Cannot open USB webcam.")
        sys.exit(1)

    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  1920)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)

    apply_manual_camera_settings(cap)

    focus = 0
    cap.set(cv2.CAP_PROP_FOCUS, focus)

    detector = Detector(
        families="tag16h5",
        nthreads=4,
        quad_decimate=1.0,   # full resolution for single-shot accuracy
        quad_sigma=0.0,
        refine_edges=1,
        decode_sharpening=0.25,
    )

    win_name  = "AprilTag — Live Preview"
    snap_name = "AprilTag — Captured"
    cv2.namedWindow(win_name,  cv2.WINDOW_NORMAL)
    cv2.namedWindow(snap_name, cv2.WINDOW_NORMAL)

    print("W/S = focus  |  SPACE = capture  |  Q = quit")

    # Show live feed but don't detect until capture
    while True:
        ret, frame = cap.read()
        if not ret:
            print("Frame grab failed.")
            break

        preview = frame.copy()
        draw_overlay(preview, focus, num_tags=0)
        cv2.imshow(win_name, preview)

        key = cv2.waitKey(1) & 0xFF

        if key == ord('q'):
            break

        elif key == ord(' '):
            print(f"\nCapturing... (decision_margin threshold: {DECISION_MARGIN})")
            snap = frame.copy()
            snap, n = detect_and_draw(snap, detector)
            draw_overlay(snap, focus, num_tags=n)
            cv2.imshow(snap_name, snap)
            print(f"Done — {n} tag(s) detected.\n")

        elif key == ord('w'):
            focus = min(FOCUS_MAX, focus + FOCUS_STEP)
            cap.set(cv2.CAP_PROP_FOCUS, focus)
            print(f"Focus: {focus}")

        elif key == ord('s'):
            focus = max(FOCUS_MIN, focus - FOCUS_STEP)
            cap.set(cv2.CAP_PROP_FOCUS, focus)
            print(f"Focus: {focus}")

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()