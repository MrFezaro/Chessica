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


# ── camera calibration ────────────────────────────────────────────────────────

CAMERA_MATRIX_FILE = "./Observer/camera_matrix.npy"
DIST_COEFFS_FILE   = "./Observer/dist_coeffs.npy"

def load_calibration(frame_shape):
    """
    Load camera matrix + distortion coefficients if available.
    Returns (K, dist, new_K) or (None, None, None) if not found.
    """
    if not (os.path.exists(CAMERA_MATRIX_FILE) and os.path.exists(DIST_COEFFS_FILE)):
        return None, None, None
    K    = np.load(CAMERA_MATRIX_FILE)
    dist = np.load(DIST_COEFFS_FILE)
    h, w = frame_shape[:2]
    new_K, _ = cv2.getOptimalNewCameraMatrix(K, dist, (w, h), alpha=0)
    print("Camera calibration loaded — lens undistortion active.")
    return K, dist, new_K

def undistort(frame, K, dist, new_K):
    if K is None:
        return frame
    return cv2.undistort(frame, K, dist, None, new_K)


COLS = 'abcdefgh'
ROWS = '87654321'
BOARD_SIZE = 800
CELL = BOARD_SIZE // 8
INNER = (7, 7)

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
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    flags = (cv2.CALIB_CB_EXHAUSTIVE | cv2.CALIB_CB_ACCURACY)
    ret, corners = cv2.findChessboardCornersSB(gray, INNER, flags)
    if not ret:
        ret, corners = cv2.findChessboardCorners(gray, INNER,
            cv2.CALIB_CB_ADAPTIVE_THRESH | cv2.CALIB_CB_NORMALIZE_IMAGE)
        if ret:
            criteria = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
            corners = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)
    if not ret or corners is None:
        return None, None
    corners = corners.reshape(INNER[1], INNER[0], 2)
    v_right_top  = corners[0, 1] - corners[0, 0]
    v_right_bot  = corners[6, 1] - corners[6, 0]
    v_down_left  = corners[1, 0] - corners[0, 0]
    v_down_right = corners[1, 6] - corners[0, 6]
    tl = corners[0, 0] - v_right_top - v_down_left
    tr = corners[0, 6] + v_right_top - v_down_left
    br = corners[6, 6] + v_right_bot + v_down_right
    bl = corners[6, 0] - v_right_bot + v_down_right
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
    return CASTLING_PATTERNS.get(frozenset(chess_coords), None)

def detect_en_passant(chess_coords):
    if len(chess_coords) != 3:
        return None
    parsed = []
    for sq in chess_coords:
        if len(sq) != 2 or sq[0] not in COLS or sq[1] not in ROWS:
            return None
        parsed.append((COLS.index(sq[0]), ROWS.index(sq[1])))
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
    if abs(a[0] - b[0]) != 1:
        return None
    if dest[0] not in (a[0], b[0]):
        return None
    shared_rank = a[1]
    if abs(dest[1] - shared_rank) != 1:
        return None
    if shared_rank == 3:
        colour = "White"
    elif shared_rank == 4:
        colour = "Black"
    else:
        return None
    return f"{colour} En Passant  ({'  '.join(chess_coords)})"

def classify_move(chess_coords):
    coords = [c for c in chess_coords if c]
    # Castling — needs 4 squares
    if len(coords) >= 4:
        castle = detect_castling(coords[:4])
        if castle:
            return castle, coords[:4]
    # En passant — try every combination of 3 from top results (fixes missed-square bug)
    for trio in combinations(coords[:4], 3):
        ep = detect_en_passant(list(trio))
        if ep:
            return ep, list(trio)
    # Plain move — top 2 only
    return "", coords[:2]

# ── mouse callback ────────────────────────────────────────────────────────────

corner_pts = []
selecting  = False

def mouse_cb(event, x, y, flags, param):
    global corner_pts, selecting
    if selecting and event == cv2.EVENT_LBUTTONDOWN and len(corner_pts) < 4:
        corner_pts.append((x, y))
        print(f"  Corner {len(corner_pts)} set: ({x},{y})")
        if len(corner_pts) == 4:
            selecting = False
            save_corners(corner_pts)
            print("Board defined manually.")

# ══════════════════════════════════════════════════════════════════════════════
# GAME STATE
# ══════════════════════════════════════════════════════════════════════════════

INITIAL_BOARD = {
    'a8':'r','b8':'n','c8':'b','d8':'q','e8':'k','f8':'b','g8':'n','h8':'r',
    'a7':'p','b7':'p','c7':'p','d7':'p','e7':'p','f7':'p','g7':'p','h7':'p',
    'a2':'P','b2':'P','c2':'P','d2':'P','e2':'P','f2':'P','g2':'P','h2':'P',
    'a1':'R','b1':'N','c1':'B','d1':'Q','e1':'K','f1':'B','g1':'N','h1':'R',
}

UNICODE_PIECES = {
    'K': '♔', 'Q': '♕', 'R': '♖', 'B': '♗', 'N': '♘', 'P': '♙',
    'k': '♚', 'q': '♛', 'r': '♜', 'b': '♝', 'n': '♞', 'p': '♟',
}

