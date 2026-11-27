# Go-live gate

Updated 2026-11-27 10:50 UTC. A strategy is **READY** only when every check passes. **WAIT** means not enough data yet. Thresholds: `config.toml [gate]`. Even READY means only "eligible for a tiny live trial", never "safe".

## Forex trend strategy: **NOT READY**

| Check | Status | Detail |
|---|---|---|
| duration | WAIT | 1.7 of 26 weeks |
| edge | WAIT | practice return +0.96% after all costs |
| costs | PASS | fills 0.68 bps vs assumed 1.32 bps (max x1.25); financing paid -46.62 vs expected 76.67 (paper account doesn't model carry) over 10 weekdays (9 fills) |
| agreement | PASS | practice +0.96% vs paper +1.33% (gap -0.37 pts, max 3) |
| reliability | FAIL | missed weekdays 0; mismatches 1; order problems 2; not halted |
| drawdown | PASS | worst fall -1.3% (limit -20%) |

## Forex learning model: **NOT READY**

| Check | Status | Detail |
|---|---|---|
| duration | WAIT | 1.7 of 26 weeks |
| edge | WAIT | practice return +1.53% after all costs; live IC: 1 week(s) scored |
| costs | FAIL | fills 0.68 bps vs assumed 1.29 bps (max x1.25); financing paid 153.62 vs expected 101.38 over 10 weekdays (11 fills) |
| agreement | PASS | practice +1.53% vs paper +1.85% (gap -0.32 pts, max 3) |
| reliability | PASS | missed weekdays 0; mismatches 0; order problems 0; not halted |
| drawdown | PASS | worst fall -1.3% (limit -20%) |
