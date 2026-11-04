# Final numbers

Source: `results/summary.csv` (36 runs: 18 adaptive, 18 baseline). Each value is the mean over runs, with the standard deviation in brackets.

## 1. Adaptive vs baseline (all runs)

| Metric | Adaptive | Baseline | Change vs baseline |
|---|---|---|---|
| Recovery time (s) | 0.32 (0.09) | 7.40 (0.32) | -95.6 % |
| Unrecovered loss (%) | 0.00 (0.00) | 1.19 (0.42) | -100.0 % |
| Raw loss, all attempts (%) | 0.65 (0.70) | 12.11 (3.83) | -94.6 % |
| RTT before failure (ms) | 41.80 (12.87) | 34.98 (10.20) | +19.5 % |
| RTT during failure (ms) | 210.97 (133.60) | 1348.82 (533.58) | -84.4 % |
| RTT after failure (ms) | 41.01 (10.64) | 37.78 (11.26) | +8.6 % |
| Throughput (kbps) | 6.90 (3.92) | 5.58 (3.08) | +23.8 % |

For recovery time, loss and RTT a negative change is better. For throughput a positive change is better.

## 2a. By number of clients

| clients | controller | runs | recovery (s) | unrecovered loss (%) | raw loss (%) | RTT during (ms) | throughput (kbps) |
|---|---|---|---|---|---|---|---|
| 1 | adaptive | 6 | 0.30 | 0.00 | 0.66 | 251.91 | 3.31 |
| 1 | baseline | 6 | 7.26 | 1.20 | 12.31 | 1578.96 | 2.74 |
| 2 | adaptive | 6 | 0.31 | 0.00 | 0.62 | 230.51 | 6.96 |
| 2 | baseline | 6 | 7.48 | 1.20 | 12.38 | 1504.03 | 5.60 |
| 3 | adaptive | 6 | 0.36 | 0.00 | 0.68 | 150.48 | 10.45 |
| 3 | baseline | 6 | 7.45 | 1.18 | 11.63 | 963.48 | 8.38 |

## 2b. By sending rate (packets/s per client)

| rate | controller | runs | recovery (s) | unrecovered loss (%) | raw loss (%) | RTT during (ms) | throughput (kbps) |
|---|---|---|---|---|---|---|---|
| 5.0 | adaptive | 9 | 0.28 | 0.00 | 0.68 | 174.62 | 4.71 |
| 5.0 | baseline | 9 | 7.31 | 1.60 | 15.77 | 1230.02 | 3.83 |
| 10.0 | adaptive | 9 | 0.37 | 0.00 | 0.62 | 247.31 | 9.09 |
| 10.0 | baseline | 9 | 7.48 | 0.79 | 8.44 | 1467.62 | 7.33 |

## 3. RTT before, during and after the failure (ms)

| controller | before | during | after | during / before |
|---|---|---|---|---|
| adaptive | 41.80 | 210.97 | 41.01 | 5.0x |
| baseline | 34.98 | 1348.82 | 37.78 | 38.6x |

## 4. Challenging scenarios

| run | controller | sent | delivered | unrecovered loss (%) | raw loss (%) | RTT during (ms) | recovery (s) | throughput (kbps) |
|---|---|---|---|---|---|---|---|---|
| scen_bothdown_adaptive | adaptive | 600 | 594 | 1.0 | 8.62 | 337.74 | 0.352 | 7.839 |
| scen_bothdown_baseline | baseline | 600 | 592 | 1.33 | 12.81 | 1382.09 | 13.356 | 6.221 |
| scen_loss5_adaptive | adaptive | 600 | 600 | 0.0 | 18.48 | 476.27 | 0.122 | 6.241 |
| scen_loss5_baseline | baseline | 600 | 596 | 0.67 | 25.87 | 392.44 | 7.462 | 5.053 |
| scen_multi_adaptive | adaptive | 600 | 600 | 0.0 | 0.5 | 347.17 | 0.413 | 9.929 |
| scen_multi_baseline | baseline | 600 | 598 | 0.33 | 5.68 | 2285.35 | 5.136 | 7.589 |

Note: `recovery_time_s` is measured from the FIRST failure only. In the both-paths-down and repeated-failure scenarios, the loss columns describe the whole experiment.

