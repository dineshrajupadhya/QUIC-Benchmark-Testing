import struct
from enum import IntEnum
from dataclasses import dataclass
from typing import Optional

class MessageType(IntEnum):
    CLIENT_SETUP = 0x00
    SERVER_SETUP = 0x01
    REQUEST_ERROR = 0x02
    REQUEST_OK = 0x03
    SUBSCRIBE = 0x05
    SUBSCRIBE_OK = 0x06
    SUBSCRIBE_DONE = 0x07
    UNSUBSCRIBE = 0x08
    STOP_SENDING = 0x09
    PUBLISH = 0x0A
    PUBLISH_OK = 0x0B
    PUBLISH_DONE = 0x0C
    PUBLISH_NAMESPACE = 0x0D
    SUBSCRIBE_NAMESPACE = 0x10

class ErrorCode(IntEnum):
    NO_ERROR = 0x00
    DOES_NOT_EXIST = 0x01
    PROTOCOL_VIOLATION = 0x06

class FilterType(IntEnum):
    LARGEST_OBJECT = 0x06

MOQT_VERSION_1 = 0x00000001

def encode_varint(value):
    if value <= 0x3F:
        return struct.pack("!B", value)
    elif value <= 0x3FFF:
        return struct.pack("!H", value | 0x4000)
    elif value <= 0x3FFFFFFF:
        return struct.pack("!I", value | 0x80000000)
    elif value <= 0x3FFFFFFFFFFFFFFF:
        return struct.pack("!Q", value | 0xC000000000000000)
    else:
        raise ValueError("Varint too large")

def decode_varint(data, offset=0):
    first = data[offset]
    tag = (first & 0xC0) >> 6
    if tag == 0:
        return first & 0x3F, 1
    elif tag == 1:
        return struct.unpack("!H", data[offset:offset+2])[0] & 0x3FFF, 2
    elif tag == 2:
        return struct.unpack("!I", data[offset:offset+4])[0] & 0x3FFFFFFF, 4
    else:
        return struct.unpack("!Q", data[offset:offset+8])[0] & 0x3FFFFFFFFFFFFFFF, 8

def encode_namespace(ns):
    result = bytearray()
    for part in ns.split("/"):
        b = part.encode("utf-8")
        result.extend(encode_varint(len(b)))
        result.extend(b)
    return bytes(result)

def decode_namespace(data, offset=0):
    parts = []
    consumed = 0
    while offset < len(data):
        ln, c = decode_varint(data, offset)
        offset += c
        consumed += c
        if ln == 0:
            break
        parts.append(data[offset:offset+ln].decode("utf-8"))
        offset += ln
        consumed += ln
    return "/".join(parts), consumed

def _msg(mt, payload):
    return encode_varint(mt) + encode_varint(len(payload)) + payload

@dataclass
class MoqMessage:
    message_type: MessageType = MessageType.CLIENT_SETUP
    length: int = 0

@dataclass
class ClientSetup(MoqMessage):
    supported_versions: list = None
    def __post_init__(self):
        self.message_type = MessageType.CLIENT_SETUP
        if self.supported_versions is None:
            self.supported_versions = [MOQT_VERSION_1]
    def encode(self):
        p = bytearray()
        p.extend(encode_varint(0))
        p.extend(encode_varint(len(self.supported_versions)))
        for v in self.supported_versions:
            p.extend(encode_varint(v))
        p.extend(encode_varint(0))
        return _msg(MessageType.CLIENT_SETUP, bytes(p))

@dataclass
class ServerSetup(MoqMessage):
    selected_version: int = MOQT_VERSION_1
    def __post_init__(self):
        self.message_type = MessageType.SERVER_SETUP
    def encode(self):
        p = bytearray()
        p.extend(encode_varint(self.selected_version))
        p.extend(encode_varint(0))
        return _msg(MessageType.SERVER_SETUP, bytes(p))

@dataclass
class SubscribeRequest(MoqMessage):
    track_namespace: str = ""
    track_name: str = ""
    filter_type: FilterType = FilterType.LARGEST_OBJECT
    def __post_init__(self):
        self.message_type = MessageType.SUBSCRIBE
    def encode(self):
        p = bytearray()
        nb = encode_namespace(self.track_namespace)
        p.extend(encode_varint(len(nb)))
        p.extend(nb)
        tb = self.track_name.encode("utf-8")
        p.extend(encode_varint(len(tb)))
        p.extend(tb)
        p.extend(encode_varint(0))
        p.extend(encode_varint(self.filter_type))
        p.extend(encode_varint(0))
        p.extend(encode_varint(0))
        p.extend(encode_varint(0))
        return _msg(MessageType.SUBSCRIBE, bytes(p))

