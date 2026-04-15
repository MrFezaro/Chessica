import chess
import chess.engine
import chess.pgn
from pathlib import Path

class Brain:
    _engine : chess.engine.SimpleEngine = chess.engine.SimpleEngine.popen_uci(r"C:/_dev/Chessica/Thinker/stockfish-windows-x86-64-avx2/stockfish-windows-x86-64-avx2.exe")
    board : chess.Board = None
    previousBoard : chess.Board = None
    #How deep should the engine explore, e.g. how many steps in the future.

    timePerMove = 0.01 #In seconds

    def __init__(self, searchDepth : int, initialBoard : chess.Board):
        self._engine.options["Depth"] = searchDepth
        self.board = initialBoard
        return

    #param ponder: Whether the engine should keep running in the background when awaiting its turn.
    #param newBoard: A new board to pass, for example when it turns out opponent did an invalid move and go along with it. If none, keeps using the same board.
    #returns: A string formatted as UCI, with an appended 'q' if promotion and appended 'x' if piece got taken.
    def makeMove(self, ponder : bool = False) -> str:
        playResult = self._engine.play(
            self.board,
            chess.engine.Limit(time=self.timePerMove),
            info = chess.engine.INFO_NONE,
            ponder = ponder,
            )
        
        out = self.toCustomUci(playResult.move)
        self.board.push(playResult.move)
        return out
        
    #Parses the move into custom UCI for better PLC friendliness by appending characters.
    #This uses the current board state to determine the move type. As calling it after a board update will result
    #in weird results.
    #q - promotion (non-queen promotions unsupported, built into standard UCI) (non-attack promotion)
    #Q - promotion with capture
    #x - capture at end position (attack)
    #p - en passant (special capture)
    #c - castling (short/long gets deduced at PLC)
    def toCustomUci(self, move : chess.Move, referenceBoard : chess.Board = None) -> str:
        if(referenceBoard is None):
            referenceBoard = self.board
        
        moveResult : str = move.uci()

        if(move == None):
            return "_0000" #Null move
        
        #We do not care about piece color
        piece = referenceBoard.piece_at(move.from_square)
        pieceType = "_" #Empty piece type
        if(piece != None):
            pieceType : str = piece.symbol().upper()
        
        moveResult = pieceType + moveResult

        if(referenceBoard.is_en_passant(move)):
            moveResult += "p"

        elif(referenceBoard.is_capture(move)):
            if(moveResult[-1] == "q"): #Replace standard UCI promotion mark with attack promotion mark
                moveResult = moveResult.replace("q", "Q")
            else:
                moveResult += "x"
        
        elif(referenceBoard.is_castling(move)):
            moveResult += "c"
        
        return moveResult

    ###!WARNING!   WIP - UNTESTED  and also huge TODO###
    ##AWAITING CAMERA VISION TO IMPLEMENT THIS
    #Deduces the chess move made by the opponent by comparing the newBoard to the previous board (in memory).
    #In fancy terms, it acquires the delta of the boards.
    #Also checks if whatever move was made by the opponent was valid! If not, it will output and propagate an alarm signal to the PLC.
    def deduceOpponentMove(self, newBoard : chess.Board) -> chess.Move:
        #Figure out how to get the delta
        #A piece ALWAYS has to vanish from one square and appear on another
        #If a piece has moved: sum of pieces remains the same. 
        # - 1 previously filled tile is empty, 1 previously empty is filled.
        #If a piece has attacked: sum of pieces is one less
        # - 1 previously filled tile is empty, 1 tile has changed piece colors.
        newMap = newBoard.piece_map()
        map = self.board.piece_map()
        
        move : chess.Move = chess.Move.null()
        wasAttack = False

        #Calculate deltamove
        #TODO: Deduce castling! (king switches places with tower/rook)
        #TODO: Deduce promotion! (pawn reaches end of board)
        #TODO: Deduce en passant (low priority)
        for square in range(chess.H8): #H8 = 63, last tile
            new : chess.Piece = None
            if(square in newMap): new = newMap[square]

            old : chess.Piece = None
            if(square in map): old = map[square]

            if(old != new):
                wasAttack = (old != None and new != None) and (new.color != old.color)

                if(old != None and new == None): #Moved from
                    move.from_square = square

                elif((old == None and new != None) or wasAttack): #Moved to OR attacked
                    move.to_square = square
                
                if(move.from_square != -1 and move.to_square != -1):
                    piece = new
                    break

        return move

    #Applies a move to he board
    def applyMove(self, move : chess.Move) -> None:
        self.previousBoard = self.board.copy()
        self.board.push(move)
        return

    #Checks if the game is complete.
    #If true is returned, it automatically stops the engine.
    def gameComplete(self) -> bool:
        b = self.board.is_game_over()
        if(b):
            self._engine.quit()
            print("Game Complete")
        return b
    
    #Returns whether loading succeeded
    def loadBoard(self, filename : str) -> bool:
        try:
            pgn = open(filename)
            self.board = chess.pgn.read_game(pgn).board()
            return self.board != None
        except OSError as err:
            print(f"Cannot open file '{filename}'. Error: {err}")

        return False

    def printBoard(self, filename : str, eventName : str, dateTime : str) -> None:
        game = chess.pgn.Game.from_board(self.board)
        game.headers["Event"] = eventName
        game.headers["Date"] = dateTime

        Path("./Thinker/Games/").mkdir(parents=True, exist_ok=True)
        print(game, file=open(f"./Thinker/Games/{filename}.pgn", "x"), end="\n\n")
        return
pass

