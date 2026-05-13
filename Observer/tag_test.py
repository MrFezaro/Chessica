import tag
import threading
import cv2

print("Initializing tag observer...")
tag.init()

scan_requested = threading.Event()

def input_loop():
    while True:
        input("Press Enter to scan board...")
        scan_requested.set()

threading.Thread(target=input_loop, daemon=True).start()

while True:
    if scan_requested.is_set():
        scan_requested.clear()
        tag.update_game_state(show=True)
        print(tag.game_state)
    else:
        cv2.waitKey(30)  # keeps window responsive while waiting