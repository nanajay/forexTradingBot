# Go-live gate

Updated 2026-11-16 07:11 UTC. A strategy is **READY** only when every check passes. **WAIT** means not enough data yet. Thresholds: `config.toml [gate]`. Even READY means only "eligible for a tiny live trial", never "safe".

## Forex trend strategy: **NOT READY**

| Check | Status | Detail |
|---|---|---|
| duration | WAIT | 0.1 of 26 weeks |
| edge | WAIT | practice return -0.03% after all costs |
| costs | PASS | fills 0.68 bps vs assumed 1.30 bps (max x1.25); financing paid -0.00 vs assumed 0.44 (5 fills) |
| agreement | WAIT | paper account has too little history |
| reliability | FAIL | missed weekdays 0; mismatches 1; order problems 2; not halted |
| drawdown | PASS | worst fall -0.0% (limit -20%) |

## Forex learning model: **WAIT**

| Check | Status | Detail |
|---|---|---|
| duration | WAIT | 0.1 of 26 weeks |
| edge | WAIT | practice return -0.06% after all costs; live IC: 0 week(s) scored |
| costs | PASS | fills 0.67 bps vs assumed 1.31 bps (max x1.25); financing paid -0.00 vs assumed 0.68 (6 fills) |
| agreement | PASS | practice -0.06% vs paper +0.14% (gap -0.20 pts, max 3) |
| reliability | PASS | missed weekdays 0; mismatches 0; order problems 0; not halted |
| drawdown | PASS | worst fall -0.1% (limit -20%) |
