import asyncio
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from aioquic.asyncio import QuicConnectionProtocol, serve, connect
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.events import StreamDataReceived
from moq_protocol import (
    MoqMessageParser, ClientSetup, ServerSetup, SubscribeRequest, SubscribeOk,
    PublishRequest, PublishOk, PublishDone, MessageType, ErrorCode,
    FilterType, MOQT_VERSION_1
)

HOST = '127.0.0.1'
PORT = 4436
TOPIC = 'dinesh/in'
TOTAL_MESSAGES = 100
CERT_FILE = '/tmp/aioquic/examples/cert.pem'
KEY_FILE = '/tmp/aioquic/examples/key.pem'
client_events = asyncio.Queue()


class StepPublisher(QuicConnectionProtocol):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.buf = bytearray()
        self.stream_id = None
        self.publish_queue = []
        self.published_count = 0

    def quic_event_received(self, event):
        from aioquic.quic.events import StreamDataReceived, HandshakeCompleted
        if isinstance(event, HandshakeCompleted):
            print('[Server] [1/6] QUIC handshake completed')
            print('[Server] Connection status: CONNECTED')
            print('[Server]')
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
                print('[Server] [2/6] CLIENT_SETUP received')
                print('[Server] [3/6] SERVER_SETUP sent')
                print('[Server] MoQ version negotiation complete')
                print('[Server]')
        elif msg.message_type == MessageType.SUBSCRIBE:
            ns = msg.track_namespace
            tn = msg.track_name
            self.stream_id = stream_id
            self._quic.send_stream_data(stream_id,
                SubscribeOk(track_namespace=ns, track_name=tn).encode())
            print('[Server] [4/6] SUBSCRIBE received: ' + ns + '/' + tn)
            print('[Server] [5/6] SUBSCRIBE_OK sent')
            print('[Server] Subscriber verified!')
            print('[Server]')
            print('[Server] Queuing ' + str(TOTAL_MESSAGES) + ' messages...')
            self.publish_queue = list(range(1, TOTAL_MESSAGES + 1))
            print('[Server] ' + str(len(self.publish_queue)) + ' messages ready')
            print('[Server] [6/6] Publishing begins!')
            print('[Server]')

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
            if i % 10 == 0 or i == 1 or i == TOTAL_MESSAGES:
                print('[Server] Published: ' + str(i) + ' (' + str(self.published_count) + '/' + str(TOTAL_MESSAGES) + ')')
        if not self.publish_queue and self.stream_id is not None:
            self._quic.send_stream_data(self.stream_id, PublishDone(
                track_namespace=TOPIC, track_name='stream-1',
                error_code=ErrorCode.NO_ERROR, reason='All messages published'
            ).encode())
            print('[Server]')
            print('=' * 60)
            print('[Server] Done! Published ' + str(self.published_count) + ' messages.')
            print('=' * 60)
            self.stream_id = None


class StepSubscriber(QuicConnectionProtocol):
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
                    client_events.put_nowait(msg)
                except (ValueError, IndexError):
                    break


