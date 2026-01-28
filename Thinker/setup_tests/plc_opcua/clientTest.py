#USE PYTHON 3.13.11
#Client with PLC as server

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
        nsidx = 0 #await client.get_namespace_index(namespace)
        print(f"Namespace Index for '{namespace}':{nsidx}")

        testInt = client.get_node("ns=5;b=AQAAAKbhKnGK9zM6uvotdobvYEeM925gjPA0VYrgNXmc7yFghvEfJek=")
        print(f"testInt: {await testInt.read_value()}")
        
        while True:
            i = await testInt.read_value()
            print(f"testInt: {i}")
            await testInt.write_value(i + 1)
            await asyncio.sleep(0.1)
            

if __name__ == "__main__":
    asyncio.run(main())