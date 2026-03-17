import cv2
import numpy as np
import json
import os

CORNERS_FILE = "./Observer/board_corners.json"

def save_corners(pts):
    with open(CORNERS_FILE, 'w') as f:
        json.dump(pts, f)
    print(f"Saved to {CORNERS_FILE}")

def load_corners():
    if os.path.exists(CORNERS_FILE):
        with open(CORNERS_FILE, 'r') as f:
            pts = json.load(f)
        if len(pts) == 4:
            print(f"Loaded corners from {CORNERS_FILE}")
            return [tuple(p) for p in pts]
    return []

COLS = 'abcdefgh'
ROWS = '87654321'
BOARD_SIZE = 800
CELL = BOARD_SIZE // 8
INNER = (7, 7)

# ── perspective ───────────────────────────────────────────────────────────────

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

# ── auto detect ───────────────────────────────────────────────────────────────

def auto_detect_corners(frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    ret, corners = cv2.findChessboardCornersSB(gray, INNER,
        cv2.CALIB_CB_EXHAUSTIVE | cv2.CALIB_CB_ACCURACY)
    if not ret:
        ret, corners = cv2.findChessboardCorners(gray, INNER,
            cv2.CALIB_CB_ADAPTIVE_THRESH | cv2.CALIB_CB_NORMALIZE_IMAGE)
        if ret:
            corners = cv2.cornerSubPix(gray, corners, (11,11), (-1,-1),
                (cv2.TERM_CRITERIA_EPS|cv2.TERM_CRITERIA_COUNT, 30, 0.001))
    if not ret or corners is None:
        return None, None
    corners = corners.reshape(INNER[1], INNER[0], 2)
    v_rt=corners[0,1]-corners[0,0]; v_rb=corners[6,1]-corners[6,0]
    v_dl=corners[1,0]-corners[0,0]; v_dr=corners[1,6]-corners[0,6]
    outer = [tuple((corners[0,0]-v_rt-v_dl).astype(int)),
             tuple((corners[0,6]+v_rt-v_dl).astype(int)),
             tuple((corners[6,6]+v_rb+v_dr).astype(int)),
             tuple((corners[6,0]-v_rb+v_dr).astype(int))]
    return outer, corners

# ── from-square detection via frame diff ──────────────────────────────────────

def diff_top_square(ref_frame, cur_frame, board_mask, M, exclude=None):
    """
    Compare ref_frame (before move) vs cur_frame (after move).
    The square with the biggest brightness drop = piece left = from-square.
    """
    ref_gray = cv2.cvtColor(ref_frame, cv2.COLOR_BGR2GRAY).astype(np.float32)
    cur_gray = cv2.cvtColor(cur_frame, cv2.COLOR_BGR2GRAY).astype(np.float32)
    # Signed diff: positive where it got darker (piece removed)
    signed = ref_gray - cur_gray
    signed = np.clip(signed, 0, 255)   # only care about darkening
    if board_mask is not None:
        signed *= (board_mask / 255.0)

    best_sq = None
    best_score = -1
    h, w = signed.shape

    for r in range(8):
        for c in range(8):
            coord = COLS[c] + ROWS[r]
            if coord == exclude:
                continue
            sq_mask = np.zeros((h, w), dtype=np.uint8)
            poly = np.array([
                board_to_img(c*CELL,     r*CELL,     None),   # placeholder
            ], dtype=np.int32)
            # Build proper polygon via M_inv from the caller — we pass M_inv separately
            # Here we use a simpler approach: warp the square corners
            sq_mask2 = np.zeros((h, w), dtype=np.uint8)
            # We can't use M_inv here directly, so use pixel_to_chess inverse
            # Instead just score the raw signed diff image per-square bounding box
            score = float(np.mean(signed))  # fallback
            if score > best_score:
                best_score = score
                best_sq = coord

    return best_sq  # refined below with proper mask

def diff_from_square(ref_frame, cur_frame, board_mask, corner_pts, M, M_inv, exclude=None):
    """
    Per-square mean diff using proper perspective masks.
    Returns the square whose brightness dropped most (piece left).
    """
    ref_gray = cv2.cvtColor(ref_frame, cv2.COLOR_BGR2GRAY).astype(np.float32)
    cur_gray = cv2.cvtColor(cur_frame, cv2.COLOR_BGR2GRAY).astype(np.float32)
    # Positive = got darker in cur vs ref = piece was removed
    dropped = ref_gray - cur_gray
    dropped = np.clip(dropped, 0, 255)
    if board_mask is not None:
        dropped *= (board_mask / 255.0)

    h, w = dropped.shape
    best_sq = None
    best_score = -1

    for r in range(8):
        for c in range(8):
            coord = COLS[c] + ROWS[r]
            if coord == exclude:
                continue
            sq_mask = np.zeros((h, w), dtype=np.uint8)
            poly = np.array([
                board_to_img(c*CELL,     r*CELL,     M_inv),
                board_to_img((c+1)*CELL, r*CELL,     M_inv),
                board_to_img((c+1)*CELL, (r+1)*CELL, M_inv),
                board_to_img(c*CELL,     (r+1)*CELL, M_inv),
            ], dtype=np.int32)
            cv2.fillPoly(sq_mask, [poly], 255)
            pixels = dropped[sq_mask > 0]
            if len(pixels) == 0:
                continue
            score = float(np.mean(pixels))
            if score > best_score:
                best_score = score
                best_sq = coord

    return best_sq

# ── point seeding ─────────────────────────────────────────────────────────────

def seed_points(gray, board_mask):
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
    enhanced = clahe.apply(gray)
    pts = cv2.goodFeaturesToTrack(enhanced, mask=board_mask,
        maxCorners=600, qualityLevel=0.003, minDistance=4, blockSize=5)
    ys, xs = np.where(board_mask > 0)
    if len(xs):
        grid = []
        for gx in range(int(xs.min()), int(xs.max()), 8):
            for gy in range(int(ys.min()), int(ys.max()), 8):
                if 0<=gy<board_mask.shape[0] and 0<=gx<board_mask.shape[1]:
                    if board_mask[gy, gx] > 0:
                        grid.append([[float(gx), float(gy)]])
        if grid:
            garr = np.array(grid, dtype=np.float32)
            pts = np.concatenate([pts, garr]) if pts is not None else garr
    return pts

# ── hand filter ───────────────────────────────────────────────────────────────

def filter_hand(p0, p1, status):
    ok = status.ravel() == 1
    gp0 = p0[ok]; gp1 = p1[ok]
    if len(gp0) == 0:
        return gp0, gp1
    disp = gp1 - gp0
    med  = np.median(disp, axis=0)
    residual = np.linalg.norm(disp - med, axis=1)
    keep = residual > 1.2
    if keep.sum() < 4:
        return gp0, gp1
    return gp0[keep], gp1[keep]

# ── to-square from tracking ───────────────────────────────────────────────────

def record_motion(bucket, pts, M):
    for p in pts:
        coord = pixel_to_chess(float(p[0]), float(p[1]), M)
        bucket[coord] = bucket.get(coord, 0) + 1

def top_square(bucket, exclude=None):
    f = {k:v for k,v in bucket.items() if k != exclude and v >= 2}
    return max(f, key=lambda k: f[k]) if f else None

# ── drawing ───────────────────────────────────────────────────────────────────

def draw_grid(frame, M_inv, from_sq, to_sq, active_sqs):
    overlay = frame.copy()
    for r in range(8):
        for c in range(8):
            poly = np.array([board_to_img(c*CELL,r*CELL,M_inv),
                             board_to_img((c+1)*CELL,r*CELL,M_inv),
                             board_to_img((c+1)*CELL,(r+1)*CELL,M_inv),
                             board_to_img(c*CELL,(r+1)*CELL,M_inv)], dtype=np.int32)
            cv2.fillPoly(overlay, [poly], (65,55,45) if (r+c)%2==0 else (30,25,20))
    for coord,col in [(from_sq,(40,40,200)),(to_sq,(40,180,40))]:
        if not coord: continue
        c,r=COLS.index(coord[0]),ROWS.index(coord[1])
        poly = np.array([board_to_img(c*CELL,r*CELL,M_inv),
                         board_to_img((c+1)*CELL,r*CELL,M_inv),
                         board_to_img((c+1)*CELL,(r+1)*CELL,M_inv),
                         board_to_img(c*CELL,(r+1)*CELL,M_inv)], dtype=np.int32)
        cv2.fillPoly(overlay, [poly], col)
    cv2.addWeighted(overlay, 0.4, frame, 0.6, 0, frame)
    for i in range(9):
        cv2.line(frame,board_to_img(i*CELL,0,M_inv),board_to_img(i*CELL,BOARD_SIZE,M_inv),(160,160,160),1)
        cv2.line(frame,board_to_img(0,i*CELL,M_inv),board_to_img(BOARD_SIZE,i*CELL,M_inv),(160,160,160),1)
    for c in range(8):
        pt=board_to_img(int((c+0.5)*CELL),BOARD_SIZE-18,M_inv)
        cv2.putText(frame,COLS[c],(pt[0]-6,pt[1]),cv2.FONT_HERSHEY_SIMPLEX,0.45,(255,220,0),1,cv2.LINE_AA)
    for r in range(8):
        pt=board_to_img(8,int((r+0.5)*CELL),M_inv)
        cv2.putText(frame,ROWS[r],(pt[0],pt[1]+5),cv2.FONT_HERSHEY_SIMPLEX,0.45,(255,220,0),1,cv2.LINE_AA)
    for coord,lc in [(from_sq,(180,180,255)),(to_sq,(180,255,180))]:
        if not coord: continue
        c,r=COLS.index(coord[0]),ROWS.index(coord[1])
        ctr=board_to_img(int((c+0.5)*CELL),int((r+0.5)*CELL),M_inv)
        cv2.putText(frame,coord,(ctr[0]-14,ctr[1]+6),cv2.FONT_HERSHEY_SIMPLEX,0.55,lc,2,cv2.LINE_AA)
    for i,coord in enumerate(active_sqs[:2]):
        c,r=COLS.index(coord[0]),ROWS.index(coord[1])
        ctr=board_to_img(int((c+0.5)*CELL),int((r+0.5)*CELL),M_inv)
        edge=board_to_img(int((c+1)*CELL),int((r+0.5)*CELL),M_inv)
        rad=int(np.linalg.norm(np.array(ctr)-np.array(edge)))
        cv2.circle(frame,ctr,rad,[(0,255,80),(0,120,255)][i],2)
        cv2.circle(frame,ctr,4,[(0,255,80),(0,120,255)][i],-1)

def draw_second_window(ref_frame, cur_frame, trail_pts, late_bucket, board_mask, corner_pts, M_inv):
    """Left half = diff (for from-sq), right half = track trails (for to-sq)."""
    if cur_frame is None:
        return np.zeros((480, 640, 3), dtype=np.uint8)
    h, w = cur_frame.shape[:2]
    canvas = np.zeros((h, w, 3), dtype=np.uint8)

    # Diff visualisation
    if ref_frame is not None and cur_frame is not None:
        ref_g = cv2.cvtColor(ref_frame, cv2.COLOR_BGR2GRAY).astype(np.float32)
        cur_g = cv2.cvtColor(cur_frame,  cv2.COLOR_BGR2GRAY).astype(np.float32)
        dropped = np.clip(ref_g - cur_g, 0, 255).astype(np.uint8)
        dropped = cv2.convertScaleAbs(dropped, alpha=3.0)
        if board_mask is not None:
            dropped = cv2.bitwise_and(dropped, board_mask)
        canvas = cv2.cvtColor(dropped, cv2.COLOR_GRAY2BGR)

    # Overlay track trails
    for p0, p1 in trail_pts[-600:]:
        sp = float(np.linalg.norm(np.array(p1)-np.array(p0)))
        if sp < 0.5: continue
        cv2.arrowedLine(canvas, tuple(int(v) for v in p0), tuple(int(v) for v in p1),
                        (0, min(255,int(sp*40)), 255), 1, tipLength=0.5)

    # Late bucket top square label
    if late_bucket:
        best = max(late_bucket, key=lambda k: late_bucket[k])
        cv2.putText(canvas, f"TO (track): {best}", (10, 28),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (180,255,180), 2, cv2.LINE_AA)
    cv2.putText(canvas, "FROM=diff (bright)  TO=tracks (arrows)", (10, h-10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (160,160,160), 1, cv2.LINE_AA)
    return canvas

# ── mouse ─────────────────────────────────────────────────────────────────────

corner_pts=[]; selecting=False

def mouse_cb(event,x,y,flags,param):
    global corner_pts,selecting
    if selecting and event==cv2.EVENT_LBUTTONDOWN and len(corner_pts)<4:
        corner_pts.append((x,y))
        print(f"  Corner {len(corner_pts)}: ({x},{y})")
        if len(corner_pts)==4:
            selecting=False; save_corners(corner_pts)

# ── main ──────────────────────────────────────────────────────────────────────

def main():
    global corner_pts, selecting
    cap=cv2.VideoCapture(2)
    if not cap.isOpened():
        print("Error opening webcam"); return

    cv2.namedWindow("1 - Live")
    cv2.setMouseCallback("1 - Live", mouse_cb)

    corner_pts=load_corners()
    auto_status=""
    prev_gray=None; tracking=False
    pts_tracked=None
    ref_frame=None       # snapshot taken at start of tracking (before move)
    late_bucket={}
    frame_count=0
    trail_pts=[]
    from_sq=to_sq=None; active_sqs=[]
    last_frame=None

    LK=dict(winSize=(21,21),maxLevel=3,
            criteria=(cv2.TERM_CRITERIA_EPS|cv2.TERM_CRITERIA_COUNT,30,0.01))

    print("SPACE: start/confirm | A: auto | P: manual | R: reset | C: clear | Q: quit")

    while True:
        ret,frame=cap.read()
        if not ret: break
        last_frame=frame.copy()
        gray=cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY)
        board_ready=len(corner_pts)==4

        # ── LK tracking ───────────────────────────────────────────────────
        if tracking and board_ready and prev_gray is not None:
            M,M_inv=get_matrices(corner_pts)
            board_mask=get_board_mask(gray.shape,corner_pts)

            if pts_tracked is None:
                pts_tracked=seed_points(prev_gray,board_mask)

            if pts_tracked is not None and len(pts_tracked)>0:
                pts_next,status,_=cv2.calcOpticalFlowPyrLK(
                    prev_gray,gray,pts_tracked,None,**LK)

                if pts_next is not None and status is not None:
                    p0=pts_tracked.reshape(-1,2)
                    p1=pts_next.reshape(-1,2)
                    good_p0,good_p1=filter_hand(p0,p1,status)

                    frame_count+=1
                    # Late bucket for to-square (all frames — tracking finds to well)
                    record_motion(late_bucket, good_p1, M)

                    for a,b in zip(good_p0[:200],good_p1[:200]):
                        trail_pts.append((a.tolist(),b.tolist()))

                    pts_tracked=pts_next[status.ravel()==1].reshape(-1,1,2)
                    if len(pts_tracked)<8:
                        new=seed_points(gray,board_mask)
                        if new is not None:
                            pts_tracked=np.concatenate([pts_tracked,new])

        prev_gray=gray.copy()

        # ── Window 1 ──────────────────────────────────────────────────────
        display=frame.copy()
        if board_ready:
            M,M_inv=get_matrices(corner_pts)
            draw_grid(display,M_inv,from_sq,to_sq,active_sqs)
        elif corner_pts:
            for i,p in enumerate(corner_pts):
                cv2.circle(display,p,7,(0,255,255),-1)
                cv2.putText(display,str(i+1),(p[0]+8,p[1]+5),cv2.FONT_HERSHEY_SIMPLEX,0.5,(0,255,255),1)
            for i in range(len(corner_pts)-1):
                cv2.line(display,corner_pts[i],corner_pts[i+1],(0,255,255),1)

        if tracking and pts_tracked is not None:
            for pt in pts_tracked.reshape(-1,2)[:300]:
                cv2.circle(display,tuple(pt.astype(int)),2,(0,255,255),-1)


        n=len(pts_tracked) if pts_tracked is not None else 0
        if selecting:
            label=f"Click corner {len(corner_pts)+1}/4 (TL>TR>BR>BL)"
        elif auto_status:
            label=auto_status
        elif not board_ready:
            label="A: auto-detect  |  P: manual corners"
        elif tracking:
            label=f"Tracking — {n} pts, {frame_count} frames  |  SPACE to confirm"
        elif from_sq and to_sq:
            label=f"{from_sq} -> {to_sq}  |  SPACE: next move"
        else:
            label=f"SPACE: start tracking"

        cv2.putText(display,label,(10,28),cv2.FONT_HERSHEY_SIMPLEX,0.6,(0,220,255),2,cv2.LINE_AA)
        cv2.imshow("1 - Live",display)

        # ── Window 2 ──────────────────────────────────────────────────────
        if board_ready:
            bm=get_board_mask(frame.shape,corner_pts)
            M,M_inv=get_matrices(corner_pts)
            tw=draw_second_window(ref_frame,last_frame,trail_pts,late_bucket,bm,corner_pts,M_inv)
            cv2.imshow("2 - Diff + Tracks",tw)
        else:
            ph=np.zeros_like(frame)
            cv2.putText(ph,"Define board first",(10,frame.shape[0]//2),
                        cv2.FONT_HERSHEY_SIMPLEX,0.65,(0,200,255),2)
            cv2.imshow("2 - Diff + Tracks",ph)

        key=cv2.waitKey(1)&0xFF
        if key==ord('q'): break
        elif key==ord('a'):
            auto_status="Detecting..."
            det,raw=auto_detect_corners(frame)
            if det:
                corner_pts=det; from_sq=to_sq=None; active_sqs=[]
                tracking=False; pts_tracked=None; ref_frame=None
                late_bucket={}; trail_pts=[]; frame_count=0
                selecting=False; auto_status="Detected! SPACE to start."
                fb=frame.copy()
                cv2.drawChessboardCorners(fb,INNER,raw.reshape(-1,1,2),True)
                for p in corner_pts: cv2.circle(fb,p,8,(0,255,0),-1)
                cv2.imshow("1 - Live",fb); cv2.waitKey(800)
            else:
                auto_status="Failed — show full board"
        elif key==ord('p'):
            corner_pts=[]; selecting=True; from_sq=to_sq=None; active_sqs=[]
            tracking=False; pts_tracked=None; ref_frame=None
            late_bucket={}; trail_pts=[]; frame_count=0; auto_status=""

        elif key==ord('c'):
            corner_pts=[]; selecting=False; from_sq=to_sq=None; active_sqs=[]
            tracking=False; pts_tracked=None; ref_frame=None
            late_bucket={}; trail_pts=[]; frame_count=0; auto_status=""
        elif key==ord('r'):
            tracking=False; pts_tracked=None; ref_frame=None
            late_bucket={}; trail_pts=[]; frame_count=0
            from_sq=to_sq=None; active_sqs=[]; auto_status=""
            print("Reset.")
        elif key==ord(' '):
            if not board_ready:
                print("Define board first."); continue
            if not tracking:
                # Snapshot the board BEFORE the move for diff-based from detection
                ref_frame=frame.copy()
                late_bucket={}; trail_pts=[]; frame_count=0
                pts_tracked=None; from_sq=to_sq=None; active_sqs=[]
                tracking=True; auto_status=""
                print("Tracking started. Make the move then SPACE.")
            else:
                tracking=False
                M,M_inv=get_matrices(corner_pts)
                bm=get_board_mask(frame.shape,corner_pts)

                # TO = most active square from tracking (proven reliable)
                to_sq = top_square(late_bucket)

                # FROM = square that got darkest in diff (piece was removed)
                if ref_frame is not None:
                    from_sq = diff_from_square(ref_frame, frame, bm, corner_pts, M, M_inv, exclude=to_sq)
                else:
                    from_sq = None

                active_sqs=[s for s in [from_sq,to_sq] if s]
                if from_sq and to_sq:
                    print(f"✓ Move: {from_sq} -> {to_sq}")
                else:
                    print(f"Incomplete — from={from_sq} to={to_sq} (R to retry)")

    cap.release()
    cv2.destroyAllWindows()

if __name__=="__main__":
    main()