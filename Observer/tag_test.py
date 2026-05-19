import threading
import cv2
from tag import AprilTagChessTracker

print("Initializing tag observer...")
tracker = AprilTagChessTracker(camera_index=1)
tracker.set_camera(1) # Example of camera index switching
tracker.init()

scan_requested = threading.Event()

def input_loop():
    while True:
        input("Press Enter to scan board...")
        scan_requested.set()

threading.Thread(target=input_loop, daemon=True).start()

while True:
    if scan_requested.is_set():
        scan_requested.clear()
        tracker.update_game_state(show=True)
        print(tracker.game_state)
    else:
        cv2.waitKey(30)  # keeps window responsive while waiting