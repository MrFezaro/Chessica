#Based off https://github.com/FreeOpcUa/opcua-asyncio/blob/master/examples/sync/server-minimal.py

import time
from asyncua.sync import Server

server = Server()

# Set up the server's endpoint
server.set_endpoint("opc.tcp://localhost:4840/freeopcua/server/")

# Set up the server's namespace
uri = "http://opcua.chessica.io"
idx = server.register_namespace(uri)

comms = server.nodes.objects.add_object(idx, "Comms")
runtimeVar = comms.add_variable(idx, "runtime", -1.0)
runtimeVar.set_writable(False) #Readonly by clients

readyVar = comms.add_variable(idx, "ready", False)
readyVar.set_writable(True) #Read/write by clients

server.start()

#Main loop for server. Preferably this would be in some sort of update function in a real program.
try:
    while True:
        runtimeVar.write_value(runtimeVar.get_value() + 0.1)
        print(f"Runtime: {runtimeVar.read_value()}")

        if(readyVar.get_value()):
            readyVar.write_value(False)
            print("Executing next move!")

        time.sleep(0.1)
finally:
    print("Server stopping. Intentional?")
    server.stop()
