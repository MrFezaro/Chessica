#Based off https://github.com/FreeOpcUa/opcua-asyncio/blob/master/examples/client-minimal.py

import asyncio
from asyncua import Client


url = "opc.tcp://localhost:4841" #"opc.tcp://localhost:4840/chessica"
namespace = "http://opcua.chessica.io"

async def main():
    print(f"Connecting to {url} ...")
    async with Client(url=url) as client:
        print("EXPLODE")

        nsidx = await client.get_namespace_index(namespace)
        print(f"Namespace Index for '{namespace}': {nsidx}")

        obj = await client.nodes.root.get_child(f"0:Objects/{nsidx}:MyObject/{nsidx}")
        print("obj: " + obj)

        runtime = client.nodes.root.get_child(f"0:Objects/{nsidx}:Comms/{nsidx}:runtime")
        ready = client.nodes.root.get_child([f"0:Objects/{nsidx}:Comms/{nsidx}::ready"])
        print(f"runtime: {await runtime.read_value()}")
        print(f"ready: {await ready.read_value()}")
        
        while True:
            runtime.write_value(999999999.9) #This should fail
            inputStr = input("Ready for next move? ").lower()
            if(inputStr != "n" and len(inputStr) > 1 or inputStr == "y"):
                await ready.write_value(True)

if __name__ == "__main__":
    asyncio.run(main())