@dataclass
class SubscribeOk(MoqMessage):
    track_namespace: str = ""
    track_name: str = ""
    def __post_init__(self):
        self.message_type = MessageType.SUBSCRIBE_OK
    def encode(self):
        p = bytearray()
        nb = encode_namespace(self.track_namespace)
        p.extend(encode_varint(len(nb)))
        p.extend(nb)
        tb = self.track_name.encode("utf-8")
        p.extend(encode_varint(len(tb)))
        p.extend(tb)
        p.extend(encode_varint(1))
        return _msg(MessageType.SUBSCRIBE_OK, bytes(p))

@dataclass
class PublishRequest(MoqMessage):
    track_namespace: str = ""
    track_name: str = ""
    group_id: int = 0
    object_id: int = 0
    publisher_priority: int = 0
    object_payload: bytes = b""
    def __post_init__(self):
        self.message_type = MessageType.PUBLISH
    def encode(self):
        p = bytearray()
        nb = encode_namespace(self.track_namespace)
        p.extend(encode_varint(len(nb)))
        p.extend(nb)
        tb = self.track_name.encode("utf-8")
        p.extend(encode_varint(len(tb)))
        p.extend(tb)
        p.extend(encode_varint(self.group_id))
        p.extend(encode_varint(self.object_id))
        p.extend(encode_varint(self.publisher_priority))
        p.extend(encode_varint(len(self.object_payload)))
        p.extend(self.object_payload)
        return _msg(MessageType.PUBLISH, bytes(p))

@dataclass
class PublishOk(MoqMessage):
    track_namespace: str = ""
    track_name: str = ""
    def __post_init__(self):
        self.message_type = MessageType.PUBLISH_OK
    def encode(self):
        p = bytearray()
        nb = encode_namespace(self.track_namespace)
        p.extend(encode_varint(len(nb)))
        p.extend(nb)
        tb = self.track_name.encode("utf-8")
        p.extend(encode_varint(len(tb)))
        p.extend(tb)
        return _msg(MessageType.PUBLISH_OK, bytes(p))

@dataclass
class PublishDone(MoqMessage):
    track_namespace: str = ""
    track_name: str = ""
    error_code: ErrorCode = ErrorCode.NO_ERROR
    reason: str = ""
    def __post_init__(self):
        self.message_type = MessageType.PUBLISH_DONE
    def encode(self):
        p = bytearray()
        nb = encode_namespace(self.track_namespace)
        p.extend(encode_varint(len(nb)))
        p.extend(nb)
        tb = self.track_name.encode("utf-8")
        p.extend(encode_varint(len(tb)))
        p.extend(tb)
        p.extend(encode_varint(self.error_code))
        rb = self.reason.encode("utf-8")
        p.extend(encode_varint(len(rb)))
        p.extend(rb)
        return _msg(MessageType.PUBLISH_DONE, bytes(p))

