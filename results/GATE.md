# Go-live gate

Updated 2026-11-23 10:45 UTC. A strategy is **READY** only when every check passes. **WAIT** means not enough data yet. Thresholds: `config.toml [gate]`. Even READY means only "eligible for a tiny live trial", never "safe".

## Forex trend strategy: **NOT READY**

| Check | Status | Detail |
|---|---|---|
| duration | WAIT | 1.1 of 26 weeks |
| edge | WAIT | practice return +1.96% after all costs |
| costs | WAIT | fills 0.68 bps vs assumed 1.32 bps (max x1.25); financing: too early to judge (6 of 10 weekdays held) |
| agreement | PASS | practice +1.96% vs paper +2.34% (gap -0.38 pts, max 3) |
| reliability | FAIL | missed weekdays 0; mismatches 1; order problems 2; not halted |
| drawdown | PASS | worst fall -0.3% (limit -20%) |

## Forex learning model: **WAIT**

| Check | Status | Detail |
|---|---|---|
| duration | WAIT | 1.1 of 26 weeks |
| edge | WAIT | practice return +0.83% after all costs; live IC: 1 week(s) scored |
| costs | WAIT | fills 0.68 bps vs assumed 1.29 bps (max x1.25); financing: too early to judge (6 of 10 weekdays held) |
| agreement | PASS | practice +0.83% vs paper +1.12% (gap -0.29 pts, max 3) |
| reliability | PASS | missed weekdays 0; mismatches 0; order problems 0; not halted |
| drawdown | PASS | worst fall -0.5% (limit -20%) |
