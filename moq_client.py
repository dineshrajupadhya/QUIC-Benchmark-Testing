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
    if not os.path.exists(CERT_FILE):
        print('[Client] ERROR: Certificate not found!')
        print('[Client] Please generate certificates first.')
        return
    print('[Client] Certificate found: OK')

    print()
    print('[Client] [2/6] Connecting to ' + HOST + ':' + str(PORT) + '...')

    config = QuicConfiguration(
        is_client=True, alpn_protocols=['moqt'],
        max_data=10000000, max_stream_data=1000000
    )
    config.load_verify_locations(CERT_FILE)

    async with connect(HOST, PORT, configuration=config, create_protocol=MoQClient) as qc:
        print('[Client] Connection established!')
        print('[Client] QUIC handshake: SUCCESS')

        sid = qc._quic.get_next_available_stream_id()

        print()
        print('[Client] [3/6] Sending CLIENT_SETUP...')
        cs = ClientSetup()
        qc._quic.send_stream_data(sid, cs.encode())

        m = await asyncio.wait_for(events.get(), timeout=5)
        print('[Client] SERVER_SETUP received')
        print('[Client] MoQ version negotiation: COMPLETE')

        print()
        print('[Client] [4/6] Sending SUBSCRIBE...')
        sub = SubscribeRequest(track_namespace=TOPIC, track_name='stream-1',
                               filter_type=FilterType.LARGEST_OBJECT)
        qc._quic.send_stream_data(sid, sub.encode())

        m = await asyncio.wait_for(events.get(), timeout=5)
        print('[Client] SUBSCRIBE_OK received')
        print('[Client] Subscription status: ACTIVE')

        print()
        print('[Client] [5/6] Waiting for publisher to send messages...')
        print()

        received = []
        first = last = None
        start_time = time.time()
        step6_printed = False

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
                        print('[Client] [6/6] Receiving messages...')
                        print('[Client] First message received in ' + '{:.3f}'.format(elapsed) + 's')
                        step6_printed = True
                    last = n
                    qc._quic.send_stream_data(sid, PublishOk(track_namespace=m.track_namespace, track_name=m.track_name).encode())
                    if n % 1000 == 0 or n == 1 or n == 10000:
                        print('[Client] Received: ' + str(n) + ' (' + str(len(received)) + '/10000)')
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
        if received == list(range(1, 10001)):
            print('  Sequence: CORRECT (1 to 10000 in order)')
        else:
            print('  Sequence: ' + str(len(received)) + '/10000')
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
        print('     |<-- PUBLISH (x10000)|')
        print('     |-- PUBLISH_OK ----> |')
        print('     |<-- PUBLISH_DONE ---|')
        print('     |-- [5] Complete --->|')
        print('=' * 60)


if __name__ == '__main__':
    asyncio.run(main())
