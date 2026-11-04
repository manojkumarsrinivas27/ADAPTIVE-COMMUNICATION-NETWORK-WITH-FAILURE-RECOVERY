import argparse
import socket
import time

import protocol


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("server_ip")
    parser.add_argument("--client-id", type=int, default=1)
    parser.add_argument("--rate", type=float, default=10.0)
    parser.add_argument("--count", type=int, default=200)
    parser.add_argument("--log", default="client.log")
    parser.add_argument("--port", type=int, default=protocol.SERVER_PORT)
    parser.add_argument("--alert-ip", default=None)
    parser.add_argument("--alert-threshold", type=int, default=protocol.ALERT_THRESHOLD)
    return parser.parse_args()


def wait_for_ack(sock, client_id, seq, timeout):
    deadline = time.time() + timeout
    while True:
        remaining = deadline - time.time()
        if remaining <= 0:
            return None
        sock.settimeout(remaining)
        try:
            data, _ = sock.recvfrom(4096)
        except socket.timeout:
            return None
        try:
            ptype, cid, ack_seq, _, _ = protocol.unpack(data)
        except ValueError:
            continue
        if ptype == protocol.ACK and cid == client_id and ack_seq == seq:
            return time.time()


def send_alert(args, seq):
    if not args.alert_ip:
        return
    alert_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        packet = protocol.pack(protocol.ALERT, args.client_id, seq, args.server_ip.encode())
        alert_sock.sendto(packet, (args.alert_ip, protocol.CONTROLLER_ALERT_PORT))
    except OSError:
        pass
    finally:
        alert_sock.close()


def main():
    args = parse_args()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server = (args.server_ip, args.port)
    interval = 1.0 / args.rate
    payload = b"x" * protocol.PAYLOAD_SIZE
    misses = 0
    with open(args.log, "w") as log:
        log.write("client_id,seq,send_time,ack_time,retries,success\n")
        log.flush()
        for seq in range(args.count):
            started = time.time()
            ack_at = None
            retries = 0
            for attempt in range(protocol.MAX_RETRIES + 1):
                retries = attempt
                try:
                    sock.sendto(protocol.pack(protocol.DATA, args.client_id, seq, payload), server)
                except OSError:
                    time.sleep(protocol.ACK_TIMEOUT)
                    ack_at = None
                else:
                    ack_at = wait_for_ack(sock, args.client_id, seq, protocol.ACK_TIMEOUT)
                if ack_at is not None:
                    misses = 0
                    break
                misses += 1
                if misses % args.alert_threshold == 0:
                    send_alert(args, seq)
            log.write("%d,%d,%.6f,%s,%d,%d\n" % (
                args.client_id,
                seq,
                started,
                "%.6f" % ack_at if ack_at is not None else "",
                retries,
                1 if ack_at is not None else 0,
            ))
            log.flush()
            pause = interval - (time.time() - started)
            if pause > 0:
                time.sleep(pause)


if __name__ == "__main__":
    main()
