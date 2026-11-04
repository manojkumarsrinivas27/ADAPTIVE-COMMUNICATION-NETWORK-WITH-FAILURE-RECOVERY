#!/bin/bash
# Runs the full experiment matrix (adaptive vs baseline, 1-3 clients, 2 rates, 3 repeats)
# and then builds results/summary.csv and the graphs.
#
# Run from the project root:
#   sudo env "PATH=$PATH" bash experiments/run_all.sh
#
# 36 runs, roughly 45 minutes. Reduce the loops below for a quicker test.

set -e
cd "$(dirname "$0")/.."

for rep in 1 2 3; do
  for ctrl in adaptive baseline; do
    for clients in 1 2 3; do
      for rate in 5 10; do
        # --count scales with the rate so every run lasts about 25 s and the
        # client is still sending when the link is restored at second 12.
        python3 experiments/run_experiment.py \
          --controller "$ctrl" --clients "$clients" --rate "$rate" \
          --count $((rate * 25)) \
          --run-id "${ctrl}_c${clients}_r${rate}_rep${rep}"
      done
    done
  done
done

python3 analysis/analyze_logs.py
python3 analysis/plot_results.py
echo "Done. See results/summary.csv and results/graphs/"
