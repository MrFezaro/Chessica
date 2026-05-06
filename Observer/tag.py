#!/usr/bin/env python3
import cv2
import sys
from pupil_apriltags import Detector

DECISION_MARGIN = 30
FOCUS_STEP      = 1
FOCUS_MIN       = 0
FOCUS_MAX       = 255

def draw_overlay(frame, num_tags, focus, manual_focus):
    overlay = frame.copy()
    w = frame.shape[1]
    cv2.rectangle(overlay, (0, 0), (w, 40), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.5, frame, 0.5, 0, frame)
    focus_str = f"Focus: {focus} (W/S)" if manual_focus else "Focus: AUTO"
    cv2.putText(frame,
                f"{focus_str}  |  F = toggle  |  SPACE = capture  |  Q = quit  |  Tags: {num_tags}",
                (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

def detect_and_draw(frame, detector):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    tags = detector.detect(gray)
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

    manual_focus = False
    focus = 0

    detector = Detector(
        families="tag16h5",
        nthreads=4,
        quad_decimate=1.0,
        quad_sigma=0.0,
        refine_edges=1,
        decode_sharpening=0.25,
    )

    win_name  = "AprilTag — Live Preview"
    snap_name = "AprilTag — Captured"
    cv2.namedWindow(win_name,  cv2.WINDOW_NORMAL)
    cv2.namedWindow(snap_name, cv2.WINDOW_NORMAL)

    print("F = toggle focus  |  W/S = focus (manual)  |  SPACE = capture  |  Q = quit")

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Frame grab failed.")
            break

        preview = frame.copy()
        draw_overlay(preview, num_tags=0, focus=focus, manual_focus=manual_focus)
        cv2.imshow(win_name, preview)

        key = cv2.waitKey(1) & 0xFF

        if key == ord('q'):
            break

        elif key == ord('f'):
            manual_focus = not manual_focus
            if manual_focus:
                cap.set(cv2.CAP_PROP_AUTOFOCUS, 0)
                cap.set(cv2.CAP_PROP_FOCUS, focus)
                print(f"Manual focus ON  (focus={focus})")
            else:
                cap.set(cv2.CAP_PROP_AUTOFOCUS, 1)
                print("Autofocus ON")

        elif key == ord('w') and manual_focus:
            focus = min(FOCUS_MAX, focus + FOCUS_STEP)
            cap.set(cv2.CAP_PROP_FOCUS, focus)
            print(f"Focus: {focus}")

        elif key == ord('s') and manual_focus:
            focus = max(FOCUS_MIN, focus - FOCUS_STEP)
            cap.set(cv2.CAP_PROP_FOCUS, focus)
            print(f"Focus: {focus}")

        elif key == ord(' '):
            print(f"\nCapturing... (decision_margin threshold: {DECISION_MARGIN})")
            snap = frame.copy()
            snap, n = detect_and_draw(snap, detector)
            draw_overlay(snap, num_tags=n, focus=focus, manual_focus=manual_focus)
            cv2.imshow(snap_name, snap)
            print(f"Done — {n} tag(s) detected.\n")

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()