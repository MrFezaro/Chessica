import chess
import chess.engine
import chess.pgn
from pathlib import Path

class Brain:
    _engine : chess.engine.SimpleEngine = chess.engine.SimpleEngine.popen_uci(r"C:/_dev/Chessica/Thinker/stockfish-windows-x86-64-avx2/stockfish-windows-x86-64-avx2.exe")
    _board : chess.Board = None
    #How deep should the engine explore, e.g. how many steps in the future.

    timePerMove = 0.01 #In seconds

    def __init__(self, searchDepth : int, initialBoard : chess.Board):
        self._engine.options["Depth"] = searchDepth
        self._board = initialBoard
        return

    #TODO find out how to play against a human, and decide if the robor is white or black
    #param ponder: Whether the engine should keep running in the background when awaiting its turn.
    #param newBoard: A new board to pass, for example when it turns out opponent did an invalid move and go along with it. If none, keeps using the same board.
    #
    def makeMove(self, ponder : bool = False) -> str:
        result = self._engine.play(
            self._board,
            chess.engine.Limit(time=self.timePerMove),
            info = chess.engine.INFO_NONE,
            ponder = ponder,
            )
        
        self._board.push(result.move)

        if(result.move == None):
            return "0000" #Null move
        else:
            return result.move.uci()

    #Checks if the game is complete.
    #If true is returned, it automatically stops the engine.
    def gameComplete(self) -> bool:
        b = self._board.is_game_over()
        if(b):
            self._engine.quit()
            print("Game Complete")
        return b
    
    def printBoard(self, filename : str, eventName : str, dateTime : str) -> None:
        game = chess.pgn.Game.from_board(self._board)
        game.headers["Event"] = eventName
        game.headers["Date"] = dateTime

        Path("./Thinker/Games/").mkdir(parents=True, exist_ok=True)
        print(game, file=open(f"./Thinker/Games/{filename}.pgn", "x"), end="\n\n")
        return
pass