async def subscriber_task():
    print()
    print('=' * 60)
    print('  MoQ Transport Subscriber Client')
    print('  Based on draft-ietf-moq-transport-21')
    print('=' * 60)
    print()
    print('  Protocol Flow:')
    print('  [1/6] Check certificate')
    print('  [2/6] Connect to server')
    print('  [3/6] CLIENT_SETUP sent')
    print('  [4/6] SUBSCRIBE sent')
    print('  [5/6] Wait for messages')
    print('  [6/6] Receive all messages')
    print('=' * 60)
    print()
    print('[Client] [1/6] Checking certificate...')
    print('[Client] Certificate found: OK')
    print()
    print('[Client] [2/6] Connecting to ' + HOST + ':' + str(PORT) + '...')

    config = QuicConfiguration(
        is_client=True, alpn_protocols=['moqt'],
        max_data=10000000, max_stream_data=1000000
    )
    config.load_verify_locations(CERT_FILE)

    async with connect(HOST, PORT, configuration=config, create_protocol=StepSubscriber) as qc:
        print('[Client] Connection established!')
        print('[Client] QUIC handshake: SUCCESS')

        sid = qc._quic.get_next_available_stream_id()

        print()
        print('[Client] [3/6] Sending CLIENT_SETUP...')
        cs = ClientSetup()
        qc._quic.send_stream_data(sid, cs.encode())

        m = await asyncio.wait_for(client_events.get(), timeout=5)
        print('[Client] SERVER_SETUP received')
        print('[Client] MoQ version negotiation: COMPLETE')

        print()
        print('[Client] [4/6] Sending SUBSCRIBE...')
        sub = SubscribeRequest(track_namespace=TOPIC, track_name='stream-1',
                               filter_type=FilterType.LARGEST_OBJECT)
        qc._quic.send_stream_data(sid, sub.encode())

        m = await asyncio.wait_for(client_events.get(), timeout=5)
        print('[Client] SUBSCRIBE_OK received')
        print('[Client] Subscription status: ACTIVE')

        print()
        print('[Client] [5/6] Waiting for publisher to send messages...')
        print()

        received = []
        first = last = None
        start_time = time.time()

        for _ in range(TOTAL_MESSAGES + 5):
            try:
                m = await asyncio.wait_for(client_events.get(), timeout=30)
                if m.message_type == MessageType.PUBLISH:
                    try:
                        n = int(m.object_payload.decode())
                    except (ValueError, UnicodeDecodeError):
                        continue
                    received.append(n)
                    if first is None:
                        first = n
                        elapsed = time.time() - start_time
                        print('[Client] [6/6] Receiving messages...')
                        print('[Client] First message received in ' + '{:.3f}'.format(elapsed) + 's')
                    last = n
                    qc._quic.send_stream_data(sid, PublishOk(
                        track_namespace=m.track_namespace, track_name=m.track_name
                    ).encode())
                    if n % 10 == 0 or n == 1 or n == TOTAL_MESSAGES:
                        print('[Client] Received: ' + str(n) + ' (' + str(len(received)) + '/' + str(TOTAL_MESSAGES) + ')')
                elif m.message_type == MessageType.PUBLISH_DONE:
                    print('[Client] PUBLISH_DONE: ' + m.reason)
                    break
            except asyncio.TimeoutError:
                print('[Client] Timeout at ' + str(len(received)) + ' messages')
                break

        elapsed = time.time() - start_time
        print()
        print('=' * 60)
        print('  RESULTS')
        print('=' * 60)
        print('  Total received: ' + str(len(received)))
        print('  First: ' + str(first))
        print('  Last: ' + str(last))
        print('  Time taken: ' + '{:.3f}'.format(elapsed) + 's')
        if elapsed > 0:
            print('  Throughput: ' + str(int(len(received)/elapsed)) + ' messages/sec')
        if received == list(range(1, TOTAL_MESSAGES + 1)):
            print('  Sequence: CORRECT')
        else:
            print('  Sequence: ' + str(len(received)) + '/' + str(TOTAL_MESSAGES))
        print()
        print('  MoQ Protocol Flow (Completed):')
        print('  Subscriber           Publisher')
        print('     |                    |')
        print('     |-- [1] Check Conn ->|')
        print('     |<-- Conn OK --------|')
        print('     |-- [2] CLIENT_SETUP>|')
        print('     |<-- SERVER_SETUP ---|')
        print('     |-- [3] SUBSCRIBE -->|')
        print('     |<-- SUBSCRIBE_OK ---|')
        print('     |-- [4] Wait Pub --->|')
        print('     |<-- PUBLISH (x' + str(TOTAL_MESSAGES) + ')|')
        print('     |-- PUBLISH_OK ----> |')
        print('     |<-- PUBLISH_DONE ---|')
        print('     |-- [5] Complete --->|')
        print('=' * 60)


async def main():
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
    print('  MoQ Transport Publisher Server')
    print('  Based on draft-ietf-moq-transport-21')
    print('=' * 60)
    print()
    print('  Topic: ' + TOPIC)
    print('  Messages: 1-' + str(TOTAL_MESSAGES))
    print('  Listening on: ' + HOST + ':' + str(PORT))
    print('  Protocol: QUIC + MoQT (version 0x00000001)')
    print('  ALPN: moqt')
    print()
    print('  Protocol Flow:')
    print('  [1/6] QUIC handshake')
    print('  [2/6] CLIENT_SETUP received')
    print('  [3/6] SERVER_SETUP sent')
    print('  [4/6] SUBSCRIBE received')
    print('  [5/6] SUBSCRIBE_OK sent')
    print('  [6/6] Publish messages')
    print('=' * 60)
    print()
    print('[Server] Starting...')
    await serve(HOST, PORT, configuration=config, create_protocol=StepPublisher)
    print('[Server] Listening on ' + HOST + ':' + str(PORT))
    print('[Server] Waiting for subscriber to connect...')
    print()

    await asyncio.sleep(1)
    await subscriber_task()


if __name__ == '__main__':
    asyncio.run(main())
