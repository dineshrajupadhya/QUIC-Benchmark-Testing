import asyncio
from aioquic.asyncio import connect
from aioquic.quic.configuration import QuicConfiguration

async def main():
    config = QuicConfiguration(is_client=True)
    config.load_verify_locations("/tmp/aioquic/examples/cert.pem")
    async with connect("127.0.0.1", 4433, configuration=config) as conn:
        print("Connected to server via QUIC!")
        print("Interoperability test PASSED!")

asyncio.run(main())
