import asyncio
import time
from aioquic.asyncio import connect, QuicConnectionProtocol, serve
from aioquic.quic.configuration import QuicConfiguration

results = []

class ServerProtocol(QuicConnectionProtocol):
    def quic_event_received(self, event):
        pass

async def run_server():
    config = QuicConfiguration(is_client=False)
    config.load_cert_chain("/tmp/aioquic/examples/cert.pem", "/tmp/aioquic/examples/key.pem")
    await serve("127.0.0.1", 4433, configuration=config, create_protocol=ServerProtocol)

async def run_client():
    await asyncio.sleep(1)
    config = QuicConfiguration(is_client=True)
    config.load_verify_locations("/tmp/aioquic/examples/cert.pem")
    
    times = []
    for i in range(10):
        start = time.time()
        async with connect("127.0.0.1", 4433, configuration=config) as conn:
            pass
        elapsed = (time.time() - start) * 1000
        times.append(elapsed)
    
    print("=== QUIC Benchmark Results ===")
    print(f"Connections: {len(times)}")
    print(f"Average latency: {sum(times)/len(times):.2f} ms")
    print(f"Min latency: {min(times):.2f} ms")
    print(f"Max latency: {max(times):.2f} ms")

async def main():
    await asyncio.gather(run_server(), run_client())

asyncio.run(main())
