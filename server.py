import asyncio
from aioquic.asyncio import QuicConnectionProtocol, serve
from aioquic.quic.configuration import QuicConfiguration

async def handle_stream(protocol):
    pass
config = QuicConfiguration(is_client=False)
config.load_cert_chain("/tmp/aioquic/examples/cert.pem", "/tmp/aioquic/examples/key.pem")

async def main():
    protocol = await serve("127.0.0.1", 4433, configuration=config, create_protocol=QuicConnectionProtocol)
    print("Server running on 127.0.0.1:4433")
    await asyncio.Future()

asyncio.run(main())
