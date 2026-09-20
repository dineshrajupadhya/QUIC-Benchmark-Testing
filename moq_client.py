import asyncio
import sys
import os
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
    if not os.path.exists(CERT_FILE):
        print('[Client] Certificate not found! Start server first.')
        return

    config = QuicConfiguration(
        is_client=True, alpn_protocols=['moqt'],
        max_data=10000000, max_stream_data=1000000
    )
    config.load_verify_locations(CERT_FILE)

    print()
    print('=' * 60)
    print('  MoQ Transport Subscriber Client')
    print('  Based on draft-ietf-moq-transport-21')
    print('=' * 60)
    print()
    print('  Scenario: Subscriber connects BEFORE publisher publishes')
    print('  Subscriber subscribes first, then receives all messages')
    print('=' * 60)
    print()
    print(f'[Client] Connecting to {HOST}:{PORT}...')

    async with connect(HOST, PORT, configuration=config, create_protocol=MoQClient) as qc:
        print('[Client] Connected')
        sid = qc._quic.get_next_available_stream_id()

        cs = ClientSetup()
        qc._quic.send_stream_data(sid, cs.encode())
        print('[Client] CLIENT_SETUP sent')

        m = await asyncio.wait_for(events.get(), timeout=5)
        print('[Client] SERVER_SETUP received')

        sub = SubscribeRequest(track_namespace=TOPIC, track_name='stream-1',
                               filter_type=FilterType.LARGEST_OBJECT)
        qc._quic.send_stream_data(sid, sub.encode())
        print('[Client] SUBSCRIBE sent (subscriber is now ready)')

        m = await asyncio.wait_for(events.get(), timeout=5)
        print('[Client] SUBSCRIBE_OK received')
        print('[Client] Subscriber is subscribed. Waiting for publisher to publish...')
        print()

        received = []
        first = last = None
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

        print()
        print('=' * 60)
        print('  RESULTS')
        print('=' * 60)
        print(f'  Total received: {len(received)}')
        print(f'  First: {first}')
        print(f'  Last: {last}')
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
        print('     |--- CLIENT_SETUP -->|')
        print('     |<-- SERVER_SETUP ---|')
        print('     |--- SUBSCRIBE ----->|')
        print('     |<-- SUBSCRIBE_OK ---|')
        print('     |                    | (publisher starts sending)')
        print('     |<-- PUBLISH (x10000)|')
        print('     |--- PUBLISH_OK ---> |')
        print('     |<-- PUBLISH_DONE ---|')
        print('=' * 60)


if __name__ == '__main__':
    asyncio.run(main())
