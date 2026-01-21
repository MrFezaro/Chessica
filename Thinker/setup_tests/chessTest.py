import chess
import chess.engine
import chess.pgn

engine = chess.engine.SimpleEngine.popen_uci(r"C:/_dev/Chessica/Thinker/stockfish-windows-x86-64-avx2/stockfish-windows-x86-64-avx2.exe")
#How deep should the engine explore, e.g. how many steps in the future.
engine.options["Depth"] = 2

timePerMove = 0.01 #seconds, exact search time

i = 0
moveBuffer = ""

board = chess.Board()
while not board.is_game_over():
    result = engine.play(board, chess.engine.Limit(time=timePerMove), info=chess.engine.INFO_NONE)
    board.push(result.move)

game = chess.pgn.Game.from_board(board)
game.headers["Event"] = "Test"
print(game, file=open("./Thinker/setup_tests/game.pgn", "w"), end="\n\n")
print("Game complete")

engine.quit()

