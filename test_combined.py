import asyncio
import sys
import os
sys.path.insert(0, '/home/dinesh_raj_upadhya/QUIC-Benchmark-Testing')

from aioquic.asyncio import QuicConnectionProtocol, serve, connect
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.events import StreamDataReceived, HandshakeCompleted
from moq_protocol import (
    MoqMessageParser, ClientSetup, ServerSetup,
    SubscribeRequest, SubscribeOk, PublishRequest, PublishOk, PublishDone,
    MessageType, ErrorCode, FilterType, MOQT_VERSION_1
)

HOST = '127.0.0.1'
PORT = 4434
TOPIC = 'dinesh/in'
TOTAL_MESSAGES = 100

results = []
events_q = asyncio.Queue()

class Server(QuicConnectionProtocol):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.buf = bytearray()
        self.subs = {}
        self.started = False

    def quic_event_received(self, event):
        if isinstance(event, HandshakeCompleted):
            print('[Server] Handshake done')
        elif isinstance(event, StreamDataReceived):
            self.buf.extend(event.data)
            while self.buf:
                try:
                    msg, c = MoqMessageParser.parse(bytes(self.buf))
                    self.buf = self.buf[c:]
                    if msg.message_type == MessageType.CLIENT_SETUP:
                        print('[Server] CLIENT_SETUP')
                        self._quic.send_stream_data(event.stream_id,
                            ServerSetup(selected_version=MOQT_VERSION_1).encode())
                        print('[Server] SERVER_SETUP sent')
                    elif msg.message_type == MessageType.SUBSCRIBE:
                        print(f'[Server] SUBSCRIBE {msg.track_namespace}/{msg.track_name}')
                        self.subs[msg.track_name] = event.stream_id
                        self._quic.send_stream_data(event.stream_id,
                            SubscribeOk(track_namespace=msg.track_namespace, track_name=msg.track_name).encode())
                        print('[Server] SUBSCRIBE_OK sent')
                        if not self.started:
                            asyncio.create_task(self.publish(msg.track_name))
                    elif msg.message_type == MessageType.PUBLISH_OK:
                        pass
                    else:
                        break
                except ValueError:
                    break

    async def publish(self, tn):
        self.started = True
        print(f'\n[Server] Publishing 1-{TOTAL_MESSAGES} on {TOPIC}')
        print('-' * 50)
        await asyncio.sleep(0.1)
        for i in range(1, TOTAL_MESSAGES + 1):
            if tn not in self.subs:
                break
            m = PublishRequest(track_namespace=TOPIC, track_name=tn,
                               group_id=1, object_id=i, publisher_priority=0,
                               object_payload=str(i).encode('utf-8'))
            self._quic.send_stream_data(self.subs[tn], m.encode())
            if i % 10 == 0 or i == 1 or i == TOTAL_MESSAGES:
                print(f'[Server] Sent: {i}')
            await asyncio.sleep(0.01)
        d = PublishDone(track_namespace=TOPIC, track_name=tn,
                        error_code=ErrorCode.NO_ERROR, reason='Done')
        self._quic.send_stream_data(self.subs[tn], d.encode())
        print('-' * 50)
        print(f'[Server] Done!')

class Client(QuicConnectionProtocol):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.buf = bytearray()

    def quic_event_received(self, event):
        if isinstance(event, HandshakeCompleted):
            pass
        elif isinstance(event, StreamDataReceived):
            self.buf.extend(event.data)
            while self.buf:
                try:
                    msg, c = MoqMessageParser.parse(bytes(self.buf))
                    self.buf = self.buf[c:]
                    events_q.put_nowait(msg)
                except ValueError:
                    break

async def main():
    sc = QuicConfiguration(is_client=False, alpn_protocols=['moqt'],
                           max_data=10000000, max_stream_data=1000000)
    sc.load_cert_chain('/tmp/aioquic/examples/cert.pem', '/tmp/aioquic/examples/key.pem')
    print('\n' + '=' * 60)
    print('  MoQ Protocol Test')
    print('=' * 60)
    print(f'  Topic: {TOPIC} | Messages: 1-{TOTAL_MESSAGES}')
    print(f'  ALPN: moqt | Version: 0x{MOQT_VERSION_1:08x}')
    print('=' * 60 + '\n')
    await serve(HOST, PORT, configuration=sc, create_protocol=Server)
    print('[Server] Listening on 127.0.0.1:4434\n')
    await asyncio.sleep(1)
    cc = QuicConfiguration(is_client=True, alpn_protocols=['moqt'],
                           max_data=10000000, max_stream_data=1000000)
    cc.load_verify_locations('/tmp/aioquic/examples/cert.pem')
    async with connect(HOST, PORT, configuration=cc, create_protocol=Client) as qc:
        print('[Client] Connected')
        sid = qc._quic.get_next_available_stream_id()
        qc._quic.send_stream_data(sid, ClientSetup(number_of_routes=0, supported_versions=[MOQT_VERSION_1]).encode())
        print('[Client] CLIENT_SETUP sent')
        m = await asyncio.wait_for(events_q.get(), timeout=5)
        print('[Client] SERVER_SETUP received')
        qc._quic.send_stream_data(sid, SubscribeRequest(track_namespace=TOPIC, track_name='stream-1', filter_type=FilterType.LARGEST_OBJECT).encode())
        print('[Client] SUBSCRIBE sent')
        m = await asyncio.wait_for(events_q.get(), timeout=5)
        print('[Client] SUBSCRIBE_OK received')
        print('\n[Client] Receiving messages...\n')
        first = last = None
        for _ in range(TOTAL_MESSAGES + 5):
            try:
                m = await asyncio.wait_for(events_q.get(), timeout=10)
                if m.message_type == MessageType.PUBLISH:
                    n = int(m.object_payload.decode())
                    results.append(n)
                    if first is None: first = n
                    last = n
                    if n % 10 == 0 or n == 1 or n == TOTAL_MESSAGES:
                        print(f'[Client] Received: {n}')
                elif m.message_type == MessageType.PUBLISH_DONE:
                    print(f'[Client] PUBLISH_DONE: {m.reason}')
                    break
            except asyncio.TimeoutError:
                print(f'[Client] Timeout at {len(results)} msgs')
                break
        print('\n' + '=' * 60)
        print('  RESULTS')
        print('=' * 60)
        print(f'  Total: {len(results)} | First: {first} | Last: {last}')
        if results == list(range(1, TOTAL_MESSAGES + 1)):
            print('  Sequence: CORRECT')
        else:
            print(f'  Sequence: {len(results)}/{TOTAL_MESSAGES}')
        print('=' * 60)

if __name__ == '__main__':
    asyncio.run(main())
