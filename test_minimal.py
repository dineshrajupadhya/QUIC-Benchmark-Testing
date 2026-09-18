import asyncio
import sys
sys.path.insert(0, '/home/dinesh_raj_upadhya/QUIC-Benchmark-Testing')
from aioquic.asyncio import QuicConnectionProtocol, serve, connect
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.events import StreamDataReceived

results = []

class ServerP(QuicConnectionProtocol):
    def quic_event_received(self, event):
        if isinstance(event, StreamDataReceived):
            print(f'Server got: {event.data}')
            self._quic.send_stream_data(event.stream_id, b'REPLY')

class ClientP(QuicConnectionProtocol):
    def quic_event_received(self, event):
        if isinstance(event, StreamDataReceived):
            print(f'Client got: {event.data}')
            results.append(event.data)

async def main():
    cert = '/tmp/aioquic/examples/cert.pem'
    key = '/tmp/aioquic/examples/key.pem'
    sc = QuicConfiguration(is_client=False, alpn_protocols=['t'])
    sc.load_cert_chain(cert, key)
    await serve('127.0.0.1', 4435, configuration=sc, create_protocol=ServerP)
    await asyncio.sleep(0.5)
    cc = QuicConfiguration(is_client=True, alpn_protocols=['t'])
    cc.load_verify_locations(cert)
    async with connect('127.0.0.1', 4435, configuration=cc, create_protocol=ClientP) as qc:
        sid = qc._quic.get_next_available_stream_id()
        qc._quic.send_stream_data(sid, b'PING')
        await asyncio.sleep(1)
        print(f'Results: {results}')

asyncio.run(main())
