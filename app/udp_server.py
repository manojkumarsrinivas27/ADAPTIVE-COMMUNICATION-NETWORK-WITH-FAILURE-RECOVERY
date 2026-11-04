import signal
import socket
import sys
import time

import protocol


def _stop(signum, frame):
    raise KeyboardInterrupt


def main():
    log_path = sys.argv[1] if len(sys.argv) > 1 else "server.log"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else protocol.SERVER_PORT
    signal.signal(signal.SIGTERM, _stop)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("0.0.0.0", port))
    seen = {}
    malformed = 0
    with open(log_path, "w") as log:
        log.write("time,client_id,seq,duplicate\n")
        log.flush()
        try:
            while True:
                data, addr = sock.recvfrom(4096)
                try:
                    ptype, client_id, seq, timestamp, payload = protocol.unpack(data)
                except ValueError:
                    malformed += 1
                    continue
                if ptype == protocol.DATA:
                    received = seen.setdefault(client_id, set())
                    duplicate = seq in received
                    received.add(seq)
                    try:
                        sock.sendto(protocol.pack(protocol.ACK, client_id, seq, b"", timestamp), addr)
                    except OSError:
                        pass
                    log.write("%.6f,%d,%d,%d\n" % (time.time(), client_id, seq, int(duplicate)))
                    log.flush()
                elif ptype == protocol.HEARTBEAT:
                    try:
                        sock.sendto(protocol.pack(protocol.ACK, client_id, seq, b"", timestamp), addr)
                    except OSError:
                        pass
        except KeyboardInterrupt:
            pass
        finally:
            log.write("# malformed_packets=%d\n" % malformed)
            log.flush()


if __name__ == "__main__":
    main()
