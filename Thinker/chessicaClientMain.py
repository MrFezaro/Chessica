#USE PYTHON 3.13.11
#Client with virtual PLC as server

import inspect
import datetime
import asyncio
import chess
from asyncua import Client
import brain
import supersecret

#If console commands should be enabled. SHOULD BE FALSE outside of testing.
CONSOLE_COMMANDS : bool = True
#How many nodes deep the bot should explore
BOT_DEPTH : int = 10

initialChessBoard = chess.Board()

#--- OPC-UA Setup ---
url = "opc.tcp://158.38.140.60:4840"
username = "admin"
password = "NTNUIndSysavnj9"

nodeReadyId = "ns=5;b=AQAAAKbhKnGK9zM6uvotdobvYEeM925mjOIkbek=" #OUTPUT, if PLC is ready
nodeMoveInputId = "ns=5;b=AQAAAKbhKnGK9zM6uvotdobvYEeM9255hvUlXYfzNWDp" #INPUT, move for PLC to execute
nodeMoveExecuteId = "ns=5;b=AQAAAKbhKnGK9zM6uvotdobvYEeM925xkeYjYZ3mDXuf5kA=" #INPUT Rising Edge, execute move

#--- ---

#Wrapper around input() to make it run asynchronously
#Required or else various things break down with the async OPC UA
async def async_input(prompt: str) -> str:
    return await asyncio.to_thread(input, prompt)

