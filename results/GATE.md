# Go-live gate

Updated 2026-11-20 09:59 UTC. A strategy is **READY** only when every check passes. **WAIT** means not enough data yet. Thresholds: `config.toml [gate]`. Even READY means only "eligible for a tiny live trial", never "safe".

## Forex trend strategy: **NOT READY**

| Check | Status | Detail |
|---|---|---|
| duration | WAIT | 0.7 of 26 weeks |
| edge | WAIT | practice return +1.60% after all costs |
| costs | WAIT | fills 0.68 bps vs assumed 1.32 bps (max x1.25); financing: too early to judge (5 of 10 weekdays held) |
| agreement | PASS | practice +1.60% vs paper +2.01% (gap -0.41 pts, max 3) |
| reliability | FAIL | missed weekdays 0; mismatches 1; order problems 2; not halted |
| drawdown | PASS | worst fall -0.3% (limit -20%) |

## Forex learning model: **WAIT**

| Check | Status | Detail |
|---|---|---|
| duration | WAIT | 0.7 of 26 weeks |
| edge | WAIT | practice return +1.33% after all costs; live IC: 0 week(s) scored |
| costs | WAIT | fills 0.67 bps vs assumed 1.31 bps (max x1.25); financing: too early to judge (5 of 10 weekdays held) |
| agreement | PASS | practice +1.33% vs paper +1.64% (gap -0.31 pts, max 3) |
| reliability | PASS | missed weekdays 0; mismatches 0; order problems 0; not halted |
| drawdown | PASS | worst fall -0.1% (limit -20%) |
