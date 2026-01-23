#Based off https://github.com/FreeOpcUa/opcua-asyncio/blob/master/examples/server-minimal.py

import asyncio
import logging

from asyncua import Server, ua
from asyncua.common.methods import uamethod

async def main():
    _logger = logging.getLogger(__name__)

    server = Server()
    await server.init()

    # Set up the server's endpoint
    server.set_endpoint("opc.tcp://0.0.0.0:4841/chessica")

    # Set up the server's namespace
    uri = "http://opcua.chessica.io"
    idx = await server.register_namespace(uri)
    print(f"NAMESPACE idx: {idx}")

    comms = await server.nodes.objects.add_object(idx, "Comms")
    runtimeVar = await comms.add_variable(idx, "runtime", -1.0)
    await runtimeVar.set_writable(False) #Readonly by clients

    readyVar = await comms.add_variable(idx, "ready", False)
    await readyVar.set_writable(True) #Read/write by clients

    #Main loop for server. Preferably this would be in some sort of update function in a real program.
    _logger.info("Starting server!")
    async with server:
        while True:
            await runtimeVar.write_value(await runtimeVar.get_value() + 0.1)
            print(f"Runtime: {await runtimeVar.read_value()}")

            if(await readyVar.get_value()):
                await readyVar.write_value(False)
                print("Executing next move!")

            await asyncio.sleep(0.1)

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    asyncio.run(main(), debug=True)