class MoqMessageParser:
    @staticmethod
    def parse(data):
        if len(data) < 2:
            raise ValueError("Need more data")
        o = 0
        mt, c = decode_varint(data, o)
        o += c
        ln, c = decode_varint(data, o)
        o += c
        if len(data) < o + ln:
            raise ValueError("Need more data for payload")
        d = data[o:o+ln]
        o += ln
        if mt == MessageType.CLIENT_SETUP:
            return MoqMessageParser._cs(d), o
        elif mt == MessageType.SERVER_SETUP:
            return MoqMessageParser._ss(d), o
        elif mt == MessageType.SUBSCRIBE:
            return MoqMessageParser._sub(d), o
        elif mt == MessageType.SUBSCRIBE_OK:
            return MoqMessageParser._sok(d), o
        elif mt == MessageType.PUBLISH:
            return MoqMessageParser._pub(d), o
        elif mt == MessageType.PUBLISH_OK:
            return MoqMessageParser._pok(d), o
        elif mt == MessageType.PUBLISH_DONE:
            return MoqMessageParser._pdone(d), o
        else:
            return MoqMessage(message_type=MessageType(mt), length=ln), o

    @staticmethod
    def _cs(d):
        o = 0
        nr, c = decode_varint(d, o); o += c
        nv, c = decode_varint(d, o); o += c
        vs = []
        for _ in range(nv):
            v, c = decode_varint(d, o); o += c; vs.append(v)
        return ClientSetup(supported_versions=vs)

    @staticmethod
    def _ss(d):
        o = 0
        v, c = decode_varint(d, o); o += c
        np, c = decode_varint(d, o); o += c
        return ServerSetup(selected_version=v)

    @staticmethod
    def _sub(d):
        o = 0
        nl, c = decode_varint(d, o); o += c
        ns, _ = decode_namespace(d[o:o+nl]); o += nl
        tl, c = decode_varint(d, o); o += c
        tn = d[o:o+tl].decode("utf-8"); o += tl
        _, c = decode_varint(d, o); o += c
        ft, c = decode_varint(d, o); o += c
        _, c = decode_varint(d, o); o += c
        _, c = decode_varint(d, o); o += c
        _, c = decode_varint(d, o); o += c
        return SubscribeRequest(track_namespace=ns, track_name=tn, filter_type=FilterType(ft))

    @staticmethod
    def _sok(d):
        o = 0
        nl, c = decode_varint(d, o); o += c
        ns, _ = decode_namespace(d[o:o+nl]); o += nl
        tl, c = decode_varint(d, o); o += c
        tn = d[o:o+tl].decode("utf-8"); o += tl
        return SubscribeOk(track_namespace=ns, track_name=tn)

    @staticmethod
    def _pub(d):
        o = 0
        nl, c = decode_varint(d, o); o += c
        ns, _ = decode_namespace(d[o:o+nl]); o += nl
        tl, c = decode_varint(d, o); o += c
        tn = d[o:o+tl].decode("utf-8"); o += tl
        gi, c = decode_varint(d, o); o += c
        oi, c = decode_varint(d, o); o += c
        pp, c = decode_varint(d, o); o += c
        pl, c = decode_varint(d, o); o += c
        payload = d[o:o+pl]
        return PublishRequest(track_namespace=ns, track_name=tn, group_id=gi, object_id=oi, publisher_priority=pp, object_payload=payload)

    @staticmethod
    def _pok(d):
        o = 0
        nl, c = decode_varint(d, o); o += c
        ns, _ = decode_namespace(d[o:o+nl]); o += nl
        tl, c = decode_varint(d, o); o += c
        tn = d[o:o+tl].decode("utf-8"); o += tl
        return PublishOk(track_namespace=ns, track_name=tn)

    @staticmethod
    def _pdone(d):
        o = 0
        nl, c = decode_varint(d, o); o += c
        ns, _ = decode_namespace(d[o:o+nl]); o += nl
        tl, c = decode_varint(d, o); o += c
        tn = d[o:o+tl].decode("utf-8"); o += tl
        ec, c = decode_varint(d, o); o += c
        rl, c = decode_varint(d, o); o += c
        reason = d[o:o+rl].decode("utf-8") if rl > 0 else ""
        return PublishDone(track_namespace=ns, track_name=tn, error_code=ErrorCode(ec), reason=reason)


def test():
    for v in [0, 1, 63, 64, 16383, 16384]:
        assert decode_varint(encode_varint(v))[0] == v
    cs = ClientSetup()
    d = cs.encode()
    m, _ = MoqMessageParser.parse(d)
    assert m.message_type == MessageType.CLIENT_SETUP
    srv = ServerSetup()
    d = srv.encode()
    m, _ = MoqMessageParser.parse(d)
    assert m.message_type == MessageType.SERVER_SETUP
    sub = SubscribeRequest(track_namespace="dinesh/in", track_name="t1")
    d = sub.encode()
    m, _ = MoqMessageParser.parse(d)
    assert m.track_namespace == "dinesh/in"
    pub = PublishRequest(track_namespace="dinesh/in", track_name="t1", group_id=1, object_id=42, object_payload=b"hello")
    d = pub.encode()
    m, _ = MoqMessageParser.parse(d)
    assert m.object_payload == b"hello" and m.object_id == 42
    print("All protocol tests passed!")


if __name__ == "__main__":
    test()
