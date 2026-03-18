#USE PYTHON 3.13.11
#Based off https://github.com/FreeOpcUa/opcua-asyncio/blob/master/examples/client-minimal.py

import asyncio
from asyncua import Client


url = "opc.tcp://localhost:4840" #"opc.tcp://localhost:4840/chessica"
namespace = "http://opcua.chessica.io"

#Wrapper around input() to make it run asynchronously
#Required or else various things break down with the async OPC UA
async def async_input(prompt: str) -> str:
    return await asyncio.to_thread(input, prompt)

async def main():
    print(f"Connecting to {url} ...")
    async with Client(url=url) as client:
        nsidx = await client.get_namespace_index(namespace)
        print(f"Namespace Index for '{namespace}':{nsidx}")

        runtime = await client.nodes.root.get_child(f"0:Objects/{nsidx}:Comms/{nsidx}:runtime")
        ready = await client.nodes.root.get_child(f"0:Objects/{nsidx}:Comms/{nsidx}:ready")
        print(f"runtime: {await runtime.read_value()}")
        print(f"ready: {await ready.read_value()}")
        
        while True:
            if(not await ready.read_value()): #Server not ready (ready == False) for next move
                print("Waiting...")
                await asyncio.sleep(0.1)
                continue
            else:
                #await runtime.write_value(999999999.9) #This should fail when uncommented as it is READ-ONLY
                inputStr = await async_input("Ready for next move [y/n]? ")
                if(inputStr.lower() == "y"):
                    await ready.write_value(False)

if __name__ == "__main__":
    asyncio.run(main())