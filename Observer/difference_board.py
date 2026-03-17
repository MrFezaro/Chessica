import cv2
import numpy as np
import json
import os
from itertools import combinations

CORNERS_FILE = "./Observer/board_corners.json"

def save_corners(pts):
    with open(CORNERS_FILE, 'w') as f:
        json.dump(pts, f)
    print(f"Board corners saved to {CORNERS_FILE}")

def load_corners():
    if os.path.exists(CORNERS_FILE):
        with open(CORNERS_FILE, 'r') as f:
            pts = json.load(f)
        if len(pts) == 4:
            print(f"Loaded saved board corners from {CORNERS_FILE}")
            return [tuple(p) for p in pts]
    return []


COLS = 'abcdefgh'
ROWS = '87654321'
BOARD_SIZE = 800
CELL = BOARD_SIZE // 8
INNER = (7, 7)  # inner corners of a standard 8x8 chessboard

# ── perspective helpers ───────────────────────────────────────────────────────

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
    col = max(0, min(7, int(bx / CELL)))
    row = max(0, min(7, int(by / CELL)))
    return COLS[col] + ROWS[row]

def get_board_mask(shape, pts):
    mask = np.zeros(shape[:2], dtype=np.uint8)
    cv2.fillPoly(mask, [np.array(pts, dtype=np.int32)], 255)
    return mask

# ── auto corner detection ─────────────────────────────────────────────────────

def auto_detect_corners(frame):
    """
    Use cv2.findChessboardCornersSB to find the 7x7 inner corners,
    then extrapolate outward by one cell to get the 4 board boundary corners.
    Returns list of 4 (x,y) tuples [TL, TR, BR, BL] or None.
    """
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    flags = (cv2.CALIB_CB_EXHAUSTIVE | cv2.CALIB_CB_ACCURACY)
    ret, corners = cv2.findChessboardCornersSB(gray, INNER, flags)

    if not ret:
        # Fallback to classic detector with subpixel refinement
        ret, corners = cv2.findChessboardCorners(gray, INNER,
            cv2.CALIB_CB_ADAPTIVE_THRESH | cv2.CALIB_CB_NORMALIZE_IMAGE)
        if ret:
            criteria = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
            corners = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)

    if not ret or corners is None:
        return None, None

    corners = corners.reshape(INNER[1], INNER[0], 2)  # (7,7,2)

    # Vectors for one cell right and one cell down at each board corner
    # Using the two nearest inner corner neighbours to estimate cell size/direction
    v_right_top  = corners[0, 1] - corners[0, 0]       # top row: right step
    v_right_bot  = corners[6, 1] - corners[6, 0]
    v_down_left  = corners[1, 0] - corners[0, 0]       # left col: down step
    v_down_right = corners[1, 6] - corners[0, 6]

    tl = corners[0, 0] - v_right_top - v_down_left
    tr = corners[0, 6] + v_right_top - v_down_left   # mirror right step
    br = corners[6, 6] + v_right_bot + v_down_right
    bl = corners[6, 0] - v_right_bot + v_down_right  # mirror left step

    outer = [tuple(tl.astype(int)), tuple(tr.astype(int)),
             tuple(br.astype(int)), tuple(bl.astype(int))]
    return outer, corners

# ── grid drawing ──────────────────────────────────────────────────────────────

