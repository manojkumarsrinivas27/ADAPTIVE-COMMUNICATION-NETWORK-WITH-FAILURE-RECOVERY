"""Final calculations: reads results/summary.csv and results/scenarios_summary.csv and
writes readable comparison tables to results/final_numbers.md (and prints them).

Usage (from the project root):  python3 analysis/final_numbers.py
Change vs baseline % = (adaptive - baseline) / baseline * 100
"""
import csv
import os
import statistics as st

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SUMMARY = os.path.join(ROOT, "results", "summary.csv")
SCEN = os.path.join(ROOT, "results", "scenarios_summary.csv")
OUT = os.path.join(ROOT, "results", "final_numbers.md")

METRICS = [
    ("recovery_time_s", "Recovery time (s)"),
    ("unrecovered_loss_pct", "Unrecovered loss (%)"),
    ("raw_loss_pct", "Raw loss, all attempts (%)"),
    ("rtt_before_ms", "RTT before failure (ms)"),
    ("rtt_during_ms", "RTT during failure (ms)"),
    ("rtt_after_ms", "RTT after failure (ms)"),
    ("throughput_kbps", "Throughput (kbps)"),
]


def read(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def vals(rows, key):
    out = []
    for r in rows:
        v = r.get(key, "")
        if v not in ("", "None", None):
            out.append(float(v))
    return out


def mean(v):
    return st.mean(v) if v else None


def sd(v):
    return st.stdev(v) if len(v) > 1 else 0.0


def fmt(x, nd=2):
    return "n/a" if x is None else ("%." + str(nd) + "f") % x


def table(header, rows):
    lines = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    lines += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(lines)


def main():
    rows = read(SUMMARY)
    ad = [r for r in rows if r["controller"] == "adaptive"]
    ba = [r for r in rows if r["controller"] == "baseline"]
    out = []
    out.append("# Final numbers\n")
    out.append("Source: `results/summary.csv` (%d runs: %d adaptive, %d baseline). "
               "Each value is the mean over runs, with the standard deviation in brackets.\n" % (len(rows), len(ad), len(ba)))

    # 1. overall comparison
    out.append("## 1. Adaptive vs baseline (all runs)\n")
    t = []
    for key, label in METRICS:
        a, b = vals(ad, key), vals(ba, key)
        ma, mb = mean(a), mean(b)
        chg = "n/a" if (ma is None or not mb) else "%+.1f %%" % ((ma - mb) / mb * 100)
        t.append([label, "%s (%s)" % (fmt(ma), fmt(sd(a))), "%s (%s)" % (fmt(mb), fmt(sd(b))), chg])
    out.append(table(["Metric", "Adaptive", "Baseline", "Change vs baseline"], t) + "\n")
    out.append("For recovery time, loss and RTT a negative change is better. For throughput a positive change is better.\n")

    # 2. by number of clients and rate
    for group, title in (("clients", "number of clients"), ("rate", "sending rate (packets/s per client)")):
        out.append("## 2%s. By %s\n" % ("a" if group == "clients" else "b", title))
        t = []
        for g in sorted({r[group] for r in rows}, key=float):
            for ctrl in ("adaptive", "baseline"):
                sub = [r for r in rows if r[group] == g and r["controller"] == ctrl]
                t.append([g, ctrl, len(sub)] + [fmt(mean(vals(sub, k))) for k in
                          ("recovery_time_s", "unrecovered_loss_pct", "raw_loss_pct", "rtt_during_ms", "throughput_kbps")])
        out.append(table([group, "controller", "runs", "recovery (s)", "unrecovered loss (%)",
                          "raw loss (%)", "RTT during (ms)", "throughput (kbps)"], t) + "\n")

    # 3. RTT detail
    out.append("## 3. RTT before, during and after the failure (ms)\n")
    t = []
    for ctrl, grp in (("adaptive", ad), ("baseline", ba)):
        b, d, a = (mean(vals(grp, k)) for k in ("rtt_before_ms", "rtt_during_ms", "rtt_after_ms"))
        t.append([ctrl, fmt(b), fmt(d), fmt(a), "%.1fx" % (d / b) if (b and d) else "n/a"])
    out.append(table(["controller", "before", "during", "after", "during / before"], t) + "\n")

    # 4. scenarios
    if os.path.exists(SCEN):
        out.append("## 4. Challenging scenarios\n")
        t = [[r["run_id"], r["controller"], r["sent"], r["delivered"], r["unrecovered_loss_pct"],
              r["raw_loss_pct"], r["rtt_during_ms"], r["recovery_time_s"], r["throughput_kbps"]]
             for r in read(SCEN)]
        out.append(table(["run", "controller", "sent", "delivered", "unrecovered loss (%)",
                          "raw loss (%)", "RTT during (ms)", "recovery (s)", "throughput (kbps)"], t) + "\n")
        out.append("Note: `recovery_time_s` is measured from the FIRST failure only. In the both-paths-down and "
                   "repeated-failure scenarios, the loss columns describe the whole experiment.\n")

    text = "\n".join(out)
    with open(OUT, "w") as f:
        f.write(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
