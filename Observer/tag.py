import cv2
import numpy as np
from pupil_apriltags import Detector

# ── Constants ──────────────────────────────────────────────────────────────
DECISION_MARGIN = 30
BOARD_COLS      = 8
BOARD_ROWS      = 8

# ── Piece / colour lookup ───────────────────────────────────────────────────
_WHITE_PIECES = {0: 'pawn', 1: 'rook', 2: 'horse',
                 11: 'bishop', 4: 'queen',  3: 'king'}
_BLACK_PIECES = {5: 'pawn', 6: 'rook', 10: 'horse',
                 7: 'bishop', 9: 'queen',  8: 'king'}
PIECE_MAP = {**_WHITE_PIECES, **_BLACK_PIECES}
COLOR_MAP = {**{k: 'white' for k in _WHITE_PIECES},
             **{k: 'black' for k in _BLACK_PIECES}}

# ── Public game state ──────────────────────────────────────────────────────
game_state: dict = {}
# { "e4": {"piece": "farmer", "color": "white", "tag_id": 0}, … }

# ── Shared camera / detector (lazy init) ───────────────────────────────────
_cap      = None
_detector = None

# ── Calibration state ──────────────────────────────────────────────────────
_undistort_map1 = None   # precomputed remap tables (fast per-frame undistort)
_undistort_map2 = None

# ── Board definition state ─────────────────────────────────────────────────
_board_corners: list = []
_defining_board: bool = False
_perspective_M        = None


# ══════════════════════════════════════════════════════════════════════════
#  Public API
# ══════════════════════════════════════════════════════════════════════════

def init() -> None:
    """Warm up the camera and detector without capturing. Call once on startup."""
    _ensure_init()


def load_calibration(path: str = "camera_calibration.npz") -> None:
    """
    Load camera calibration produced by calibrate.py and precompute
    undistortion maps. Call once before update_game_state().

    Example:
        tag.load_calibration()                        # default filename
        tag.load_calibration("my_calibration.npz")   # custom path
    """
    global _undistort_map1, _undistort_map2
    data = np.load(path)
    camera_matrix = data["camera_matrix"]
    dist_coeffs   = data["dist_coeffs"]
    w, h          = data["image_size"]

    # alpha=0: crop black borders away after undistortion
    new_matrix, _ = cv2.getOptimalNewCameraMatrix(
        camera_matrix, dist_coeffs, (w, h), alpha=0, newImgSize=(w, h)
    )
    _undistort_map1, _undistort_map2 = cv2.initUndistortRectifyMap(
        camera_matrix, dist_coeffs, None, new_matrix, (w, h), cv2.CV_16SC2
    )
    print(f"Calibration loaded from '{path}'  ({int(w)}x{int(h)})")


def update_game_state(show: bool = False) -> dict:
    """
    Grab one frame from the camera, detect AprilTags, and update game_state.
    Returns the updated game_state dict.

    show=True  — opens/refreshes an annotated window showing detected tags.
    """
    global game_state
    _ensure_init()

    _cap.read()  # flush stale buffered frame
    ret, frame = _cap.read()
    if not ret:
        print("tag: frame grab failed.")
        return game_state

    frame = _undistort(frame)

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    tags = _detector.detect(gray)
    tags = [t for t in tags if t.decision_margin >= DECISION_MARGIN]

    new_state: dict = {}
    for tag in tags:
        cx, cy  = int(tag.center[0]), int(tag.center[1])
        tid     = tag.tag_id
        piece   = PIECE_MAP.get(tid, f'unknown({tid})')
        color   = COLOR_MAP.get(tid, 'unknown')
        square  = _image_to_square((cx, cy))

        print(f"  Tag {tid:2d}  {color:5s} {piece:7s}  "
              f"({cx:4d},{cy:4d})  margin={tag.decision_margin:.1f}  "
              f"square={square or 'off-board'}")

        new_state[square or f"tag_{tid}"] = {
            "piece":  piece,
            "color":  color,
            "tag_id": tid,
            "square": square,
        }

    game_state = new_state

    if show:
        snap = frame.copy()
        n = _annotate_snap(snap)
        _draw_board_outline(snap)
        _draw_overlay(snap, num_tags=n)
        cv2.namedWindow("AprilTag - Captured", cv2.WINDOW_NORMAL)
        cv2.imshow("AprilTag - Captured", snap)
        cv2.waitKey(1)

    return game_state


def set_board_corners(tl, tr, br, bl) -> None:
    """
    Set board corners programmatically instead of clicking them in the GUI.
    Each argument is an (x, y) pixel tuple.

    Example:
        tag.set_board_corners((100, 80), (900, 80), (900, 700), (100, 700))
    """
    global _board_corners
    _board_corners = [tuple(tl), tuple(tr), tuple(br), tuple(bl)]
    _recompute_perspective()
    print(f"Board corners set: TL={tl}  TR={tr}  BR={br}  BL={bl}")