def draw_grid(frame, M_inv, chess_coords, circles, colors):
    overlay = frame.copy()
    for r in range(8):
        for c in range(8):
            poly = np.array([
                board_to_img(c*CELL,     r*CELL,     M_inv),
                board_to_img((c+1)*CELL, r*CELL,     M_inv),
                board_to_img((c+1)*CELL, (r+1)*CELL, M_inv),
                board_to_img(c*CELL,     (r+1)*CELL, M_inv),
            ], dtype=np.int32)
            shade = (65, 55, 45) if (r+c) % 2 == 0 else (30, 25, 20)
            cv2.fillPoly(overlay, [poly], shade)

    for i, coord in enumerate(chess_coords):
        if not coord:
            continue
        c, r = COLS.index(coord[0]), ROWS.index(coord[1])
        poly = np.array([
            board_to_img(c*CELL,     r*CELL,     M_inv),
            board_to_img((c+1)*CELL, r*CELL,     M_inv),
            board_to_img((c+1)*CELL, (r+1)*CELL, M_inv),
            board_to_img(c*CELL,     (r+1)*CELL, M_inv),
        ], dtype=np.int32)
        cv2.fillPoly(overlay, [poly], colors[i % len(colors)])

    cv2.addWeighted(overlay, 0.45, frame, 0.55, 0, frame)

    for i in range(9):
        cv2.line(frame, board_to_img(i*CELL, 0, M_inv),
                        board_to_img(i*CELL, BOARD_SIZE, M_inv), (180,180,180), 1)
        cv2.line(frame, board_to_img(0, i*CELL, M_inv),
                        board_to_img(BOARD_SIZE, i*CELL, M_inv), (180,180,180), 1)

    for c in range(8):
        pt = board_to_img(int((c+0.5)*CELL), BOARD_SIZE-18, M_inv)
        cv2.putText(frame, COLS[c], (pt[0]-6, pt[1]),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255,220,0), 1, cv2.LINE_AA)
    for r in range(8):
        pt = board_to_img(8, int((r+0.5)*CELL), M_inv)
        cv2.putText(frame, ROWS[r], (pt[0], pt[1]+5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255,220,0), 1, cv2.LINE_AA)

    for i, coord in enumerate(chess_coords):
        if not coord:
            continue
        c, r = COLS.index(coord[0]), ROWS.index(coord[1])
        centre = board_to_img(int((c+0.5)*CELL), int((r+0.5)*CELL), M_inv)
        cv2.putText(frame, coord, (centre[0]-14, centre[1]+6),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255,255,255), 2, cv2.LINE_AA)

# ── diff / cell detection ─────────────────────────────────────────────────────

