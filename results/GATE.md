# Go-live gate

Updated 2026-11-19 10:18 UTC. A strategy is **READY** only when every check passes. **WAIT** means not enough data yet. Thresholds: `config.toml [gate]`. Even READY means only "eligible for a tiny live trial", never "safe".

## Forex trend strategy: **NOT READY**

| Check | Status | Detail |
|---|---|---|
| duration | WAIT | 0.6 of 26 weeks |
| edge | WAIT | practice return +0.85% after all costs |
| costs | WAIT | fills 0.70 bps vs assumed 1.32 bps (max x1.25); financing: too early to judge (4 of 10 weekdays held) |
| agreement | PASS | practice +0.85% vs paper +1.28% (gap -0.43 pts, max 3) |
| reliability | FAIL | missed weekdays 0; mismatches 1; order problems 2; not halted |
| drawdown | PASS | worst fall -0.3% (limit -20%) |

## Forex learning model: **WAIT**

| Check | Status | Detail |
|---|---|---|
| duration | WAIT | 0.6 of 26 weeks |
| edge | WAIT | practice return +0.50% after all costs; live IC: 0 week(s) scored |
| costs | WAIT | fills 0.67 bps vs assumed 1.31 bps (max x1.25); financing: too early to judge (4 of 10 weekdays held) |
| agreement | PASS | practice +0.50% vs paper +0.79% (gap -0.30 pts, max 3) |
| reliability | PASS | missed weekdays 0; mismatches 0; order problems 0; not halted |
| drawdown | PASS | worst fall -0.1% (limit -20%) |
