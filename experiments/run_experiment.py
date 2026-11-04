import argparse
import json
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "topology"))

from mininet.log import setLogLevel
from topo import ALERT_IP, CLIENT_HOSTS, SERVER_IP, build_network


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--controller", choices=["adaptive", "baseline"], default="adaptive")
    parser.add_argument("--clients", type=int, default=1)
    parser.add_argument("--rate", type=float, default=10.0)
    parser.add_argument("--count", type=int, default=200)
    parser.add_argument("--delay", default="5ms")
    parser.add_argument("--loss", type=float, default=0)
    parser.add_argument("--event", action="append")
    parser.add_argument("--settle", type=float, default=6.0)
    parser.add_argument("--max-time", type=float, default=90.0)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--external-controller", action="store_true")
    return parser.parse_args()


def parse_event(text):
    action, rest = text.split(":")
    link, when = rest.split("@")
    a, b = link.split("-")
    return float(when), action, a, b


def start_controller(kind, run_dir):
    script = "adaptive_controller.py" if kind == "adaptive" else "baseline_controller.py"
    env = dict(os.environ, CONTROLLER_LOG=os.path.join(run_dir, "controller.csv"))
    out = open(os.path.join(run_dir, "ryu.out"), "w")
    return subprocess.Popen(
        ["ryu-manager", os.path.join(ROOT, "controller", script), "--observe-links"],
        env=env,
        stdout=out,
        stderr=subprocess.STDOUT,
    )


def main():
    args = parse_args()
    setLogLevel("info")
    events = sorted(parse_event(e) for e in (args.event or ["down:s1-s2@5", "up:s1-s2@12"]))
    run_id = args.run_id or "%s_c%d_r%g_%d" % (args.controller, args.clients, args.rate, int(time.time()))
    run_dir = os.path.join(ROOT, "results", "logs", run_id)
    os.makedirs(run_dir, exist_ok=True)

    with open(os.path.join(run_dir, "config.json"), "w") as f:
        json.dump({
            "run_id": run_id,
            "controller": args.controller,
            "clients": args.clients,
            "rate": args.rate,
            "count": args.count,
            "delay": args.delay,
            "loss": args.loss,
        }, f)

    # "mn -c" also kills any running ryu-manager, so skip it when the controller
    # was started by hand (--external-controller).
    if not args.external_controller:
        subprocess.run(["mn", "-c"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    controller = None
    net = None
    server_proc = None
    clients = []
    try:
        if not args.external_controller:
            controller = start_controller(args.controller, run_dir)
            time.sleep(4)

        net = build_network(delay=args.delay, loss=args.loss)
        time.sleep(args.settle)
        net.pingAll(timeout="1")

        server = net.get("h2")
        server_proc = server.popen(
            ["python3", os.path.join(ROOT, "app", "udp_server.py"), os.path.join(run_dir, "server.log")],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(1)

        for i in range(args.clients):
            host = net.get(CLIENT_HOSTS[i % len(CLIENT_HOSTS)])
            cmd = [
                "python3", os.path.join(ROOT, "app", "udp_client.py"), SERVER_IP,
                "--client-id", str(i + 1),
                "--rate", str(args.rate),
                "--count", str(args.count),
                "--log", os.path.join(run_dir, "client_%d.log" % (i + 1)),
            ]
            if args.controller == "adaptive":
                cmd += ["--alert-ip", ALERT_IP]
            err = open(os.path.join(run_dir, "client_%d.err" % (i + 1)), "w")
            clients.append(host.popen(cmd, stdout=err, stderr=err))

        start = time.time()
        with open(os.path.join(run_dir, "events.csv"), "w") as ev:
            ev.write("time,action,link\n")
            for when, action, a, b in events:
                wait = start + when - time.time()
                if wait > 0:
                    time.sleep(wait)
                ts = time.time()
                net.configLinkStatus(a, b, action)
                ev.write("%.6f,%s,%s-%s\n" % (ts, action, a, b))
                ev.flush()

        deadline = start + args.max_time
        for proc in clients:
            try:
                proc.wait(timeout=max(0.0, deadline - time.time()))
            except subprocess.TimeoutExpired:
                proc.terminate()
    finally:
        for proc in clients:
            if proc.poll() is None:
                proc.terminate()
        if server_proc is not None:
            server_proc.terminate()
        if net is not None:
            net.stop()
        if controller is not None:
            controller.terminate()
            controller.wait()


if __name__ == "__main__":
    main()
