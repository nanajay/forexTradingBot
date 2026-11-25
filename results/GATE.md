# Go-live gate

Updated 2026-11-25 11:16 UTC. A strategy is **READY** only when every check passes. **WAIT** means not enough data yet. Thresholds: `config.toml [gate]`. Even READY means only "eligible for a tiny live trial", never "safe".

## Forex trend strategy: **NOT READY**

| Check | Status | Detail |
|---|---|---|
| duration | WAIT | 1.4 of 26 weeks |
| edge | WAIT | practice return +2.33% after all costs |
| costs | WAIT | fills 0.68 bps vs assumed 1.32 bps (max x1.25); financing: too early to judge (8 of 10 weekdays held) |
| agreement | PASS | practice +2.33% vs paper +2.73% (gap -0.39 pts, max 3) |
| reliability | FAIL | missed weekdays 0; mismatches 1; order problems 2; not halted |
| drawdown | PASS | worst fall -0.3% (limit -20%) |

## Forex learning model: **WAIT**

| Check | Status | Detail |
|---|---|---|
| duration | WAIT | 1.4 of 26 weeks |
| edge | WAIT | practice return +0.01% after all costs; live IC: 1 week(s) scored |
| costs | WAIT | fills 0.68 bps vs assumed 1.29 bps (max x1.25); financing: too early to judge (8 of 10 weekdays held) |
| agreement | PASS | practice +0.01% vs paper +0.29% (gap -0.28 pts, max 3) |
| reliability | PASS | missed weekdays 0; mismatches 0; order problems 0; not halted |
| drawdown | PASS | worst fall -1.3% (limit -20%) |
