import csv
import glob
import json
import os
import statistics
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "app"))

import protocol

FIELDS = [
    "run_id", "controller", "clients", "rate", "loss", "delay",
    "sent", "delivered", "unrecovered_loss_pct", "raw_loss_pct",
    "rtt_avg_ms", "rtt_min_ms", "rtt_max_ms",
    "rtt_before_ms", "rtt_during_ms", "rtt_after_ms",
    "recovery_time_s", "throughput_kbps",
]


def read_csv(path):
    with open(path) as f:
        return list(csv.DictReader(f))


def load_clients(run_dir):
    rows = []
    for path in sorted(glob.glob(os.path.join(run_dir, "client_*.log"))):
        for r in read_csv(path):
            rows.append({
                "client_id": int(r["client_id"]),
                "seq": int(r["seq"]),
                "send": float(r["send_time"]),
                "ack": float(r["ack_time"]) if r["ack_time"] else None,
                "retries": int(r["retries"]),
                "success": r["success"] == "1",
            })
    return rows


def failure_time(run_dir):
    path = os.path.join(run_dir, "events.csv")
    if not os.path.exists(path):
        return None
    for r in read_csv(path):
        if r["action"] == "down":
            return float(r["time"])
    return None


def recovery_time(rows, fail_ts):
    per_client = []
    for cid in sorted({r["client_id"] for r in rows}):
        candidates = [
            r["ack"] for r in rows
            if r["client_id"] == cid and r["success"] and r["ack"] > fail_ts
            and (r["retries"] > 0 or r["send"] >= fail_ts)
        ]
        if not candidates:
            return None
        per_client.append(min(candidates) - fail_ts)
    return max(per_client) if per_client else None


def mean_ms(values):
    return round(statistics.mean(values) * 1000, 2) if values else ""


def analyze_run(run_dir):
    with open(os.path.join(run_dir, "config.json")) as f:
        cfg = json.load(f)
    rows = load_clients(run_dir)
    if not rows:
        return None
    fail = failure_time(run_dir)
    ok = [r for r in rows if r["success"]]
    total_tx = sum(r["retries"] + 1 for r in rows)
    lost_tx = sum(r["retries"] if r["success"] else r["retries"] + 1 for r in rows)
    rtts = [(r["ack"], r["ack"] - r["send"]) for r in ok]

    rec = recovery_time(rows, fail) if fail else None
    before, during, after = [], [], []
    if fail:
        before = [d for a, d in rtts if a < fail]
        if rec is None:
            during = [d for a, d in rtts if a >= fail]
        else:
            end = fail + rec + 1e-6
            during = [d for a, d in rtts if fail <= a <= end]
            after = [d for a, d in rtts if a > end]

    throughput = ""
    if ok:
        span = max(r["ack"] for r in ok) - min(r["send"] for r in rows)
        if span > 0:
            throughput = round(len(ok) * protocol.PAYLOAD_SIZE * 8 / 1000 / span, 3)

    all_rtt = [d for _, d in rtts]
    return {
        "run_id": cfg["run_id"],
        "controller": cfg["controller"],
        "clients": cfg["clients"],
        "rate": cfg["rate"],
        "loss": cfg["loss"],
        "delay": cfg["delay"],
        "sent": len(rows),
        "delivered": len(ok),
        "unrecovered_loss_pct": round(100.0 * (len(rows) - len(ok)) / len(rows), 2),
        "raw_loss_pct": round(100.0 * lost_tx / total_tx, 2),
        "rtt_avg_ms": mean_ms(all_rtt),
        "rtt_min_ms": round(min(all_rtt) * 1000, 2) if all_rtt else "",
        "rtt_max_ms": round(max(all_rtt) * 1000, 2) if all_rtt else "",
        "rtt_before_ms": mean_ms(before),
        "rtt_during_ms": mean_ms(during),
        "rtt_after_ms": mean_ms(after),
        "recovery_time_s": round(rec, 3) if rec is not None else "",
        "throughput_kbps": throughput,
    }


def analyze_all(logs_dir, out_path):
    results = []
    for run_dir in sorted(glob.glob(os.path.join(logs_dir, "*"))):
        if os.path.exists(os.path.join(run_dir, "config.json")):
            result = analyze_run(run_dir)
            if result:
                results.append(result)
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(results)
    return results


def main():
    logs_dir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "results", "logs")
    out_path = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, "results", "summary.csv")
    results = analyze_all(logs_dir, out_path)
    print(" | ".join(FIELDS))
    for r in results:
        print(" | ".join(str(r[k]) for k in FIELDS))


if __name__ == "__main__":
    main()
