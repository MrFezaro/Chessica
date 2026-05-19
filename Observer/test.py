import cv2

cap = cv2.VideoCapture(2)  # try 0, 1, 2 if needed

while True:
    ret, frame = cap.read()
    if not ret:
        break
    cv2.imshow('STC-MCA5MUSB3', frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()