import asyncio
import json
from aioquic.asyncio import connect
from aioquic.asyncio.protocol import QuicConnectionProtocol
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.events import QuicEvent, StreamDataReceived

class MoQClient(QuicConnectionProtocol):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.received = []
        self.buffer = ''

    def quic_event_received(self, event: QuicEvent):
        if isinstance(event, StreamDataReceived):
            self.buffer += event.data.decode()
            while '\n' in self.buffer:
                line, self.buffer = self.buffer.split('\n', 1)
                if line.strip():
                    try:
                        msg = json.loads(line.strip())
                        seq = msg.get('seq')
                        val = msg.get('val')
                        if seq is not None:
                            self.received.append(seq)
                            if len(self.received) <= 5 or len(self.received) % 1000 == 0 or len(self.received) == 10000:
                                print(f'[Client] Received: {val}')
                    except json.JSONDecodeError:
                        pass

async def main():
    config = QuicConfiguration(is_client=True)
    config.load_verify_locations('/tmp/aioquic/examples/cert.pem')

    print('=== MoQ Pub/Sub Client ===')
    print('Connecting to server...')

    async with connect('127.0.0.1', 4434, configuration=config, create_protocol=MoQClient) as conn:
        sub_msg = json.dumps({'type': 'subscribe', 'topic': 'dinesh/in'})
        stream_id = conn._quic.get_next_available_stream_id()
        conn._quic.send_stream_data(stream_id, sub_msg.encode() + b'\n')
        print('[Client] Subscribed to topic: dinesh/in')
        print('[Client] Waiting for messages...\n')
        await asyncio.sleep(20)

        msgs = conn.received
        print(f'\n========== RESULTS ==========')
        print(f'Total received: {len(msgs)}')
        if msgs:
            print(f'First: {msgs[0]}')
            print(f'Last: {msgs[-1]}')
            if msgs == list(range(1, len(msgs) + 1)):
                print('Sequence check: CORRECT (1 to', len(msgs), 'in order)')
            else:
                print('Sequence check: OUT OF ORDER')

asyncio.run(main())
