import cv2
import numpy as np

COLS = 'abcdefgh'
ROWS = '87654321'  # top row = rank 8, bottom row = rank 1
BOARD_SIZE = 800
CELL = BOARD_SIZE // 8

# ── perspective helpers ────────────────────────────────────────────────────────

def get_matrices(pts):
    src = np.array(pts, dtype=np.float32)
    dst = np.array([[0,0],[BOARD_SIZE,0],[BOARD_SIZE,BOARD_SIZE],[0,BOARD_SIZE]], dtype=np.float32)
    M     = cv2.getPerspectiveTransform(src, dst)
    M_inv = cv2.getPerspectiveTransform(dst, src)
    return M, M_inv

def board_to_img(bx, by, M_inv):
    pt = np.array([[[float(bx), float(by)]]], dtype=np.float32)
    return tuple(cv2.perspectiveTransform(pt, M_inv)[0][0].astype(int))

def img_to_board(ix, iy, M):
    pt = np.array([[[float(ix), float(iy)]]], dtype=np.float32)
    return cv2.perspectiveTransform(pt, M)[0][0]

def pixel_to_chess(px, py, M):
    bx, by = img_to_board(px, py, M)
    col = int(bx / CELL)
    row = int(by / CELL)
    col = max(0, min(7, col))
    row = max(0, min(7, row))
    return COLS[col] + ROWS[row]

def get_board_mask(shape, pts):
    mask = np.zeros(shape[:2], dtype=np.uint8)
    cv2.fillPoly(mask, [np.array(pts, dtype=np.int32)], 255)
    return mask

# ── grid drawing ──────────────────────────────────────────────────────────────

def draw_grid(frame, M_inv, chess_coords, circles, colors):
    overlay = frame.copy()

    # Alternating square colours
    for r in range(8):
        for c in range(8):
            tl = board_to_img(c*CELL,       r*CELL,       M_inv)
            tr = board_to_img((c+1)*CELL,   r*CELL,       M_inv)
            br = board_to_img((c+1)*CELL,   (r+1)*CELL,   M_inv)
            bl = board_to_img(c*CELL,       (r+1)*CELL,   M_inv)
            poly = np.array([tl, tr, br, bl], dtype=np.int32)
            shade = (60, 60, 60) if (r + c) % 2 == 0 else (30, 30, 30)
            cv2.fillPoly(overlay, [poly], shade)

    # Highlight changed squares
    for i, coord in enumerate(chess_coords):
        if not coord:
            continue
        c = COLS.index(coord[0])
        r = ROWS.index(coord[1])
        tl = board_to_img(c*CELL,     r*CELL,     M_inv)
        tr = board_to_img((c+1)*CELL, r*CELL,     M_inv)
        br = board_to_img((c+1)*CELL, (r+1)*CELL, M_inv)
        bl = board_to_img(c*CELL,     (r+1)*CELL, M_inv)
        poly = np.array([tl, tr, br, bl], dtype=np.int32)
        cv2.fillPoly(overlay, [poly], colors[i])

    cv2.addWeighted(overlay, 0.45, frame, 0.55, 0, frame)

    # Grid lines
    for i in range(9):
        cv2.line(frame, board_to_img(i*CELL, 0, M_inv),
                        board_to_img(i*CELL, BOARD_SIZE, M_inv), (180,180,180), 1)
        cv2.line(frame, board_to_img(0, i*CELL, M_inv),
                        board_to_img(BOARD_SIZE, i*CELL, M_inv), (180,180,180), 1)

    # Column labels (a–h) along bottom edge
    for c in range(8):
        pt = board_to_img(int((c+0.5)*CELL), BOARD_SIZE - 18, M_inv)
        cv2.putText(frame, COLS[c], (pt[0]-6, pt[1]),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255,230,0), 1, cv2.LINE_AA)

    # Row labels (1–8) along left edge
    for r in range(8):
        pt = board_to_img(8, int((r+0.5)*CELL), M_inv)
        cv2.putText(frame, ROWS[r], (pt[0], pt[1]+5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255,230,0), 1, cv2.LINE_AA)

    # Coordinate label at square centre
    for i, coord in enumerate(chess_coords):
        if not coord:
            continue
        c = COLS.index(coord[0])
        r = ROWS.index(coord[1])
        centre = board_to_img(int((c+0.5)*CELL), int((r+0.5)*CELL), M_inv)
        cv2.putText(frame, coord, (centre[0]-14, centre[1]+6),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255,255,255), 2, cv2.LINE_AA)

# ── diff / circle detection ───────────────────────────────────────────────────

def find_top2_circles(diff, mask=None, threshold=25):
    gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY)
    if mask is not None:
        thresh = cv2.bitwise_and(thresh, mask)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return []
    contours = sorted(contours, key=cv2.contourArea, reverse=True)[:2]
    circles = []
    for cnt in contours:
        if cv2.contourArea(cnt) < 200:
            continue
        (cx, cy), radius = cv2.minEnclosingCircle(cnt)
        circles.append((int(cx), int(cy), int(radius)))
    return circles

# ── mouse callback ────────────────────────────────────────────────────────────

corner_pts = []
selecting = False

def mouse_cb(event, x, y, flags, param):
    global corner_pts, selecting
    if selecting and event == cv2.EVENT_LBUTTONDOWN:
        if len(corner_pts) < 4:
            corner_pts.append((x, y))
            print(f"  Corner {len(corner_pts)} set: ({x}, {y})")
            if len(corner_pts) == 4:
                selecting = False
                print("Board defined! Press SPACE to start capturing.")

