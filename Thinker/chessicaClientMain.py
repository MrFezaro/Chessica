#USE PYTHON 3.13.11
#Client with virtual PLC as server

import datetime
import asyncio
from asyncua import Client
import brain

chessimind = brain.Brain()

url = "opc.tcp://localhost:4840"

nodeReadyId = "" #OUTPUT, if PLC is ready
nodeMoveInputId = "" #INPUT, move for PLC to execute
nodeMoveExecuteId = "" #INPUT Rising Edge, execute move

#Wrapper around input() to make it run asynchronously
#Required or else various things break down with the async OPC UA
async def async_input(prompt: str) -> str:
    return await asyncio.to_thread(input, prompt)

async def main():
    print(f"Connecting to {url} ...")

    async with Client(url=url) as client:

        nodeReady = client.get_node(nodeReadyId)
        nodeMoveInput = client.get_node(nodeMoveInputId)
        nodeMoveExecute = client.get_node(nodeMoveExecuteId)
        
        while not chessimind.gameComplete():

            if(await nodeReady.read_value()): #Awaits PLC to give a ready signal before doing next move
                move = chessimind.makeMove()

                await nodeMoveInput.write_value(move)

                #Send rising edge pulse
                await nodeMoveExecute.write_value(True)
                await asyncio.sleep(0.1)
                await nodeMoveExecute.write_value(False)

                await asyncio.sleep(0.1)
                continue
            #else:
                #Figure out how to input commands and put stockfish on pause
                #inputCommand(async_input())
        
        chessimind.printBoard(
            f"Game {datetime.datetime.today().strftime("%Y-%m-%d, %H:%M:%S")}",
            "Ebic Chessica Gameplay",
            datetime.datetime.today().strftime("%Y-%m-%d, %H:%M:%S"),
            )

def inputCommand(cmd : str) -> None:

    return 

if __name__ == "__main__":
    asyncio.run(main())