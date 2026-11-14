"""CLI: python -m fxbot <command>"""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from .config import ROOT, load_config, pair_symbols


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="fxbot", description="Forex trend bot (paper trading only)")
    ap.add_argument("--config", default=None)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("backtest", help="Full-history backtest -> results/BACKTEST.md")
    pp = sub.add_parser("paper", help="Paper account")
    pp.add_argument("action", choices=["run", "status", "report"])
    pp.add_argument("--state", default=str(ROOT / "paper"))
    mp = sub.add_parser("ml", help="Learning-model paper account (weekly retrain)")
    mp.add_argument("action", choices=["run", "status", "report"])
    mp.add_argument("--state", default=str(ROOT / "paper_ml"))
    mp.add_argument("--trend-state", default=str(ROOT / "paper"))
    sub.add_parser("signals", help="Print today's signal per pair (no trading)")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    cfg = load_config(args.config)

    if args.cmd == "backtest":
        from .data import load_closes
        from .report import backtest_report
        closes = load_closes(pair_symbols(cfg))
        md = backtest_report(closes, cfg, ROOT / "results")
        print(md.split("## Robustness")[0])
    elif args.cmd == "signals":
        from .data import load_closes
        from .strategy import rule_weights
        closes = load_closes(pair_symbols(cfg), start="2024-01-01")
        st = cfg["strategy"]
        print(f"signal day {closes.index[-1].date()} ({st['mode']})")
        for p in closes:
            w = rule_weights(closes[p].dropna(), "blend", st["mode"], tuple(st["sma"]), tuple(st["mom"]))
            print(f"  {p}: {w.iloc[-1]:+.2f}")
    elif args.cmd == "ml":
        from . import ml_paper
        state = Path(args.state)
        if args.action == "run":
            out = ml_paper.run(cfg, state)
            print(json.dumps(out, indent=1, default=str))
        elif args.action == "status":
            print(ml_paper.status(state))
        else:
            print(ml_paper.report(cfg, state, Path(args.trend_state)))
    elif args.cmd == "paper":
        from . import paper
        state = Path(args.state)
        if args.action == "run":
            out = paper.run_daily(cfg, state)
            print(json.dumps({k: out[k] for k in ("log", "already_processed", "fills")}, indent=1))
        elif args.action == "status":
            print(paper.status(cfg, state))
        else:
            from .report import paper_report
            print(paper_report(cfg, state))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
