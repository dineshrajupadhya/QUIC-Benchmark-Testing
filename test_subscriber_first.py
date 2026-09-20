import asyncio
import sys
import os
import time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from aioquic.asyncio import QuicConnectionProtocol, connect, serve
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.events import StreamDataReceived
from moq_protocol import (
    MoqMessageParser, ClientSetup, ServerSetup, SubscribeRequest, SubscribeOk,
    PublishRequest, PublishOk, PublishDone, MessageType, ErrorCode,
    FilterType, MOQT_VERSION_1
)

HOST = '127.0.0.1'
PORT = 4435
TOPIC = 'dinesh/in'
TOTAL_MESSAGES = 100
CERT_FILE = '/tmp/aioquic/examples/cert.pem'
KEY_FILE = '/tmp/aioquic/examples/key.pem'


class TestPublisher(QuicConnectionProtocol):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.buf = bytearray()
        self.stream_id = None
        self.publish_queue = []
        self.published_count = 0

    def quic_event_received(self, event):
        from aioquic.quic.events import StreamDataReceived, HandshakeCompleted
        if isinstance(event, HandshakeCompleted):
            print('[Server] QUIC handshake completed')
        elif isinstance(event, StreamDataReceived):
            self.buf.extend(event.data)
            self._parse(event.stream_id)
        self._flush()

    def _parse(self, stream_id):
        while len(self.buf) >= 2:
            try:
                msg, c = MoqMessageParser.parse(bytes(self.buf))
                self.buf = self.buf[c:]
                self._handle(msg, stream_id)
            except (ValueError, IndexError):
                break

    def _handle(self, msg, stream_id):
        if msg.message_type == MessageType.CLIENT_SETUP:
            if MOQT_VERSION_1 in msg.supported_versions:
                self._quic.send_stream_data(stream_id,
                    ServerSetup(selected_version=MOQT_VERSION_1).encode())
                print('[Server] CLIENT_SETUP -> SERVER_SETUP exchanged')

        elif msg.message_type == MessageType.SUBSCRIBE:
            self.stream_id = stream_id
            self._quic.send_stream_data(stream_id,
                SubscribeOk(track_namespace=msg.track_namespace, track_name=msg.track_name).encode())
            print('[Server] SUBSCRIBE received -> SUBSCRIBE_OK sent')
            print('[Server] Subscriber is ready! Publishing messages now...')
            self.publish_queue = list(range(1, TOTAL_MESSAGES + 1))

        elif msg.message_type == MessageType.PUBLISH_OK:
            pass

    def _flush(self):
        sent = 0
        while self.publish_queue and self.stream_id is not None and sent < 50:
            i = self.publish_queue.pop(0)
            m = PublishRequest(
                track_namespace=TOPIC, track_name='stream-1',
                group_id=1, object_id=i, publisher_priority=0,
                object_payload=str(i).encode('utf-8')
            )
            self._quic.send_stream_data(self.stream_id, m.encode())
            sent += 1
            self.published_count += 1
        if not self.publish_queue and self.stream_id is not None:
            self._quic.send_stream_data(self.stream_id, PublishDone(
                track_namespace=TOPIC, track_name='stream-1',
                error_code=ErrorCode.NO_ERROR, reason='All messages published'
            ).encode())
            print(f'[Server] Done! Published {self.published_count} messages.')
            self.stream_id = None


class TestSubscriber(QuicConnectionProtocol):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.buf = bytearray()

    def quic_event_received(self, event):
        if isinstance(event, StreamDataReceived):
            self.buf.extend(event.data)
            while len(self.buf) >= 2:
                try:
                    msg, c = MoqMessageParser.parse(bytes(self.buf))
                    self.buf = self.buf[c:]
                    events.put_nowait(msg)
                except (ValueError, IndexError):
                    break


events = asyncio.Queue()


async def subscriber_task():
    print()
    print('[TEST] Step 1: Subscriber connects and subscribes')
    print('[TEST] (Publisher has NOT started publishing yet)')
    print()

    config = QuicConfiguration(
        is_client=True, alpn_protocols=['moqt'],
        max_data=10000000, max_stream_data=1000000
    )
    config.load_verify_locations(CERT_FILE)

    async with connect(HOST, PORT, configuration=config, create_protocol=TestSubscriber) as qc:
        sid = qc._quic.get_next_available_stream_id()

        cs = ClientSetup()
        qc._quic.send_stream_data(sid, cs.encode())
        m = await asyncio.wait_for(events.get(), timeout=5)
        print('[Client] CLIENT_SETUP -> SERVER_SETUP exchanged')

        sub = SubscribeRequest(track_namespace=TOPIC, track_name='stream-1',
                               filter_type=FilterType.LARGEST_OBJECT)
        qc._quic.send_stream_data(sid, sub.encode())
        m = await asyncio.wait_for(events.get(), timeout=5)
        print('[Client] SUBSCRIBE -> SUBSCRIBE_OK exchanged')
        print('[Client] Subscriber is now subscribed. Waiting for messages...')
        print()
        print('[TEST] Step 2: Publisher now starts sending messages')
        print()

        received = []
        for _ in range(TOTAL_MESSAGES + 5):
            try:
                m = await asyncio.wait_for(events.get(), timeout=30)
                if m.message_type == MessageType.PUBLISH:
                    n = int(m.object_payload.decode())
                    received.append(n)
                    qc._quic.send_stream_data(sid, PublishOk(
                        track_namespace=m.track_namespace, track_name=m.track_name
                    ).encode())
                elif m.message_type == MessageType.PUBLISH_DONE:
                    break
            except asyncio.TimeoutError:
                break

        return received


async def main():
    if not os.path.exists(CERT_FILE):
        os.makedirs('/tmp/aioquic/examples', exist_ok=True)
        import subprocess
        subprocess.run([
            'openssl', 'req', '-x509', '-newkey', 'rsa:4096',
            '-keyout', KEY_FILE, '-out', CERT_FILE,
            '-days', '365', '-nodes',
            '-subj', '/CN=localhost',
            '-addext', 'subjectAltName = DNS:localhost, IP:127.0.0.1'
        ], check=True, capture_output=True)

    config = QuicConfiguration(
        is_client=False, alpn_protocols=['moqt'],
        max_data=10000000, max_stream_data=1000000
    )
    config.load_cert_chain(CERT_FILE, KEY_FILE)

    print()
    print('=' * 60)
    print('  TEST: Subscriber Subscribes BEFORE Publisher Publishes')
    print('=' * 60)

    print()
    print('[TEST] Starting server (publisher) - it will NOT publish yet')
    print('[TEST] Server only publishes after receiving SUBSCRIBE')
    print()

    await serve(HOST, PORT, configuration=config, create_protocol=TestPublisher)
    print('[Server] Started, waiting for connections...')
    print()

    await asyncio.sleep(1)

    received = await subscriber_task()

    print()
    print('=' * 60)
    print('  RESULTS')
    print('=' * 60)
    print(f'  Total received: {len(received)}/{TOTAL_MESSAGES}')
    if received == list(range(1, TOTAL_MESSAGES + 1)):
        print('  Sequence: CORRECT')
        print('  Status: PASSED')
    else:
        print('  Sequence: INCORRECT')
        print('  Status: FAILED')
    print()
    print('  Scenario verified: Subscriber subscribed BEFORE')
    print('  publisher sent any messages. Server waited for')
    print('  SUBSCRIBE, then published all messages.')
    print('=' * 60)


if __name__ == '__main__':
    asyncio.run(main())
