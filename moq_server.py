import asyncio
import sys
import os
import time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from aioquic.asyncio import QuicConnectionProtocol, serve
from aioquic.quic.configuration import QuicConfiguration
from moq_protocol import (
    MoqMessageParser, ServerSetup, SubscribeOk, PublishRequest, PublishDone,
    MessageType, ErrorCode, MOQT_VERSION_1
)

HOST = '0.0.0.0'
PORT = 4434
TOPIC = 'dinesh/in'
TOTAL_MESSAGES = 10000
BATCH_SIZE = 50
CERT_FILE = '/tmp/aioquic/examples/cert.pem'
KEY_FILE = '/tmp/aioquic/examples/key.pem'


class MoQPublisher(QuicConnectionProtocol):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.buf = bytearray()
        self.subs = {}
        self.publish_queue = []
        self.stream_id = None
        self.published_count = 0
        self.connected = False
        self.subscribed = False

    def quic_event_received(self, event):
        from aioquic.quic.events import StreamDataReceived, HandshakeCompleted
        if isinstance(event, HandshakeCompleted):
            self.connected = True
            print('[Server] [1/6] QUIC handshake completed')
            print('[Server] Connection status: CONNECTED')
            print()
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
                print()

        elif msg.message_type == MessageType.SUBSCRIBE:
            ns = msg.track_namespace
            tn = msg.track_name
            self.subs[tn] = stream_id
            self.stream_id = stream_id
            self.subscribed = True

            self._quic.send_stream_data(stream_id,
                SubscribeOk(track_namespace=ns, track_name=tn).encode())
            print('[Server] [4/6] SUBSCRIBE received: ' + ns + '/' + tn)
            print('[Server] [5/6] SUBSCRIBE_OK sent')
            print('[Server] Active subscribers: ' + str(len(self.subs)))
            print('[Server] Subscriber verified!')
            print()
            print('[Server] Queuing ' + str(TOTAL_MESSAGES) + ' messages...')
            self.publish_queue = list(range(1, TOTAL_MESSAGES + 1))
            print('[Server] ' + str(len(self.publish_queue)) + ' messages ready')
            print('[Server] [6/6] Publishing begins!')
            print()

        elif msg.message_type == MessageType.PUBLISH_OK:
            pass

    def _flush(self):
        sent = 0
        while self.publish_queue and self.stream_id is not None and sent < BATCH_SIZE:
            i = self.publish_queue.pop(0)
            m = PublishRequest(
                track_namespace=TOPIC, track_name='stream-1',
                group_id=1, object_id=i, publisher_priority=0,
                object_payload=str(i).encode('utf-8')
            )
            self._quic.send_stream_data(self.stream_id, m.encode())
            sent += 1
            self.published_count += 1
            if i % 1000 == 0 or i == 1 or i == TOTAL_MESSAGES:
                print('[Server] Published: ' + str(i) + ' (' + str(self.published_count) + '/' + str(TOTAL_MESSAGES) + ')')

        if not self.publish_queue and self.stream_id is not None:
            d = PublishDone(
                track_namespace=TOPIC, track_name='stream-1',
                error_code=ErrorCode.NO_ERROR, reason='All messages published'
            )
            self._quic.send_stream_data(self.stream_id, d.encode())
            print()
            print('=' * 60)
            print('[Server] Done! Published ' + str(self.published_count) + ' messages.')
            print('[Server] PUBLISH_DONE sent to subscriber')
            print('=' * 60)
            self.stream_id = None


async def main():
    if not os.path.exists(CERT_FILE) or not os.path.exists(KEY_FILE):
        os.makedirs('/tmp/aioquic/examples', exist_ok=True)
        import subprocess
        subprocess.run([
            'openssl', 'req', '-x509', '-newkey', 'rsa:4096',
            '-keyout', KEY_FILE, '-out', CERT_FILE,
            '-days', '365', '-nodes',
            '-subj', '/CN=localhost',
            '-addext', 'subjectAltName = DNS:localhost, IP:127.0.0.1'
        ], check=True, capture_output=True)
        print('[Server] Certificates generated!')

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

    await serve(HOST, PORT, configuration=config, create_protocol=MoQPublisher)
    print('[Server] Started on ' + HOST + ':' + str(PORT))
    print('[Server] Waiting for subscriber to connect...')
    print()

    try:
        await asyncio.Future()
    except KeyboardInterrupt:
        print('\n[Server] Shutting down...')


if __name__ == '__main__':
    asyncio.run(main())