# ══════════════════════════════════════════════════════════════════════════
#  Internal helpers
# ══════════════════════════════════════════════════════════════════════════

def _undistort(frame):
    """Apply calibration remap if loaded, otherwise pass frame through."""
    if _undistort_map1 is None:
        return frame
    return cv2.remap(frame, _undistort_map1, _undistort_map2, cv2.INTER_LINEAR)


def _ensure_init() -> None:
    global _cap, _detector
    if _cap is None:
        import platform
        backend = cv2.CAP_DSHOW if platform.system() == "Windows" else cv2.CAP_V4L2
        _cap = cv2.VideoCapture(0, backend)  # Change camera index if you have multiple webcams
        if not _cap.isOpened():
            raise RuntimeError("tag: cannot open USB webcam.")
        _cap.set(cv2.CAP_PROP_FRAME_WIDTH,  1920)
        _cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
        _cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        # Auto-load calibration from the same directory as this file
        import os
        cal_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "camera_calibration.npz")
        if os.path.exists(cal_path):
            load_calibration(cal_path)
        _load_board_corners()
        # Flush stale/black frames that DirectShow serves on startup
        for _ in range(10):
            _cap.read()
    if _detector is None:
        _detector = Detector(
            families="tag16h5",
            nthreads=4,
            quad_decimate=1.0,
            quad_sigma=0.0,
            refine_edges=1,
            decode_sharpening=0.25,
        )


def _recompute_perspective() -> None:
    global _perspective_M
    if len(_board_corners) < 4:
        _perspective_M = None
        return
    s = np.array(_board_corners[:4], dtype=np.float32)
    dst = np.array([[0, 0], [BOARD_COLS, 0],
                    [BOARD_COLS, BOARD_ROWS], [0, BOARD_ROWS]],
                   dtype=np.float32)
    _perspective_M = cv2.getPerspectiveTransform(s, dst)
    _save_board_corners()


def _corners_path() -> str:
    import os
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "board_corners.npz")


def _save_board_corners() -> None:
    if len(_board_corners) < 4:
        return
    p = _corners_path()
    np.savez(p, corners=np.array(_board_corners[:4]))
    print(f"Board corners saved to '{p}'")


def _load_board_corners() -> None:
    global _board_corners
    import os
    p = _corners_path()
    if not os.path.exists(p):
        return
    data = np.load(p)
    _board_corners = [tuple(int(v) for v in pt) for pt in data["corners"]]
    # Recompute without re-saving
    global _perspective_M
    s = np.array(_board_corners[:4], dtype=np.float32)
    dst = np.array([[0, 0], [BOARD_COLS, 0],
                    [BOARD_COLS, BOARD_ROWS], [0, BOARD_ROWS]],
                   dtype=np.float32)
    _perspective_M = cv2.getPerspectiveTransform(s, dst)
    print(f"Board corners loaded from '{p}': {_board_corners}")


def _image_to_square(pt_xy) -> str | None:
    if _perspective_M is None:
        return None
    pt = np.array([[[float(pt_xy[0]), float(pt_xy[1])]]], dtype=np.float32)
    bx, by = cv2.perspectiveTransform(pt, _perspective_M)[0][0]
    col, row = int(bx), int(by)
    if 0 <= col < BOARD_COLS and 0 <= row < BOARD_ROWS:
        return f"{'abcdefgh'[col]}{8 - row}"
    return None


def _board_to_image_pt(bx: float, by: float) -> tuple[int, int]:
    src = np.array(_board_corners[:4], dtype=np.float32)
    dst = np.array([[0, 0], [BOARD_COLS, 0],
                    [BOARD_COLS, BOARD_ROWS], [0, BOARD_ROWS]],
                   dtype=np.float32)
    M_inv = cv2.getPerspectiveTransform(dst, src)
    pt    = np.array([[[bx, by]]], dtype=np.float32)
    px, py = cv2.perspectiveTransform(pt, M_inv)[0][0]
    return int(px), int(py)


# ── Mouse callback ─────────────────────────────────────────────────────────
def _mouse_cb(event, x, y, flags, param) -> None:
    global _board_corners, _defining_board
    if not _defining_board:
        return
    if event == cv2.EVENT_LBUTTONDOWN:
        _board_corners.append((x, y))
        labels = ['TL', 'TR', 'BR', 'BL']
        print(f"  Corner {len(_board_corners)}/4 ({labels[len(_board_corners)-1]}): ({x}, {y})")
        if len(_board_corners) == 4:
            _defining_board = False
            _recompute_perspective()
            print("Board defined — perspective transform ready.\n")


