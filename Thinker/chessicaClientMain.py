#USE PYTHON 3.13.11
#Client with virtual PLC as server

import datetime
import asyncio
import chess
from asyncua import Client
import brain

#If console commands should be enabled. SHOULD BE FALSE outside of testing.
CONSOLE_COMMANDS : bool = True
#How many nodes deep the bot should explore
BOT_DEPTH : int = 10

initialChessBoard = chess.Board()

#--- OPC-UA Setup ---
url = "opc.tcp://localhost:4840"

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
    #Commands:
    #move [uci move]
    #ready [optional y/n]
    #reset
    #history | aliases: h, hist
    async def inputCommand(input : str) -> None:
        cmd : list[str] = input.lower().split(" ")
        #Input move command
        if(cmd[0] == "move"):
            if(len(cmd) == 1):
                whiteTurn = len(chessimind.board.move_stack) % 2 == 0
                team = "White"
                if(whiteTurn): team = "Black"
                print(f"Last move: {chessimind.board.peek()} ({team})")
                return
            try:
                move : chess.Move = chess.Move.from_uci(cmd[1])
            except chess.InvalidMoveError as err:
                print(f"{err}: Invalid move format. Expected UCI format: xnym")
                return
            
            if(chessimind.board.is_legal(move)):
                chessimind.applyMove(move)
            else:
                print(f"Illegal move!")
            return
        
        if(cmd[0] == "ready"):
            if(len(cmd) == 1):
                print(await nodeReady.read_value())
                return
            
            shouldReady = cmd[1][0] == "y" and not cmd[1][0] == "n"
            await nodeReady.write_value(shouldReady)
            print(f"ready is {shouldReady}")
            return
    
        if(cmd[0] == "reset"):
            print("RESETTING BOARD")
            chessimind.board = chess.Board()
            return
        
        if(cmd[0] == "history" or cmd[0] == "h" or cmd[0] == "hist"):
            wrap = 8
            if(len(cmd) > 1 and cmd[1] != ""):
                if(cmd[1].isdigit()):
                    wrap = abs(cmd[1])
                elif(cmd[1]):
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

        print("Not a recognized command. Did you mistype?")
    #
    #--- no more func ---
    #

    print(f"Connecting to {url} ...")

    async with Client(url=url) as client:
        print(f"CONNECTED!")

        nodeReady = client.get_node(nodeReadyId)
        nodeMoveInput = client.get_node(nodeMoveInputId)
        nodeMoveExecute = client.get_node(nodeMoveExecuteId)

        chessimind = brain.Brain(BOT_DEPTH, initialChessBoard)

        while not chessimind.gameComplete():

            #Awaits PLC to give a ready signal before deducing opponent's move and executing own move
            if(await nodeReady.read_value()):
                #Opponent deduction is a heavy todo. Handling delta must be solved.
                #Example of funky case:
                #ready y | 0000 -> e7e5
                #move a2a4 | -> a2a4
                #ready y | -> 0000* -> e2a4
                #history
                #*this null move is a DIRECT CONSEQUENCE of the current delta handling below this very comment.
                #newBoard = chessimind.board #PLACEHOLDER! Will be replaced with camera vision or commandline user input
                #chessimind.applyMove(chessimind.deduceOpponentMove(newBoard)) #Handle opponent's turn

                move = chessimind.makeMove()
                
                await nodeMoveInput.write_value(move)
                await nodeReady.write_value(False) #PLC WILL be busy, and to ensure only 1 move is sent.

                #Send rising edge pulse
                await nodeMoveExecute.write_value(True)
                await asyncio.sleep(0.1)
                await nodeMoveExecute.write_value(False)
                await asyncio.sleep(0.1)
                continue
            else:
                await inputCommand(await async_input("chessica >"))
                pass

            pass
        
        chessimind.printBoard(
            f"Game {datetime.datetime.today().strftime("%Y-%m-%d, %H-%M-%S")}",
            "Ebic Chessica Gameplay",
            datetime.datetime.today().strftime("%Y-%m-%d, %H:%M:%S"),
            )
        
    return

if __name__ == "__main__":
    asyncio.run(main())