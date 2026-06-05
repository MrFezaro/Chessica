# Chessica

> *"I can't lie to you about your chances, but... you have my sympathies."*

## Project Structure

`chessicaClientMain.py` is the main program running on the computer, serving as the entry point 
for the Chessica system. It coordinates the following modules:

- **Thinker** is the chess engine and responsible for move generation, game state 
management, and decision-making.
- **Observer** handles computer vision and AprilTag detection, tracking physical piece 
positions on the board.
- **Mover** contains the PLC program and Universal Robots script responsible for 
physically executing moves on the board.

> **Demo Video:** [Watch on YouTube](https://youtu.be/VDj9hcz8Fek)
---

## Project Poster
<img src="poster.png" width="1000"/>

---

## System Diagram
<img src="diagram.png" width="1000"/>

---

## Final Setup
<img src="final_setup.jpg" width="1000"/>