class GameState:
    def __init__(self):
        self.board       = dict(INITIAL_BOARD)
        self.turn        = 'w'          # 'w' or 'b'
        self.history     = []           # list of move strings
        self.move_number = 1

    def reset(self):
        self.board       = dict(INITIAL_BOARD)
        self.turn        = 'w'
        self.history     = []
        self.move_number = 1
        print("Game reset to starting position.")
        self.print_board()

    # ── helpers ───────────────────────────────────────────────────────────────

    def color_of(self, piece):
        """Return 'w', 'b', or None."""
        if not piece:
            return None
        return 'w' if piece.isupper() else 'b'

    def _advance_turn(self):
        if self.turn == 'w':
            self.turn = 'b'
        else:
            self.turn = 'w'
            self.move_number += 1

    def _record(self, move_str):
        dot = '.' if self.turn == 'w' else '...'
        self.history.append(f"{self.move_number}{dot} {move_str}")

    # ── move application ──────────────────────────────────────────────────────

    def infer_and_apply(self, changed_coords, move_label):
        """
        Determine what happened from the changed squares + move_label,
        update board state, and return a human-readable description.
        """
        coords = [c for c in changed_coords if c]

        if move_label and 'Castle' in move_label:
            return self._apply_castling(move_label)

        if move_label and 'En Passant' in move_label:
            return self._apply_en_passant(coords)

        if len(coords) >= 2:
            return self._apply_normal(coords[:2])

        return "Could not determine move (not enough changed squares)"

    def _apply_normal(self, coords):
        sq1, sq2 = coords[0], coords[1]
        p1, p2   = self.board.get(sq1), self.board.get(sq2)
        c1, c2   = self.color_of(p1),  self.color_of(p2)

        # Identify source (current player's piece) and destination
        if c1 == self.turn:
            src, dst, captured = sq1, sq2, p2
        elif c2 == self.turn:
            src, dst, captured = sq2, sq1, p1
        else:
            # Neither square has the expected colour — out-of-sync, best guess
            src, dst, captured = sq1, sq2, p2
            print(f"  [warn] Expected {self.turn} piece on {sq1} or {sq2}; "
                  f"board may be out of sync.")

        piece = self.board.get(src)
        if not piece:
            desc = f"No piece at {src} — board may be out of sync"
            print(f"  [warn] {desc}")
            return desc

        # Execute move
        self.board.pop(src, None)
        self.board[dst] = piece

        # Pawn promotion → auto-promote to queen
        promotion = ""
        if piece == 'P' and dst[1] == '8':
            self.board[dst] = 'Q'
            promotion = " (promoted to ♕)"
        elif piece == 'p' and dst[1] == '1':
            self.board[dst] = 'q'
            promotion = " (promoted to ♛)"

        cap_str  = f" ×{captured}" if captured else ""
        move_str = f"{UNICODE_PIECES.get(piece,'?')} {src}→{dst}{cap_str}{promotion}"
        self._record(move_str)
        self._advance_turn()
        return move_str

    def _apply_castling(self, label):
        patterns = {
            "White Kingside Short Castle":  [('e1','g1'), ('h1','f1')],
            "White Queenside Long Castle":  [('e1','c1'), ('a1','d1')],
            "Black Kingside Short Castle":  [('e8','g8'), ('h8','f8')],
            "Black Queenside Long Castle":  [('e8','c8'), ('a8','d8')],
        }
        for key, moves in patterns.items():
            if key in label:
                for src, dst in moves:
                    if src in self.board:
                        self.board[dst] = self.board.pop(src)
                self._record(label)
                self._advance_turn()
                return label
        return f"Unknown castling: {label}"

    def _apply_en_passant(self, coords):
        """
        En passant: 3 squares change.
          - source      = current player's pawn (has piece in board)
          - destination = empty square (diagonal forward)
          - captured    = enemy pawn on same file as destination, same rank as source
        """
        my_sq  = [sq for sq in coords if self.color_of(self.board.get(sq)) == self.turn]
        opp_sq = [sq for sq in coords if self.color_of(self.board.get(sq)) != self.turn
                  and self.board.get(sq) is not None]
        emp_sq = [sq for sq in coords if sq not in self.board]

        if not my_sq or not opp_sq or not emp_sq:
            # fallback
            move_str = f"En passant: {coords} (board unchanged — could not parse)"
            print(f"  [warn] {move_str}")
            return move_str

        src    = my_sq[0]
        dst    = emp_sq[0]
        cap_sq = opp_sq[0]

        piece    = self.board.pop(src)
        captured = self.board.pop(cap_sq, '?')
        self.board[dst] = piece

        move_str = (f"En passant: {UNICODE_PIECES.get(piece,'?')} "
                    f"{src}→{dst} (×{UNICODE_PIECES.get(captured,'?')} on {cap_sq})")
        self._record(move_str)
        self._advance_turn()
        return move_str

    # ── board printing ────────────────────────────────────────────────────────

    def print_board(self):
        for rank in '87654321':
            print(''.join(self.board.get(f + rank, '.') for f in 'abcdefgh'))


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
    auto_status = ""
    last_diff_display = None   # persists the diff image between moves

    # ── lens undistortion ─────────────────────────────────────────────────────
    ret0, probe = cap.read()
    K, dist, new_K = load_calibration(probe.shape) if ret0 else (None, None, None)

    # ── game state ────────────────────────────────────────────────────────────
    game = GameState()
    print("Starting fresh game.")
    game.print_board()

    print("Controls:")
    print("  A     - Auto-detect chessboard corners (OpenCV)")
    print("  P     - Manually click 4 corners (TL>TR>BR>BL)")
    print("  SPACE - Capture Frame 1 / Frame 2")
    print("  R     - Reset captures")
    print("  G     - Reset game to starting position")
    print("  C     - Clear board overlay")
    print("  Q     - Quit")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame   = undistort(frame, K, dist, new_K)
        display = frame.copy()
        board_ready = len(corner_pts) == 4

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

        for i, (cx, cy, r) in enumerate(circles):
            cv2.circle(display, (cx, cy), r, colors[i % len(colors)], 2)
            cv2.circle(display, (cx, cy), 4, colors[i % len(colors)], -1)

        # status label
        turn_label = f"{'White' if game.turn=='w' else 'Black'} move {game.move_number}"
        if selecting:
            label = f"Click corner {len(corner_pts)+1}/4  (TL > TR > BR > BL)"
        elif auto_status:
            label = auto_status
        elif not board_ready:
            label = "A: auto-detect  |  P: manual corners"
        elif capture_count == 0:
            label = f"SPACE: capture Frame 1  [{turn_label}]"
        else:
            if move_label:
                label = move_label
            elif chess_coords:
                label = "  ".join([f"Region {i+1}: {c}" for i,c in enumerate(chess_coords) if c])
            else:
                label = f"SPACE: capture next frame  [{turn_label}]"

        cv2.putText(display, label, (10, 28),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.62, (0,220,255), 2, cv2.LINE_AA)
        cv2.imshow("1 - Live Colour", display)

        # ── diff window — always visible ──────────────────────────────────────
        if last_diff_display is not None:
            cv2.imshow("2 - Frame Difference", last_diff_display)
        else:
            ph = np.zeros((frame.shape[0], frame.shape[1], 3), dtype=np.uint8)
            msg = ("Waiting for Frame 2..." if capture_count == 1
                   else "Press A to detect board, then SPACE")
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
                fb = frame.copy()
                cv2.drawChessboardCorners(fb, INNER, raw_corners.reshape(-1,1,2), True)
                for p in corner_pts:
                    cv2.circle(fb, p, 8, (0,255,0), -1)
                cv2.imshow("1 - Live Colour", fb)
                cv2.waitKey(800)
            else:
                auto_status = "Detection failed - ensure board is fully visible"
                print("Could not detect chessboard.")

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

        elif key == ord('g'):
            game.reset()

        elif key == ord('r'):
            frame1 = frame2 = None
            capture_count = 0
            circles = []
            chess_coords = []
            move_label = ""
            auto_status = ""
            last_diff_display = None
            print("Captures reset.")

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
                diff = cv2.absdiff(frame1, frame2)

                all_circles = find_changed_cells(diff, M, M_inv, top_n=4)
                all_coords  = list(dict.fromkeys(
                    [pixel_to_chess(cx, cy, M) for (cx, cy, r) in all_circles]
                ))

                move_label, all_coords = classify_move(all_coords)
                circles      = all_circles[:len(all_coords)]
                chess_coords = all_coords

                # ── update game state ─────────────────────────────────────────
                move_desc = game.infer_and_apply(chess_coords, move_label)
                print(" ")
                game.print_board()
                # ─────────────────────────────────────────────────────────────

                if move_label:
                    move_label = f"{move_label}  |  {move_desc}"
                else:
                    move_label = move_desc

                # ── build diff display image ──────────────────────────────────
                diff_amp = cv2.convertScaleAbs(diff, alpha=3.0, beta=0)
                if board_ready:
                    mask = get_board_mask(diff_amp.shape, corner_pts)
                    diff_amp = cv2.bitwise_and(diff_amp, cv2.merge([mask, mask, mask]))
                for i, (cx, cy, r) in enumerate(circles):
                    cv2.circle(diff_amp, (cx, cy), r, colors[i % len(colors)], 2)
                    cv2.circle(diff_amp, (cx, cy), 4,  colors[i % len(colors)], -1)
                changed_px = int(np.sum(np.any(diff > 25, axis=2)))
                pct = changed_px / (diff.shape[0] * diff.shape[1]) * 100
                cv2.putText(diff_amp, f"Changed: {changed_px}px ({pct:.1f}%)",
                            (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,255,255), 2, cv2.LINE_AA)
                cv2.putText(diff_amp, move_desc,
                            (10, 58), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0,220,255), 2, cv2.LINE_AA)
                last_diff_display = diff_amp
                # ─────────────────────────────────────────────────────────────

                # Roll frame2 → frame1 so next SPACE immediately diffs
                frame1 = frame2
                frame2 = None
                capture_count = 1

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()