# ── main ──────────────────────────────────────────────────────────────────────

def main():
    global corner_pts, selecting

    cap = cv2.VideoCapture(2)
    if not cap.isOpened():
        print("Error: Could not open webcam.")
        return

    cv2.namedWindow("1 - Live Colour")
    cv2.setMouseCallback("1 - Live Colour", mouse_cb)

    frame1 = None
    frame2 = None
    capture_count = 0
    circles = []
    chess_coords = []
    colors = [(0, 255, 80), (0, 120, 255)]

    print("Controls:")
    print("  P     - Define board (click 4 corners: top-left, top-right, bottom-right, bottom-left)")
    print("  SPACE - Capture frames for comparison (press twice)")
    print("  R     - Reset captures")
    print("  C     - Clear board corners")
    print("  Q     - Quit")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        display = frame.copy()
        board_ready = len(corner_pts) == 4

        # ── draw board overlay ──
        if board_ready:
            M, M_inv = get_matrices(corner_pts)
            draw_grid(display, M_inv, chess_coords, circles, colors)
        elif corner_pts:
            # Show corners placed so far
            for i, p in enumerate(corner_pts):
                cv2.circle(display, p, 7, (0, 255, 255), -1)
                cv2.putText(display, str(i+1), (p[0]+8, p[1]+5),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,255,255), 1)
            if len(corner_pts) > 1:
                for i in range(len(corner_pts)-1):
                    cv2.line(display, corner_pts[i], corner_pts[i+1], (0,255,255), 1)

        # ── draw detection circles on live feed ──
        for i, (cx, cy, r) in enumerate(circles):
            cv2.circle(display, (cx, cy), r, colors[i % 2], 2)
            cv2.circle(display, (cx, cy), 4, colors[i % 2], -1)

        # ── status label ──
        if selecting:
            label = f"Click corner {len(corner_pts)+1}/4  (TL > TR > BR > BL)"
        elif not board_ready:
            label = "Press P to define board corners"
        elif capture_count == 0:
            label = "SPACE: capture Frame 1"
        elif capture_count == 1:
            label = "SPACE: capture Frame 2  |  R: reset"
        else:
            if chess_coords:
                label = "  ".join([f"Region {i+1}: {c}" for i,c in enumerate(chess_coords) if c])
            else:
                label = "No changes detected  |  SPACE: recapture"

        cv2.putText(display, label, (10, 28),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.62, (0, 220, 255), 2, cv2.LINE_AA)
        cv2.imshow("1 - Live Colour", display)

        # ── diff window ──
        if capture_count == 2 and frame1 is not None and frame2 is not None:
            diff = cv2.absdiff(frame1, frame2)
            diff_amp = cv2.convertScaleAbs(diff, alpha=3.0, beta=0)

            if board_ready:
                mask = get_board_mask(diff_amp.shape, corner_pts)
                diff_amp = cv2.bitwise_and(diff_amp, cv2.merge([mask,mask,mask]))

            for i, (cx, cy, r) in enumerate(circles):
                cv2.circle(diff_amp, (cx, cy), r, colors[i % 2], 2)

            changed_px = int(np.sum(np.any(diff > 25, axis=2)))
            pct = changed_px / (diff.shape[0] * diff.shape[1]) * 100
            cv2.putText(diff_amp, f"Changed: {changed_px}px ({pct:.1f}%)",
                        (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,255,255), 2, cv2.LINE_AA)
            cv2.imshow("2 - Frame Difference", diff_amp)
        else:
            ph = np.zeros((frame.shape[0], frame.shape[1], 3), dtype=np.uint8)
            msg = "Waiting for Frame 2..." if capture_count == 1 else "Press SPACE to start"
            cv2.putText(ph, msg, (10, frame.shape[0]//2),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,200,255), 2)
            cv2.imshow("2 - Frame Difference", ph)

        key = cv2.waitKey(1) & 0xFF

        if key == ord('q'):
            break

        elif key == ord('p'):
            corner_pts = []
            selecting = True
            circles = []
            chess_coords = []
            print("Click 4 corners: top-left, top-right, bottom-right, bottom-left")

        elif key == ord('c'):
            corner_pts = []
            selecting = False
            circles = []
            chess_coords = []
            print("Board cleared.")

        elif key == ord('r'):
            frame1 = frame2 = None
            capture_count = 0
            circles = []
            chess_coords = []
            print("Reset.")

        elif key == ord(' '):
            if not board_ready:
                print("Define the board first (press P).")
                continue
            M, M_inv = get_matrices(corner_pts)
            mask = get_board_mask(frame.shape, corner_pts)

            if capture_count == 0:
                frame1 = frame.copy()
                capture_count = 1
                circles = []
                chess_coords = []
                print("Frame 1 captured.")
            elif capture_count == 1:
                frame2 = frame.copy()
                capture_count = 2
                diff = cv2.absdiff(frame1, frame2)
                circles = find_top2_circles(diff, mask=mask)
                chess_coords = [pixel_to_chess(cx, cy, M) for (cx, cy, r) in circles]
                print(f"Frame 2 captured. Changes: {chess_coords}")
            elif capture_count == 2:
                frame1 = frame.copy()
                frame2 = None
                capture_count = 1
                circles = []
                chess_coords = []
                print("Recaptured Frame 1.")

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
    