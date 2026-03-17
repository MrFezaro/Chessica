#USE PYTHON 3.13.11
#Client with virtual PLC as server

import asyncio
from asyncua import Client

url = "opc.tcp://localhost:4840"

async def main():
    print(f"Connecting to {url} ...")
    async with Client(url=url) as client:
        nodeId = "ns=5;b=AQAAAKbhKnGK9zM6uvotdobvYEeM925gjPA0VYrgNXmc7yFghvEfJek="
        testInt = client.get_node(nodeId)
        print(f"testInt: {await testInt.read_value()}")
        
        while True:
            i = await testInt.read_value()
            print(f"testInt: {i}")
            await testInt.write_value(i + 1)
            await asyncio.sleep(0.1)
            

if __name__ == "__main__":
    asyncio.run(main())