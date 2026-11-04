import csv
import os
import statistics
import sys
from collections import defaultdict

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

import analyze_logs

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COLORS = {"adaptive": "tab:green", "baseline": "tab:red"}


def load_summary(path):
    with open(path) as f:
        return list(csv.DictReader(f))


def num(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def mean_by(rows, group_key, value_key):
    groups = defaultdict(list)
    for r in rows:
        v = num(r[value_key])
        if v is not None:
            groups[r[group_key]].append(v)
    return {k: statistics.mean(v) for k, v in groups.items()}


def bar_by_controller(rows, value_key, ylabel, title, path):
    data = mean_by(rows, "controller", value_key)
    names = sorted(data)
    plt.figure(figsize=(5, 4))
    plt.bar(names, [data[n] for n in names], color=[COLORS.get(n, "gray") for n in names])
    plt.ylabel(ylabel)
    plt.title(title)
    plt.tight_layout()
    plt.savefig(path, dpi=150)
    plt.close()


def line_by_clients(rows, value_key, ylabel, title, path):
    plt.figure(figsize=(6, 4))
    for controller in sorted({r["controller"] for r in rows}):
        subset = [r for r in rows if r["controller"] == controller]
        data = mean_by(subset, "clients", value_key)
        xs = sorted(data, key=float)
        if xs:
            plt.plot([float(x) for x in xs], [data[x] for x in xs], marker="o",
                     label=controller, color=COLORS.get(controller))
    plt.xlabel("Number of clients")
    plt.ylabel(ylabel)
    plt.title(title)
    plt.legend()
    plt.tight_layout()
    plt.savefig(path, dpi=150)
    plt.close()


def rtt_timeline(logs_dir, rows, out_dir):
    for controller in sorted({r["controller"] for r in rows}):
        run = next(r for r in rows if r["controller"] == controller)
        run_dir = os.path.join(logs_dir, run["run_id"])
        client_rows = [r for r in analyze_logs.load_clients(run_dir) if r["success"]]
        if not client_rows:
            continue
        fail = analyze_logs.failure_time(run_dir)
        t0 = fail if fail else min(r["send"] for r in client_rows)
        plt.figure(figsize=(7, 4))
        for cid in sorted({r["client_id"] for r in client_rows}):
            pts = [r for r in client_rows if r["client_id"] == cid]
            plt.scatter([r["ack"] - t0 for r in pts], [(r["ack"] - r["send"]) * 1000 for r in pts],
                        s=8, label="client %d" % cid)
        if fail:
            plt.axvline(0, color="red", linestyle="--", label="link failure")
        plt.xlabel("Time relative to failure (s)")
        plt.ylabel("Effective RTT (ms)")
        plt.title("RTT over time (%s)" % controller)
        plt.legend()
        plt.tight_layout()
        plt.savefig(os.path.join(out_dir, "rtt_timeline_%s.png" % controller), dpi=150)
        plt.close()


def main():
    logs_dir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "results", "logs")
    summary = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, "results", "summary.csv")
    out_dir = sys.argv[3] if len(sys.argv) > 3 else os.path.join(ROOT, "results", "graphs")
    os.makedirs(out_dir, exist_ok=True)
    rows = load_summary(summary)
    if not rows:
        return
    bar_by_controller(rows, "recovery_time_s", "Seconds", "Recovery time",
                      os.path.join(out_dir, "recovery_time.png"))
    bar_by_controller(rows, "raw_loss_pct", "Percent", "Packet loss",
                      os.path.join(out_dir, "packet_loss.png"))
    bar_by_controller(rows, "unrecovered_loss_pct", "Percent", "Unrecovered loss after retransmission",
                      os.path.join(out_dir, "unrecovered_loss.png"))
    line_by_clients(rows, "recovery_time_s", "Seconds", "Recovery time vs clients",
                    os.path.join(out_dir, "recovery_vs_clients.png"))
    line_by_clients(rows, "raw_loss_pct", "Percent", "Packet loss vs clients",
                    os.path.join(out_dir, "loss_vs_clients.png"))
    rtt_timeline(logs_dir, rows, out_dir)


if __name__ == "__main__":
    main()
