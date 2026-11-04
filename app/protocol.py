import struct
import time

SERVER_PORT = 5005
CONTROLLER_ALERT_PORT = 5006
PAYLOAD_SIZE = 64
ACK_TIMEOUT = 0.3
MAX_RETRIES = 8
ALERT_THRESHOLD = 3

DATA = 1
ACK = 2
HEARTBEAT = 3
ALERT = 4

HEADER_FORMAT = "!BHId"
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)


def pack(ptype, client_id, seq, payload=b"", timestamp=None):
    if timestamp is None:
        timestamp = time.time()
    return struct.pack(HEADER_FORMAT, ptype, client_id, seq, timestamp) + payload


def unpack(data):
    if len(data) < HEADER_SIZE:
        raise ValueError("short packet")
    ptype, client_id, seq, timestamp = struct.unpack(HEADER_FORMAT, data[:HEADER_SIZE])
    if ptype not in (DATA, ACK, HEARTBEAT, ALERT):
        raise ValueError("unknown type")
    return ptype, client_id, seq, timestamp, data[HEADER_SIZE:]
