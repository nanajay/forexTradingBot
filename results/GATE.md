# Go-live gate

Updated 2026-11-14 17:34 UTC. A strategy is **READY** only when every check passes. **WAIT** means not enough data yet. Thresholds: `config.toml [gate]`. Even READY means only "eligible for a tiny live trial", never "safe".

## Forex trend strategy: **WAIT**

| Check | Status | Detail |
|---|---|---|
| duration | WAIT | 0.0 of 26 weeks |
| edge | WAIT | practice return +0.00% after all costs |
| costs | WAIT | no filled practice orders yet |
| agreement | WAIT | paper account has too little history |
| reliability | PASS | missed weekdays 0; mismatches 0; order problems 0; not halted |
| drawdown | PASS | worst fall 0.0% (limit -20%) |

## Forex learning model: **WAIT**

| Check | Status | Detail |
|---|---|---|
| duration | WAIT | 0.0 of 26 weeks |
| edge | WAIT | practice return +0.00% after all costs; live IC: 0 week(s) scored |
| costs | WAIT | no filled practice orders yet |
| agreement | PASS | practice +0.00% vs paper -0.00% (gap +0.00 pts, max 3) |
| reliability | PASS | missed weekdays 0; mismatches 0; order problems 0; not halted |
| drawdown | PASS | worst fall 0.0% (limit -20%) |
