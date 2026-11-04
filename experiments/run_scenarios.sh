#!/bin/bash
# Challenging scenarios (rubric: Challenging Scenario / Robustness).
# Run from the project root:
#   sudo env "PATH=$PATH" bash experiments/run_scenarios.sh
#
# Results go to results/scenarios/ so they do not mix with the main experiments.

set -e
cd "$(dirname "$0")/.."
mkdir -p results/scenarios

run() {  # run <run-id> <extra args...>
  id="$1"; shift
  python3 experiments/run_experiment.py --clients 2 --rate 10 --count 300 --run-id "$id" "$@"
  mv "results/logs/$id" "results/scenarios/$id"
}

for ctrl in adaptive baseline; do
  # 1. added packet loss on the core links
  run "scen_loss5_${ctrl}" --controller "$ctrl" --loss 5
  # 2. both paths down (controller should log NO_PATH and not crash)
  run "scen_bothdown_${ctrl}" --controller "$ctrl" \
      --event down:s1-s2@5 --event down:s1-s3@10 --event up:s1-s2@18 --event up:s1-s3@18
  # 3. repeated failures on alternating paths
  run "scen_multi_${ctrl}" --controller "$ctrl" \
      --event down:s1-s2@5 --event up:s1-s2@10 --event down:s1-s3@15 --event up:s1-s3@20
done

python3 analysis/analyze_logs.py results/scenarios results/scenarios_summary.csv
echo "Done. See results/scenarios_summary.csv"