async def main():
    #
    #--- inner func zone! ---
    #

    async def sendMove(move : str) -> None:
        print(f"Made move: {move}")
        await nodeMoveInput.write_value(move)
        return

    async def sendExecute() -> None:
        await nodeMoveExecute.write_value(True)
        return

    #Commands:
    #move [uci move]
    #ready [optional y/n]
    #reset
    #history | aliases: h, hist
    async def inputCommand(input : str) -> None:
        cmd : list[str] = input.lower().split(" ")
        if(cmd[0] == "h" or cmd[0] == "help"):
            print("""✨ Chessica - Clever Linearized Intelligience (CLI) ✨
help \t\t| @grok what is this           
move [move] \t| Supposed to represent opponent moves. Assigns UCI move to board stack. If no parameters provided: outputs latest move with the team color.  
execute [move] \t| Alias: exec | Supposed to represent Chessica moves. Assigns move to OPC-UA MoveInput node. Chessica will remember this. If no parameters provided: sends latest move to PLC. 
ready [y/n] \t | Assigns True/False to the OPC-UA Ready node, forcing PLC to appear ready. If no parameters provided: outputs node's current status.               
reset \t\t| Resets the board to the standard chess setup.               
history [wrap] \t| Alias: hist | Displays the entire move history of the current board. Optionally wraps output to [wrap] (int)
load [abs_filepath] \t | Loads a board from a .pgn file. Path is absolute.
think \t | Makes Chessica make a move on her own.
            """)
            return

        if(cmd[0] == "move"):
            if(len(cmd) == 1):
                print(chessimind.board)
                whiteTurn = len(chessimind.board.move_stack) % 2 == 0
                team = "White"
                if(whiteTurn): 
                    team = "Black"

                try:
                    print(f"Last move: {chessimind.board.peek()} ({team})")
                except:
                    print(f"No moves yet.")

            else:
                try:
                    move : chess.Move = chess.Move.from_uci(cmd[1])
                except chess.InvalidMoveError as err:
                    print(f"{err}: Invalid move format. Expected UCI format: xyuv")

                    return
                
                if(chessimind.board.is_legal(move)):
                    chessimind.applyMove(move)
                    print(f"Move added: {move}")
                else:
                    print(f"Illegal move!")

            return
        
        if(cmd[0] == "ready"):
            if(len(cmd) == 1):
                print(await nodeReady.read_value())
                return
            
            shouldReady = cmd[1][0] == "y" and not cmd[1][0] == "n"
            await nodeReady.write_value(shouldReady)
            print(f"ready set to {shouldReady}")
            return
    
        if(cmd[0] == "reset"):
            print("RESETTING BOARD")
            chessimind.board = chess.Board()
            chessimind.board = chess.Board()
            return
        
        if(cmd[0] == "history" or cmd[0] == "hist"):
            wrap = 8
            if(len(cmd) > 1 and cmd[1] != ""):
                if(cmd[1].isdigit() and int(cmd[1]) != 0):
                    wrap = abs(int(cmd[1]))
                else:
                    print(f"Invalid wrap number. Defaulting to {wrap}")
                
            print(f"Move history (wrap = {wrap}):")
            if(len(chessimind.board.move_stack) == 0):
                print("(empty)")
                return
            
            i = 0
            toPrint = ""
            for m in chessimind.board.move_stack:
                toPrint += m.uci() + " "
                i += 1
                if(i % wrap == 0):
                    toPrint += "\n"
            
            toPrint = toPrint.replace(" ", " -> ")
            print(toPrint)
            return

        if(cmd[0] == "execute" or cmd[0] == "exec"):
            try:
                if(len(cmd) == 1):
                    customUci = chessimind.toCustomUci(chessimind.board.peek(), chessimind.previousBoard)
                    await sendMove(customUci)
                    await sendExecute()
                    return
            except Exception as err:
                print(f"ERROR: {err}")
                print(f"No move to execute")
                return
            
            try:
                move : chess.Move = chess.Move.from_uci(cmd[1])
            except chess.InvalidMoveError as err:
                print(f"{err}: Invalid move format. Expected UCI format: xnym")
                return
            
            if(chessimind.board.is_legal(move)):
                customUci = chessimind.toCustomUci(move)
                chessimind.applyMove(move)
                await sendMove(customUci)
                await sendExecute()
            else:
                print(f"Illegal move! Not executing.")            
            return
        
        if(cmd[0] == "load"):
            if(len(cmd) == 1):
                print("No filepath provided")
                return
            
            if(not cmd[1].endswith(".pgn")):
                print("Not a recognized .pgn file!")

            boardFilePath = cmd[1]
            success = chessimind.loadBoard(boardFilePath)
            if(success):
                print("Board loaded")
            return

        if(cmd[0] == "think"):
            print(f"Chessica says: {supersecret.makeThing()}")
            move = chessimind.makeMove()
            await sendMove(move)
            await sendExecute()
            return
        
        print("Not a recognized command. Did you mistype? Type 'help' or 'h' for help.")
    #
    #--- no more func ---
    #

    print(f"Connecting to {url} ...")

    client = Client(url)
    try:
        #____ Connect to OPC-UA server ____
        client.set_user(username)
        client.set_password(password)

        await client.connect()

        #___ Actual code ___
        print(f"CONNECTED!")

        nodeReady = client.get_node(nodeReadyId)
        nodeMoveInput = client.get_node(nodeMoveInputId)
        nodeMoveExecute = client.get_node(nodeMoveExecuteId)

        chessimind = brain.Brain(BOT_DEPTH, initialChessBoard)

        coldboot : bool = True
        prevReady : bool = False
        wannaExit : bool = False
        while not wannaExit:
            while not chessimind.gameComplete():

                #Awaits PLC to give a ready signal before deducing opponent's move and executing own move
                #Only on rising edge
                if(not coldboot and await nodeReady.read_value() and not prevReady):
                    #TODO: Shove in camera vision code
                    #Read board status (camera): afterOpponentMove
                    #Check if move is legal (get data from camera)
                    #If NOT legal: give some sort of error signal

                    #else if legal: Perform own move as usual
                    move = chessimind.makeMove()
                    await sendMove(move)
                    await sendExecute()
                    #Read board status (camera): beforeOpponentMove
                    continue
                else:
                    await inputCommand(await async_input("chessica >"))
                    coldboot = False
                    pass

                prevReady = await nodeReady.read_value()
                pass
            
            chessimind.printBoard(
                f"Game {datetime.datetime.today().strftime("%Y-%m-%d, %H-%M-%S")}",
                "Ebic Chessica Gameplay",
                datetime.datetime.today().strftime("%Y-%m-%d, %H:%M:%S"),
                )

        exitInput = await async_input("chessica > Exit program? [y/n] - ")
        exitInput = exitInput.lower()
        wannaExit = exitInput == "y" or exitInput == "yes"
        pass

    finally:
        client.disconnect()
        
    return

if __name__ == "__main__":
    asyncio.run(main())