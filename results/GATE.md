# Go-live gate

Updated 2026-11-17 08:23 UTC. A strategy is **READY** only when every check passes. **WAIT** means not enough data yet. Thresholds: `config.toml [gate]`. Even READY means only "eligible for a tiny live trial", never "safe".

## Forex trend strategy: **NOT READY**

| Check | Status | Detail |
|---|---|---|
| duration | WAIT | 0.3 of 26 weeks |
| edge | WAIT | practice return +0.41% after all costs |
| costs | PASS | fills 0.74 bps vs assumed 1.34 bps (max x1.25); financing paid -1.87 vs assumed 1.78 (7 fills) |
| agreement | PASS | practice +0.41% vs paper +0.90% (gap -0.49 pts, max 3) |
| reliability | FAIL | missed weekdays 0; mismatches 1; order problems 2; not halted |
| drawdown | PASS | worst fall -0.0% (limit -20%) |

## Forex learning model: **NOT READY**

| Check | Status | Detail |
|---|---|---|
| duration | WAIT | 0.3 of 26 weeks |
| edge | WAIT | practice return +0.01% after all costs; live IC: 0 week(s) scored |
| costs | FAIL | fills 0.67 bps vs assumed 1.31 bps (max x1.25); financing paid 20.66 vs assumed 2.43 (6 fills) |
| agreement | PASS | practice +0.01% vs paper +0.26% (gap -0.25 pts, max 3) |
| reliability | PASS | missed weekdays 0; mismatches 0; order problems 0; not halted |
| drawdown | PASS | worst fall -0.1% (limit -20%) |
