# Go-live gate

Updated 2026-11-17 16:08 UTC. A strategy is **READY** only when every check passes. **WAIT** means not enough data yet. Thresholds: `config.toml [gate]`. Even READY means only "eligible for a tiny live trial", never "safe".

## Forex trend strategy: **NOT READY**

| Check | Status | Detail |
|---|---|---|
| duration | WAIT | 0.3 of 26 weeks |
| edge | WAIT | practice return +0.16% after all costs |
| costs | WAIT | fills 0.74 bps vs assumed 1.34 bps (max x1.25); financing: too early to judge (2 of 10 weekdays held) |
| agreement | PASS | practice +0.16% vs paper +0.90% (gap -0.74 pts, max 3) |
| reliability | FAIL | missed weekdays 0; mismatches 1; order problems 2; not halted |
| drawdown | PASS | worst fall -0.3% (limit -20%) |

## Forex learning model: **WAIT**

| Check | Status | Detail |
|---|---|---|
| duration | WAIT | 0.3 of 26 weeks |
| edge | WAIT | practice return -0.13% after all costs; live IC: 0 week(s) scored |
| costs | WAIT | fills 0.67 bps vs assumed 1.31 bps (max x1.25); financing: too early to judge (2 of 10 weekdays held) |
| agreement | PASS | practice -0.13% vs paper +0.11% (gap -0.23 pts, max 3) |
| reliability | PASS | missed weekdays 0; mismatches 0; order problems 0; not halted |
| drawdown | PASS | worst fall -0.1% (limit -20%) |
