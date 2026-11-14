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
    pr = sub.add_parser("practice", help="Mirror a paper account onto an OANDA PRACTICE account")
    pr.add_argument("action", choices=["run", "status", "accounts", "check"])
    pr.add_argument("--strategy", choices=["trend", "ml"], default="trend")
    pr.add_argument("--dry-run", action="store_true", help="plan orders but don't send them")
    sub.add_parser("gate", help="Score both strategies against the go-live gate -> results/GATE.md")
    al = sub.add_parser("alert", help="Send an alert if today's run had problems")
    al.add_argument("--outcomes", default="", help='e.g. "paper=success ml=failure practice=success"')
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
    elif args.cmd == "gate":
        from .gate import report
        print(report(cfg, ROOT))
    elif args.cmd == "alert":
        from .alerts import run as alert_run
        outcomes = dict(kv.split("=", 1) for kv in args.outcomes.split() if "=" in kv)
        alert_run(ROOT, outcomes)
    elif args.cmd == "practice":
        import os
        from . import practice
        from .oanda import OandaPractice
        paper_dir = ROOT / ("paper" if args.strategy == "trend" else "paper_ml")
        out_dir = ROOT / f"practice_{args.strategy}"
        if args.action == "accounts":
            for a in OandaPractice().accounts():
                print(a["id"], a.get("tags", []))
        elif args.action == "check":
            from .oanda import instrument
            print(practice.check(OandaPractice(),
                                 {"trend": os.environ.get("OANDA_ACCOUNT_TREND", ""),
                                  "ml": os.environ.get("OANDA_ACCOUNT_ML", "")},
                                 [instrument(p) for p in cfg["pairs"]]))
        elif args.action == "status":
            print(practice.status(out_dir, cfg))
        else:
            var = f"OANDA_ACCOUNT_{args.strategy.upper()}"
            account = os.environ.get(var, "")
            if not account:
                print(f"skipped: {var} is not set (no practice account for the {args.strategy} strategy)")
                return 0
            out = practice.run(cfg, args.strategy, paper_dir, out_dir, account, dry_run=args.dry_run)
            print(out["log"])
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
