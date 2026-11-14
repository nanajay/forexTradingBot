"""Alerts: tell the owner when a run fails or something looks wrong, so a broken week doesn't
silently spoil the evidence for the go-live decision.

Channels (set either or both as GitHub secrets; with neither set, alerts are only printed):
  ALERT_NTFY_TOPIC   push notification to a phone through ntfy.sh (free app, no account).
                     Pick a long random topic name: anyone who knows it can read the messages.
  ALERT_WEBHOOK_URL  Slack, Discord or any webhook accepting JSON {"text": ...} / {"content": ...}

After every weekday run (python -m fxbot alert --outcomes "paper=success ml=failure ..."), one message:
  * PROBLEMS first, sent as high priority: a failed workflow step (paper run, model, OANDA practice,
    git push), or in today's practice runs a position MISMATCH, a HALT, rejected/errored orders or a crash
  * then each of the 4 accounts (trend/ML x paper/practice): today's trades, today's change, total value
    and total change since the start
  * then the go-live gate verdicts, flagged when they change
A missing daily message therefore means the workflow itself didn't run.
Messages contain no account ids or tokens.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

import requests


def problems_today(root: Path, outcomes: dict[str, str], now: datetime) -> list[str]:
    out = [f"step '{k}' {v}" for k, v in outcomes.items() if v not in ("success", "skipped", "")]
    today = now.strftime("%Y-%m-%d")
    for s in ("trend", "ml"):
        runs = root / f"practice_{s}" / "RUNS.md"
        if runs.exists():
            for line in runs.read_text().splitlines():
                if today in line[:16] and any(k in line for k in ("MISMATCH", "HALT")):
                    out.append(f"practice {s}: {line[2:260]}")
        log = root / f"practice_{s}" / "last_run.log"
        if log.exists() and "Traceback" in log.read_text():
            last = log.read_text().strip().splitlines()[-1]
            out.append(f"practice {s} crashed: {last[:200]}")
        fills = root / f"practice_{s}" / "fills.csv"
        if fills.exists():
            bad = [l for l in fills.read_text().splitlines()
                   if l.startswith(today) and (",rejected," in l or ",error," in l)]
            if bad:
                out.append(f"practice {s}: {len(bad)} order(s) rejected/errored today")
    ml_log = root / "paper_ml" / "last_run.log"
    if ml_log.exists() and "Traceback" in ml_log.read_text():
        out.append("learning-model paper run crashed: " + ml_log.read_text().strip().splitlines()[-1][:200])
    return out


def gate_summary(root: Path) -> str:
    f = root / "results" / "GATE.md"
    if not f.exists():
        return ""
    heads = [l for l in f.read_text().splitlines() if l.startswith("## ")]
    return "; ".join(h[3:].replace("**", "") for h in heads)


CURRENCY_SIGN = {"USD": "$", "GBP": "£", "EUR": "€"}
MAX_TRADES_LISTED = 7


def _money(v: float, ccy: str) -> str:
    sign = CURRENCY_SIGN.get(ccy, "")
    return f"{sign}{v:,.2f}" if sign else f"{v:,.2f} {ccy}"


def _csv(path: Path):
    import pandas as pd
    return pd.read_csv(path) if path.exists() and path.stat().st_size > 0 else None


def account_line(label: str, values, times, start_value: float, ccy: str, trades: list[str],
                 today: str, note: str = "") -> str:
    """'TREND paper: $9,994.68 · today -0.03% · total -0.05% · 2 trades: buy ...'"""
    import pandas as pd
    if values is None or len(values) == 0:
        return f"{label}: no data yet"
    t = pd.to_datetime(pd.Series(times), utc=True).dt.strftime("%Y-%m-%d").to_numpy()
    v = pd.Series(values).astype(float).to_numpy()
    now_v = v[-1]
    before = v[t < today]
    day = f"today {(now_v / before[-1] - 1) * 100:+.2f}%" if len(before) else "today: first day"
    total = f"total {(now_v / start_value - 1) * 100:+.2f}%"
    if trades:
        shown = trades[:MAX_TRADES_LISTED]
        more = f" (+{len(trades) - len(shown)} more)" if len(trades) > len(shown) else ""
        tr = f"{len(trades)} trade(s): " + "; ".join(shown) + more
    else:
        tr = "no trades" + (f" ({note})" if note else "")
    return f"{label}: {_money(now_v, ccy)} · {day} · {total}\n   {tr}"


def _fmt_units(u) -> str:
    return f"{abs(float(u)):,.0f}"


def daily_summary(root: Path, now: datetime) -> list[str]:
    """One block per account: today's trades, the day's change and the total value."""
    import json
    today = now.strftime("%Y-%m-%d")
    lines = []
    # paper accounts (USD)
    for label, d in (("TREND paper", root / "paper"), ("ML paper", root / "paper_ml")):
        st_f, eq = d / "state.json", _csv(d / "equity.csv")
        if not st_f.exists() or eq is None:
            lines.append(f"{label}: not started")
            continue
        st = json.loads(st_f.read_text())
        f = _csv(d / "fills.csv")
        trades = []
        if f is not None:
            for _, r in f[f["time"].astype(str).str.startswith(today)].iterrows():
                trades.append(f"{r['side']} {_fmt_units(r['units'])} {r['pair']}")
        lines.append(account_line(label, eq["equity"], eq["time"], float(st["initial_capital"]), "USD",
                                  trades, today))
    # OANDA practice accounts (account currency, e.g. GBP)
    for label, d in (("TREND practice", root / "practice_trend"), ("ML practice", root / "practice_ml")):
        st_f, eq = d / "state.json", _csv(d / "equity.csv")
        if not st_f.exists() or eq is None:
            lines.append(f"{label}: not connected")
            continue
        st = json.loads(st_f.read_text())
        f = _csv(d / "fills.csv")
        trades = []
        if f is not None:
            for _, r in f[f["time"].astype(str).str.startswith(today) & (f["status"] == "filled")].iterrows():
                side = "buy" if float(r["units"]) > 0 else "sell"
                trades.append(f"{side} {_fmt_units(r['units'])} {r['pair']} @ {r['price']}")
        note = ""
        runs = (d / "RUNS.md").read_text().splitlines() if (d / "RUNS.md").exists() else []
        todays = [l for l in runs if today in l[:16]]
        if todays and "market closed" in todays[-1]:
            note = "market closed"
        elif todays and "not updated recently" in todays[-1]:
            note = "paper account stale"
        lines.append(account_line(label, eq["nav"], eq["time"], float(st["start_nav"]),
                                  st.get("currency", "USD"), trades, today, note))
    return lines


def send(title: str, body: str, ntfy_topic: str | None = None, webhook: str | None = None,
         post=requests.post, urgent: bool = False) -> list[str]:
    ntfy_topic = ntfy_topic if ntfy_topic is not None else os.environ.get("ALERT_NTFY_TOPIC", "")
    webhook = webhook if webhook is not None else os.environ.get("ALERT_WEBHOOK_URL", "")
    sent = []
    if ntfy_topic:
        headers = {"Title": title, "Tags": "warning" if urgent else "chart_with_upwards_trend"}
        if urgent:
            headers["Priority"] = "high"
        post(f"https://ntfy.sh/{ntfy_topic}", data=body.encode(), timeout=15, headers=headers)
        sent.append("ntfy")
    if webhook:
        post(webhook, json={"text": f"*{title}*\n{body}", "content": f"**{title}**\n{body}"}, timeout=15)
        sent.append("webhook")
    return sent


def run(root: Path, outcomes: dict[str, str], now: datetime | None = None, post=requests.post) -> dict:
    """Daily summary after every run: problems first (high priority), then each account's trades,
    day change and total value, then the go-live gate."""
    now = now or datetime.now(timezone.utc)
    probs = problems_today(root, outcomes, now)
    gate = gate_summary(root)
    flag = root / "results" / ".gate_changed"                # written by the gate step on a change
    parts = []
    if probs:
        parts.append("PROBLEMS:\n" + "\n".join(f"- {p}" for p in probs))
    parts.append("\n".join(daily_summary(root, now)))
    if flag.exists():
        parts.append(f"GATE CHANGED: {flag.read_text()}")
    elif gate:
        parts.append(f"Gate: {gate}")
    body = "\n\n".join(parts)
    day = now.strftime("%a %d %b")
    title = f"FX bot {day}: PROBLEM in today's run" if probs else \
        (f"FX bot {day}: go-live gate changed" if flag.exists() else f"FX bot {day}: daily summary")
    try:
        sent = send(title, body, post=post, urgent=bool(probs))
    except Exception as e:                                   # never fail the workflow over an alert
        sent = [f"failed: {e}"]
    print(f"{title}\n{body}\nsent via: {sent or 'nothing configured (printed only)'}")
    return {"sent": sent, "problems": probs, "message": title, "body": body}