# ── HUD overlay ────────────────────────────────────────────────────────────
def _draw_overlay(frame, num_tags: int) -> None:
    overlay = frame.copy()
    w = frame.shape[1]
    cv2.rectangle(overlay, (0, 0), (w, 42), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.5, frame, 0.5, 0, frame)
    board_str = "Board:SET" if _perspective_M is not None else "Board:--"
    cal_str   = "Cal:ON" if _undistort_map1 is not None else "Cal:--"
    mode_str  = "  <- click TL TR BR BL" if _defining_board else ""
    cv2.putText(
        frame,
        f"B=board{mode_str}  SPACE=capture  Q=quit"
        f"  |  Tags:{num_tags}  {board_str}  {cal_str}",
        (10, 29), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2,
    )


def _draw_board_outline(frame) -> None:
    labels = ['TL', 'TR', 'BR', 'BL']
    for i, pt in enumerate(_board_corners):
        cv2.circle(frame, pt, 7, (0, 140, 255), -1)
        cv2.putText(frame, labels[i], (pt[0] + 8, pt[1] - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 140, 255), 2)
        if i > 0:
            cv2.line(frame, _board_corners[i - 1], pt, (0, 140, 255), 2)
    if len(_board_corners) == 4:
        cv2.line(frame, _board_corners[3], _board_corners[0], (0, 140, 255), 2)
        for col in range(1, BOARD_COLS):
            cv2.line(frame, _board_to_image_pt(float(col), 0.0),
                     _board_to_image_pt(float(col), float(BOARD_ROWS)),
                     (0, 100, 200), 1)
        for row in range(1, BOARD_ROWS):
            cv2.line(frame, _board_to_image_pt(0.0, float(row)),
                     _board_to_image_pt(float(BOARD_COLS), float(row)),
                     (0, 100, 200), 1)
        for col in range(BOARD_COLS):
            px, py = _board_to_image_pt(col + 0.5, BOARD_ROWS + 0.15)
            cv2.putText(frame, 'abcdefgh'[col], (px - 5, py),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 200, 255), 1)
        for row in range(BOARD_ROWS):
            px, py = _board_to_image_pt(-0.35, row + 0.6)
            cv2.putText(frame, str(8 - row), (px, py),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 200, 255), 1)


def _annotate_snap(frame) -> int:
    """Draw tag overlays on a snap frame for the GUI window. Returns tag count."""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    tags = _detector.detect(gray)
    tags = [t for t in tags if t.decision_margin >= DECISION_MARGIN]
    for tag in tags:
        corners = tag.corners.astype(int)
        for j in range(4):
            cv2.line(frame, tuple(corners[j]), tuple(corners[(j + 1) % 4]),
                     (0, 255, 0), 2)
        cx, cy  = int(tag.center[0]), int(tag.center[1])
        tid     = tag.tag_id
        piece   = PIECE_MAP.get(tid, f'unknown({tid})')
        color   = COLOR_MAP.get(tid, 'unknown')
        square  = _image_to_square((cx, cy))
        dot_col = (255, 255, 0) if color == 'white' else (180, 80, 255)
        cv2.circle(frame, (cx, cy), 5, dot_col, -1)
        label = f"{'W' if color=='white' else 'B'}-{piece}"
        if square:
            label += f" [{square}]"
        cv2.putText(frame, label, (cx - 40, cy - 14),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.65, dot_col, 2)
    return len(tags)


# ══════════════════════════════════════════════════════════════════════════
#  Standalone live preview
# ══════════════════════════════════════════════════════════════════════════

def main() -> None:
    global _board_corners, _defining_board, _perspective_M

    _ensure_init()

    win_name  = "AprilTag - Live Preview"
    snap_name = "AprilTag - Captured"
    cv2.namedWindow(win_name,  cv2.WINDOW_NORMAL)
    cv2.namedWindow(snap_name, cv2.WINDOW_NORMAL)
    cv2.setMouseCallback(win_name, _mouse_cb)

    print(__doc__)

    while True:
        ret, frame = _cap.read()
        if not ret:
            print("Frame grab failed.")
            break

        frame = _undistort(frame)

        preview = frame.copy()
        _draw_board_outline(preview)
        _draw_overlay(preview, num_tags=0)
        cv2.imshow(win_name, preview)

        key = cv2.waitKey(1) & 0xFF

        if key == ord('q'):
            break

        elif key == ord('b'):
            _board_corners  = []
            _defining_board = True
            _perspective_M  = None
            print("Board definition mode — click: TL -> TR -> BR -> BL")

        elif key == ord(' '):
            print(f"\nCapturing... (margin threshold: {DECISION_MARGIN})")
            update_game_state()
            snap = frame.copy()
            n = _annotate_snap(snap)
            _draw_overlay(snap, num_tags=n)
            cv2.imshow(snap_name, snap)
            print(f"Done — {n} tag(s).  game_state = {game_state}\n")

    _cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()