import typing
from typing import ClassVar, Callable, Counter, Dict, Generic, Hashable, Iterable, Iterator, List, Literal, Mapping, Optional, SupportsInt, Tuple, Type, TypeVar, Union
from typing_extensions import Self, TypeAlias

import os
import chess
import chess.engine
import chess.pgn
from pathlib import Path
from Observer.tag import AprilTagChessTracker

#Convert a camera piece to chess library piece type.
CAM_PIECE_TO_CHESS_PIECE : dict = {
    "pawn" : chess.PAWN,
    "horse" : chess.KNIGHT,
    "rook" : chess.ROOK,
    "bishop" : chess.BISHOP,
    "queen" : chess.QUEEN,
    "king" : chess.KING
}

#Python has no enums so here we go
MoveSearchStatus: TypeAlias = int
MSE_OK : MoveSearchStatus = 0
MSE_ERROR : MoveSearchStatus = -1 #Illegal move
MSE_NO_CHANGE : MoveSearchStatus = 1 #No change.

class Brain:
    _engine : chess.engine.SimpleEngine = chess.engine.SimpleEngine.popen_uci(r"C:/_dev/Chessica/Thinker/stockfish-windows-x86-64-avx2/stockfish-windows-x86-64-avx2.exe")
    _vision : AprilTagChessTracker = None

    showVisionWindow : bool = True
    
    board : chess.Board = None
    previousBoard : chess.Board = None
    #How deep should the engine explore, e.g. how many steps in the future.

    timePerMove = 0.01 #In seconds

    def __init__(self, searchDepth : int, initialBoard : chess.Board, cameraIndex : int = 0):
        self._initCameraVision(cameraIndex)
        self._engine.options["Depth"] = searchDepth
        self.board = initialBoard
        return

    def setCamera(self, cameraIndex : int) -> None:
        self._vision.set_camera(cameraIndex)
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

        if(referenceBoard.is_en_passant(move)): #En passant is always pawn vs pawn
            moveResult += "p"
            capturedPieceType : str = "P".upper()
            moveResult += capturedPieceType
            return moveResult

        elif(referenceBoard.is_capture(move)):
            if(moveResult[-1] == "q"): #Replace standard UCI promotion mark with attack promotion mark
                moveResult = moveResult.replace("q", "Q")
            else:
                moveResult += "x"
        
        elif(referenceBoard.is_castling(move)):
            moveResult += "c"
        
        if(referenceBoard.is_capture(move)): #If capture, append the piece type captured
            capturedPieceType : str = referenceBoard.piece_at(move.to_square).symbol().upper()
            moveResult += capturedPieceType

        return moveResult

    def openYourEyeAndSee(self) -> MoveSearchStatus:
        """
        
        I'm just a poor bot, I need no sympathy \n
        Because I'm easy come, easy go \n
        Little high, little low \n
        Any way the piece goes doesn't really matter to me... \n
        To me... \n
        Mama, just took a knight \n
        Put a pawn against his head, pushed him off, now he's dead \n
        \n
        Uses camera vision to apply opponent's move to internal state.
        Returns a `MoveSearchStatus`.
        """
        newBoard = self.cameraBoardToChessBoard(self._vision.update_game_state(show = self.showVisionWindow))
        print(f"new board:\n{newBoard}\ncurrent board:\n{self.board}")
        status, move = self.searchForMove(self.board, newBoard)
        status : MoveSearchStatus = status #Type hinting
        move : chess.Move = move
        if(status == MSE_OK):
            print(f"Saw move: {move.uci()}")
            self.board.push(move)

        return status

    def cameraBoardToChessBoard(self, boardDict : dict[str, dict]) -> chess.Board:
        """
        Converts a dictionary representing the board gained from camera vision into
        a :class:`~chess.Board` without a move stack.
        Expects the dictionary format to be as Dict<str, Dict>, that is:
        ```
        { 
            "e4": {
                "piece": "pawn", 
                "color": "white", 
                "tag_id": 0
            }
        }
        ```
        This should later be used to get a delta board.
        """

        squarePieceDict = {}
        for key in boardDict:
            data = boardDict[key]
            if(data["square"] == None): #Skip pieces outside board
                continue
            
            if("unknown" in data["piece"]):
                continue #Ignore unknowns

            pieceType : chess.PieceType = CAM_PIECE_TO_CHESS_PIECE[data["piece"]]
            print(f"Square: {data["square"]}")
            square : chess.Square = chess.parse_square(data["square"])
            print(f"Square indexed: {square}")
            piece : chess.Piece = chess.Piece(
                pieceType,
                data["color"] == "white"
            )
            squarePieceDict[square] = piece

        physBoard = chess.Board.empty()
        
        physBoard.set_piece_map(squarePieceDict)
        return physBoard

    def searchForMove(self, oldBoard : chess.Board, newBoard : chess.Board) -> Tuple:
        """
        Searches for the move that leads from `oldBoard` to `newBoard`.
        Does not modify `oldBoard`.
        Not intended to search more than 1 ply.
        (This is more flexxible and easier to code compared to difficult deduction code)

        Returns a tuple of `(MoveSearchStatus, chess.Move)`
        """
        status : MoveSearchStatus = MSE_ERROR
        move = chess.Move.null()

        if(oldBoard.fen() == newBoard.fen()):
            status = MSE_NO_CHANGE
            return (status, move)

        workBoard = oldBoard.copy()

        for m in workBoard.legal_moves:
            if(workBoard.piece_at(m.from_square) == None):
                #Raise alarm, order PLC to move robot above board,
                #then take a picture from a different angle
                continue #Not implemented due to time constraints

            workBoard.push(m)
            #print(f"Trying {m}")
            if(workBoard.fen() == newBoard.fen()):
                status = MSE_OK
                move = m
                break
            else:
                workBoard.pop() #Remove previous move before next iteration
        
        return (status, move)

    #Applies a move to the board
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

    def _initCameraVision(self, cameraIndex) -> None:
        print("Initializing tag observer...")
        self._vision : AprilTagChessTracker = AprilTagChessTracker(cameraIndex)
        self._vision.init()
        
        print("Loading camera calibration file")
        self._vision.load_calibration(os.getcwd() + "/Observer/camera_calibration.npz")
        return
    
pass