def find_changed_cells(diff, M, M_inv, top_n=4):
    """
    Warp the diff image into flat board space and score each of the 64 cells
    by mean pixel change. Returns the top_n cells as image-space
    (cx, cy, radius) tuples, sorted by score descending.

    Because scoring happens per-cell in board space, adjacent squares can
    never merge — fixing the blob-merging problem of contour-based detection.
    """
    gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
    board_gray = cv2.warpPerspective(gray, M, (BOARD_SIZE, BOARD_SIZE))

    scores = []
    for row in range(8):
        for col in range(8):
            region = board_gray[row*CELL:(row+1)*CELL, col*CELL:(col+1)*CELL]
            score = float(np.mean(region))
            scores.append((score, row, col))

    scores.sort(reverse=True)

    circles = []
    for score, row, col in scores[:top_n]:
        if score < 8:          # ignore near-zero noise
            break
        # Centre of this cell in board space → back to image space
        bx = int((col + 0.5) * CELL)
        by = int((row + 0.5) * CELL)
        cx, cy = board_to_img(bx, by, M_inv)
        circles.append((cx, cy, CELL // 2))

    return circles

# ── special move detection ────────────────────────────────────────────────────

CASTLING_PATTERNS = {
    frozenset(['e1', 'g1', 'h1', 'f1']): "White Kingside Short Castle",
    frozenset(['e1', 'c1', 'a1', 'd1']): "White Queenside Long Castle",
    frozenset(['e8', 'g8', 'h8', 'f8']): "Black Kingside Short Castle",
    frozenset(['e8', 'c8', 'a8', 'd8']): "Black Queenside Long Castle",
}

def detect_castling(chess_coords):
    """Return castling label if the changed squares match a castling pattern."""
    return CASTLING_PATTERNS.get(frozenset(chess_coords), None)

def detect_en_passant(chess_coords):
    """
    En passant changes exactly 3 squares forming an L-shape:
      - Two squares share the same rank (moving pawn origin + captured pawn).
      - The third square (destination) shares a file with one of those two,
        one rank forward.
      - The two same-rank squares are on adjacent files.
    Returns a description string or None.
    """
    if len(chess_coords) != 3:
        return None

    parsed = []
    for sq in chess_coords:
        if len(sq) != 2 or sq[0] not in COLS or sq[1] not in ROWS:
            return None
        parsed.append((COLS.index(sq[0]), ROWS.index(sq[1])))

    # Find which two squares share the same rank
    same_rank_pair = None
    lone = None
    for i in range(3):
        others = [j for j in range(3) if j != i]
        if parsed[others[0]][1] == parsed[others[1]][1]:
            same_rank_pair = (others[0], others[1])
            lone = i
            break

    if same_rank_pair is None:
        return None

    a, b = parsed[same_rank_pair[0]], parsed[same_rank_pair[1]]
    dest = parsed[lone]

    # Same-rank squares must be adjacent files
    if abs(a[0] - b[0]) != 1:
        return None

    # Destination file must match one of the same-rank squares
    if dest[0] not in (a[0], b[0]):
        return None

    # Destination must be exactly one rank away
    shared_rank = a[1]
    if abs(dest[1] - shared_rank) != 1:
        return None

    # ROWS = '87654321': index 3 = rank '5' (white captures), index 4 = rank '4' (black captures)
    if shared_rank == 3:
        colour = "White"
    elif shared_rank == 4:
        colour = "Black"
    else:
        return None  # geometrically valid but not a legal en passant rank

    return f"{colour} En Passant  ({'  '.join(chess_coords)})"

def classify_move(chess_coords):
    # Filter obvious noise (very low score) but keep borderline squares
    coords = [c for c in chess_coords if c]

    # Try castling (needs 4 squares)
    if len(coords) >= 4:
        castle = detect_castling(coords[:4])
        if castle:
            return castle, coords[:4]

    # Try en passant against every combination of 3 from the top results
    for trio in combinations(coords[:4], 3):
        ep = detect_en_passant(list(trio))
        if ep:
            return ep, list(trio)

    # Plain move — top 2 only
    return "", coords[:2]

# ── mouse callback (manual fallback) ─────────────────────────────────────────

corner_pts  = []
selecting   = False

def mouse_cb(event, x, y, flags, param):
    global corner_pts, selecting
    if selecting and event == cv2.EVENT_LBUTTONDOWN and len(corner_pts) < 4:
        corner_pts.append((x, y))
        print(f"  Corner {len(corner_pts)} set: ({x},{y})")
        if len(corner_pts) == 4:
            selecting = False
            save_corners(corner_pts)
            print("Board defined manually.")

# ── main ──────────────────────────────────────────────────────────────────────

def main():
    global corner_pts, selecting

    cap = cv2.VideoCapture(2)
    if not cap.isOpened():
        print("Error: Could not open webcam.")
        return

    cv2.namedWindow("1 - Live Colour")
    cv2.setMouseCallback("1 - Live Colour", mouse_cb)

    frame1 = frame2 = None
    capture_count = 0
    circles = []
    chess_coords = []
    move_label = ""
    corner_pts = load_corners()
    colors = [(0, 255, 80), (0, 120, 255), (255, 80, 0), (255, 0, 180)]
    auto_status = ""  # feedback string for auto-detect

    print("Controls:")
    print("  A     - Auto-detect chessboard corners (OpenCV)")
    print("  P     - Manually click 4 corners (TL>TR>BR>BL)")
    print("  SPACE - Capture Frame 1 / Frame 2")
    print("  R     - Reset captures")
    print("  C     - Clear board")
    print("  Q     - Quit")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        display = frame.copy()
        board_ready = len(corner_pts) == 4

        # Draw board overlay
        if board_ready:
            M, M_inv = get_matrices(corner_pts)
            draw_grid(display, M_inv, chess_coords, circles, colors)
        elif corner_pts:
            for i, p in enumerate(corner_pts):
                cv2.circle(display, p, 7, (0,255,255), -1)
                cv2.putText(display, str(i+1), (p[0]+8, p[1]+5),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,255,255), 1)
            for i in range(len(corner_pts)-1):
                cv2.line(display, corner_pts[i], corner_pts[i+1], (0,255,255), 1)

        # Detection circles on live feed
        for i, (cx, cy, r) in enumerate(circles):
            cv2.circle(display, (cx, cy), r, colors[i % len(colors)], 2)
            cv2.circle(display, (cx, cy), 4, colors[i % len(colors)], -1)

        # Status label
        if selecting:
            label = f"Click corner {len(corner_pts)+1}/4  (TL > TR > BR > BL)"
        elif auto_status:
            label = auto_status
        elif not board_ready:
            label = "A: auto-detect board  |  P: manual corners"
        elif capture_count == 0:
            label = "SPACE: capture Frame 1"
        elif capture_count == 1:
            label = "SPACE: capture Frame 2  |  R: reset"
        else:
            if move_label:
                label = move_label
            elif chess_coords:
                label = "  ".join([f"Region {i+1}: {c}" for i,c in enumerate(chess_coords) if c])
            else:
                label = "No change detected  |  SPACE: recapture"

        cv2.putText(display, label, (10, 28),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.62, (0,220,255), 2, cv2.LINE_AA)
        cv2.imshow("1 - Live Colour", display)

        # Diff window
        if capture_count == 2 and frame1 is not None and frame2 is not None:
            diff = cv2.absdiff(frame1, frame2)
            diff_amp = cv2.convertScaleAbs(diff, alpha=3.0, beta=0)
            if board_ready:
                mask = get_board_mask(diff_amp.shape, corner_pts)
                diff_amp = cv2.bitwise_and(diff_amp, cv2.merge([mask,mask,mask]))
            for i, (cx, cy, r) in enumerate(circles):
                cv2.circle(diff_amp, (cx, cy), r, colors[i % len(colors)], 2)
            changed_px = int(np.sum(np.any(diff > 25, axis=2)))
            pct = changed_px / (diff.shape[0]*diff.shape[1]) * 100
            cv2.putText(diff_amp, f"Changed: {changed_px}px ({pct:.1f}%)",
                        (10,28), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,255,255), 2, cv2.LINE_AA)
            cv2.imshow("2 - Frame Difference", diff_amp)
        else:
            ph = np.zeros((frame.shape[0], frame.shape[1], 3), dtype=np.uint8)
            msg = "Waiting for Frame 2..." if capture_count == 1 else "Press A to detect board, then SPACE"
            cv2.putText(ph, msg, (10, frame.shape[0]//2),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0,200,255), 2)
            cv2.imshow("2 - Frame Difference", ph)

        key = cv2.waitKey(1) & 0xFF

        if key == ord('q'):
            break

        elif key == ord('a'):
            print("Auto-detecting chessboard corners...")
            auto_status = "Detecting..."
            detected, raw_corners = auto_detect_corners(frame)
            if detected:
                corner_pts = detected
                circles = []
                chess_coords = []
                move_label = ""
                selecting = False
                auto_status = "Board auto-detected!  Press SPACE to capture."
                print(f"Board detected. Outer corners: {corner_pts}")
                # Draw found corners briefly on the frame for feedback
                fb = frame.copy()
                cv2.drawChessboardCorners(fb, INNER, raw_corners.reshape(-1,1,2), True)
                for p in corner_pts:
                    cv2.circle(fb, p, 8, (0,255,0), -1)
                cv2.imshow("1 - Live Colour", fb)
                cv2.waitKey(800)
            else:
                auto_status = "Detection failed - ensure board is fully visible"
                print("Could not detect chessboard. Make sure the full board is visible.")

        elif key == ord('p'):
            corner_pts = []
            selecting = True
            circles = []
            chess_coords = []
            move_label = ""
            auto_status = ""
            print("Manual mode: click TL, TR, BR, BL corners.")

        elif key == ord('c'):
            corner_pts = []
            selecting = False
            circles = []
            chess_coords = []
            move_label = ""
            auto_status = ""
            print("Board cleared.")

        elif key == ord('r'):
            frame1 = frame2 = None
            capture_count = 0
            circles = []
            chess_coords = []
            move_label = ""
            auto_status = ""
            print("Reset.")

        elif key == ord(' '):
            if not board_ready:
                print("Define board first (A to auto-detect, P for manual).")
                continue
            auto_status = ""
            move_label = ""
            M, M_inv = get_matrices(corner_pts)

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

                # Score every cell — fetch top 4 to cover castling (4 sq) and en passant (3 sq)
                all_circles = find_changed_cells(diff, M, M_inv, top_n=4)
                all_coords = list(dict.fromkeys(
                    [pixel_to_chess(cx, cy, M) for (cx, cy, r) in all_circles]
                ))

                move_label, all_coords = classify_move(all_coords)
                # Keep only the circles that correspond to the kept coords
                circles = all_circles[:len(all_coords)]
                chess_coords = all_coords

                if move_label:
                    print(f"Special move: {move_label}  |  Squares: {chess_coords}")
                else:
                    print(f"Frame 2 captured. Changes at: {chess_coords}")

            elif capture_count == 2:
                frame1 = frame.copy()
                frame2 = None
                capture_count = 1
                circles = []
                chess_coords = []
                move_label = ""
                print("Recaptured Frame 1.")

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()