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

    ###!WARNING!   WIP - UNTESTED   ###
    #Deduces the chess move made by the opponent by comparing the newBoard to the previous board (in memory).
    #In fancy terms, it acquires the delta of the boards.
    def deduceOpponentMove(self, newBoard : chess.Board) -> chess.Move:
        #Figure out how to get the delta
        #A piece ALWAYS has to vanish from one square and appear on another
        #If a piece has moved: sum of pieces remains the same. 
        # - 1 previously filled tile is empty, 1 previously empty is filled.
        #If a piece has attacked: sum of pieces is one less
        # - 1 previously filled tile is empty, 1 tile has changed piece colors.
        newMap = newBoard.piece_map()
        map = self._board.piece_map()
        
        move : chess.Move = None
        piece : chess.Piece = None
        wasAttack = False

        #file: a - h (y)
        #rank: 1 - 8 (x)
        currentSquare = 0

        #Calculate deltamove
        #TODO: Deduce castling! (king switches places with tower/rook)
        #TODO: Deduce promotion! (pawn reaches end of board)
        for square in range(chess.H8): #H8 = 63, last tile
            if(map[square] != newMap[square]):
                new : chess.Piece = newMap[square]
                old : chess.Piece= map[square]

                wasAttack = new.color != old.color #Consider passing this to PLC?

                if(old != None and new == None): #Moved from
                    move.from_square = square
                elif((old == None and new != None) or wasAttack): #Moved to OR attacked
                    move.to_square = square
                
                if(move.from_square != -1 and move.to_square != -1):
                    piece = new
                    break

        return move

    #Forces a move onto the board. 
    #Usually this is used for updating the board in response to deducing an opponent's move.
    def applyMove(self, move : chess.Move) -> None:
        self._board.push(move)
        return

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

