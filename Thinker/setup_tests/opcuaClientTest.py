#Based off https://github.com/FreeOpcUa/opcua-asyncio/blob/master/examples/sync/client-minimal.py

import time
from asyncua.sync import Client

with Client("opc.tcp://localhost:4840/freeopcua/server/") as client:

    # Client has a few methods to get proxy to UA nodes that should always be in address space such as Root or Objects
    # Node objects have methods to read and write node attributes as well as browse or populate address space
    print("Children of root are: ", client.nodes.root.get_children())


    obj = client.nodes.root.get_child(["0:Objects", "2:MyObject"])
    print("obj: " + obj)

    runtime = client.nodes.root.get_child(["0:Objects", "2:Comms", "2:runtime"])
    ready = client.nodes.root.get_child(["0:Objects", "2:Comms", "2:ready"])
    print(f"runtime: {runtime.read_value()}")
    print(f"ready: {ready.read_value()}")
    
    try:
        while True:
            runtime.write_value(999999999.9) #This should fail
            inputStr = input("Ready for next move? ").lower()
            if(inputStr != "n" and len(inputStr) > 1 or inputStr == "y"):
                ready.write_value(True)
            
    finally:
        print("Disconnected. Intentional?")
        client.disconnect()
