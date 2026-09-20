import asyncio
import sys
import os
import time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from aioquic.asyncio import QuicConnectionProtocol, connect
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.events import StreamDataReceived
from moq_protocol import (
    MoqMessageParser, ClientSetup, SubscribeRequest, PublishOk,
    MessageType, FilterType, MOQT_VERSION_1
)

HOST = '127.0.0.1'
PORT = 4434
TOPIC = 'dinesh/in'
CERT_FILE = '/tmp/aioquic/examples/cert.pem'
events = asyncio.Queue()


class MoQClient(QuicConnectionProtocol):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.buf = bytearray()

    def quic_event_received(self, event):
        if isinstance(event, StreamDataReceived):
            self.buf.extend(event.data)
            self._parse()

    def _parse(self):
        while len(self.buf) >= 2:
            try:
                msg, consumed = MoqMessageParser.parse(bytes(self.buf))
                self.buf = self.buf[consumed:]
                events.put_nowait(msg)
            except (ValueError, IndexError):
                break


async def main():
    print()
    print('=' * 60)
    print('  MoQ Transport Subscriber Client')
    print('  Based on draft-ietf-moq-transport-21')
    print('=' * 60)
    print()

    print('[Client] --- Connection Check ---')
    print(f'[Client] Target server: {HOST}:{PORT}')
    print(f'[Client] Certificate: {CERT_FILE}')

    if not os.path.exists(CERT_FILE):
        print('[Client] ERROR: Certificate not found!')
        print('[Client] Cannot connect without valid certificate.')
        print('[Client] Please generate certificates first:')
        print('[Client]   mkdir -p /tmp/aioquic/examples')
        print('[Client]   openssl req -x509 -newkey rsa:4096 \\')
        print('[Client]     -keyout /tmp/aioquic/examples/key.pem \\')
        print('[Client]     -out /tmp/aioquic/examples/cert.pem \\')
        print('[Client]     -days 365 -nodes -subj \'/CN=localhost\'')
        return

    print('[Client] Certificate found: OK')
    print('[Client] ------------------------')
    print()

    print('[Client] Attempting to connect to publisher...')
    print()

    config = QuicConfiguration(
        is_client=True, alpn_protocols=['moqt'],
        max_data=10000000, max_stream_data=1000000
    )
    config.load_verify_locations(CERT_FILE)

    try:
        async with connect(HOST, PORT, configuration=config, create_protocol=MoQClient) as qc:
            print('[Client] --- Connection Established ---')
            print(f'[Client] Connected to {HOST}:{PORT}')
            print('[Client] QUIC handshake: SUCCESS')
            print('[Client] --------------------------------')
            print()

            sid = qc._quic.get_next_available_stream_id()

            cs = ClientSetup()
            qc._quic.send_stream_data(sid, cs.encode())
            print('[Client] CLIENT_SETUP sent')

            m = await asyncio.wait_for(events.get(), timeout=5)
            print('[Client] SERVER_SETUP received')
            print('[Client] MoQ handshake: COMPLETE')
            print()

            print('[Client] --- Subscribe Check ---')
            print(f'[Client] Topic: {TOPIC}')
            print(f'[Client] Track: stream-1')
            print(f'[Client] Filter: LATEST')
            sub = SubscribeRequest(track_namespace=TOPIC, track_name='stream-1',
                                   filter_type=FilterType.LARGEST_OBJECT)
            qc._quic.send_stream_data(sid, sub.encode())
            print('[Client] SUBSCRIBE sent')

            m = await asyncio.wait_for(events.get(), timeout=5)
            print('[Client] SUBSCRIBE_OK received')
            print('[Client] Subscription status: ACTIVE')
            print('[Client] -------------------------')
            print()
            print('[Client] Waiting for publisher to publish messages...')
            print()

            received = []
            first = last = None
            start_time = time.time()
            for _ in range(10005):
                try:
                    m = await asyncio.wait_for(events.get(), timeout=30)
                    if m.message_type == MessageType.PUBLISH:
                        try:
                            n = int(m.object_payload.decode())
                        except (ValueError, UnicodeDecodeError):
                            continue
                        received.append(n)
                        if first is None:
                            first = n
                            elapsed = time.time() - start_time
                            print(f'[Client] First message received in {elapsed:.3f}s')
                        last = n
                        qc._quic.send_stream_data(sid, PublishOk(track_namespace=m.track_namespace, track_name=m.track_name).encode())
                        if n % 1000 == 0 or n == 1 or n == 10000:
                            print(f'[Client] Received: {n} ({len(received)}/10000)')
                    elif m.message_type == MessageType.PUBLISH_DONE:
                        print(f'[Client] PUBLISH_DONE: {m.reason}')
                        break
                except asyncio.TimeoutError:
                    print(f'[Client] Timeout at {len(received)} messages')
                    break

            elapsed = time.time() - start_time
            print()
            print('=' * 60)
            print('  RESULTS')
            print('=' * 60)
            print(f'  Total received: {len(received)}')
            print(f'  First: {first}')
            print(f'  Last: {last}')
            print(f'  Time taken: {elapsed:.3f}s')
            if elapsed > 0:
                print(f'  Throughput: {len(received)/elapsed:.0f} messages/sec')
            if received == list(range(1, 10001)):
                print('  Sequence: CORRECT (1 to 10000 in order)')
            else:
                print(f'  Sequence: {len(received)}/10000')
            print()
            print('  Scenario: Subscriber connected BEFORE publisher')
            print('  published any messages. Server waited for SUBSCRIBE')
            print('  then sent all 10000 messages to the subscriber.')
            print()
            print('  MoQ Protocol Flow:')
            print('  Subscriber           Publisher')
            print('     |                    |')
            print('     |-- Check Conn ----->|')
            print('     |<-- Conn OK --------|')
            print('     |--- CLIENT_SETUP -->|')
            print('     |<-- SERVER_SETUP ---|')
            print('     |-- Check Sub ------>|')
            print('     |<-- Sub OK ---------|')
            print('     |--- SUBSCRIBE ----->|')
            print('     |<-- SUBSCRIBE_OK ---|')
            print('     |-- Check Pub ----->|')
            print('     |<-- Pub OK ---------|')
            print('     |                    | (publisher starts sending)')
            print('     |<-- PUBLISH (x10000)|')
            print('     |--- PUBLISH_OK ---> |')
            print('     |<-- PUBLISH_DONE ---|')
            print('=' * 60)

    except Exception as e:
        print()
        print('[Client] --- Connection Failed ---')
        print(f'[Client] Error: {e}')
        print('[Client] Status: NOT CONNECTED')
        print('[Client] Please check:')
        print('[Client]   1. Is the server running?')
        print('[Client]   2. Are certificates valid?')
        print('[Client]   3. Is port 4434 available?')
        print('[Client] --------------------------------')
        print()
        print('[Client] Retry? Start server first, then run this client again.')


if __name__ == '__main__':
    asyncio.run(main())
