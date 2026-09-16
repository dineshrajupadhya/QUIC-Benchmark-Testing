import asyncio
import json
from aioquic.asyncio import QuicConnectionProtocol, serve
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.events import QuicEvent, StreamDataReceived

class MoQServer(QuicConnectionProtocol):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.buffer = ''

    def quic_event_received(self, event: QuicEvent):
        if isinstance(event, StreamDataReceived):
            self.buffer += event.data.decode()
            while '\n' in self.buffer:
                line, self.buffer = self.buffer.split('\n', 1)
                if line.strip():
                    try:
                        msg = json.loads(line.strip())
                        if msg.get('type') == 'subscribe':
                            topic = msg.get('topic', 'dinesh/in')
                            print(f'[Server] Subscriber connected for topic: {topic}')
                            asyncio.ensure_future(self.publish_sequence(event.stream_id, topic))
                    except json.JSONDecodeError:
                        pass

    async def publish_sequence(self, stream_id, topic):
        print(f'[Server] Starting to publish 1-10000 on topic: {topic}')
        for i in range(1, 10001):
            message = json.dumps({'topic': topic, 'seq': i, 'val': i})
            self._quic.send_stream_data(stream_id, message.encode() + b'\n')
            if i % 1000 == 0:
                print(f'[Server] Sent: {i}')
            await asyncio.sleep(0.0005)
        print(f'[Server] Done! Published 10000 messages.')

async def main():
    config = QuicConfiguration(is_client=False)
    config.load_cert_chain('/tmp/aioquic/examples/cert.pem', '/tmp/aioquic/examples/key.pem')
    print('=== MoQ Pub/Sub Server ===')
    print('Topic: dinesh/in')
    print('Waiting for subscriber on port 4434...')
    await serve('127.0.0.1', 4434, configuration=config, create_protocol=MoQServer)
    await asyncio.Future()

asyncio.run(main())
