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
    log = root / "results" / "alert_log.csv"            # the previous summary failed to send?
    if log.exists():
        rows = log.read_text().strip().splitlines()
        if len(rows) > 1 and ",FAILED" in rows[-1] and not rows[-1].startswith(today):
            out.append("the previous daily alert failed to send: " + rows[-1].split(",FAILED", 1)[1][:160])
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
STRATEGIES = (("trend", "📈 TREND STRATEGY", "paper", "practice_trend"),
              ("ml", "🤖 LEARNING MODEL", "paper_ml", "practice_ml"))


def _money(v: float, ccy: str, signed: bool = False) -> str:
    sign = CURRENCY_SIGN.get(ccy, "")
    s = f"{sign}{abs(v):,.2f}" if sign else f"{abs(v):,.2f} {ccy}"
    if signed:
        return ("+" if v >= 0 else "−") + s
    return s


def _pct(v: float) -> str:
    return ("+" if v >= 0 else "−") + f"{abs(v):.2f}%"


def holding_text(root: Path, paper_dir: str) -> str:
    """What the strategy is betting on, per currency vs USD: '↑ JPY · ↓ EUR, GBP (vs USD)'."""
    import json
    f = root / paper_dir / "state.json"
    if not f.exists():
        return ""
    units = json.loads(f.read_text()).get("units", {})
    up, down = [], []
    for pair, u in units.items():
        if not u:
            continue
        base, quote = pair.split("/")
        ccy, long_ccy = (base, u > 0) if quote == "USD" else (quote, u < 0)   # USD/JPY short = long JPY
        (up if long_ccy else down).append(ccy)
    if not up and not down:
        return "  Holding: nothing (all cash)"
    parts = []
    if up:
        parts.append("↑ " + ", ".join(sorted(up)))
    if down:
        parts.append("↓ " + ", ".join(sorted(down)))
    return "  Holding: " + " · ".join(parts) + " (vs USD)"


def _dot(pct: float | None) -> str:
    if pct is None or abs(pct) < 0.005:
        return "⚪"
    return "🟢" if pct > 0 else "🔴"


def _csv(path: Path):
    import pandas as pd
    return pd.read_csv(path) if path.exists() and path.stat().st_size > 0 else None


def account_stats(values, times, start_value: float, ccy: str, today: str) -> dict | None:
    """Current value, today's change (money and %) and total change since the start."""
    import pandas as pd
    if values is None or len(values) == 0:
        return None
    t = pd.to_datetime(pd.Series(times), utc=True).dt.strftime("%Y-%m-%d").to_numpy()
    v = pd.Series(values).astype(float).to_numpy()
    before = v[t < today]
    prev = before[-1] if len(before) else None
    return {"value": v[-1], "ccy": ccy, "start": start_value,
            "day_abs": (v[-1] - prev) if prev is not None else None,
            "day_pct": (v[-1] / prev - 1) * 100 if prev is not None else None,
            "total_pct": (v[-1] / start_value - 1) * 100}


def account_text(name: str, st: dict | None, missing: str) -> str:
    if st is None:
        return f"  {name}: {missing}"
    if st["day_pct"] is None:
        day = "first day"
    else:
        day = f"{_money(st['day_abs'], st['ccy'], signed=True)} today ({_pct(st['day_pct'])})"
    return (f"  {name}: {_money(st['value'], st['ccy'])}\n"
            f"     {_dot(st['day_pct'])} {day} · total {_pct(st['total_pct'])}")


def trades_text(trades: list[tuple[str, str]]) -> str:
    """[('buy','USD/JPY'), ('sell','EUR/USD')] -> 'bought USD/JPY · sold EUR/USD'"""
    bought = sorted({p for s, p in trades if s == "buy"})
    sold = sorted({p for s, p in trades if s == "sell"})
    parts = []
    if bought:
        parts.append("bought " + ", ".join(bought))
    if sold:
        parts.append("sold " + ", ".join(sold))
    return " · ".join(parts)


def _paper(root: Path, d: str, today: str):
    import json
    st_f, eq = root / d / "state.json", _csv(root / d / "equity.csv")
    if not st_f.exists() or eq is None:
        return None, []
    st = json.loads(st_f.read_text())
    f = _csv(root / d / "fills.csv")
    trades = [] if f is None else [(r["side"], r["pair"]) for _, r in
                                   f[f["time"].astype(str).str.startswith(today)].iterrows()]
    return account_stats(eq["equity"], eq["time"], float(st["initial_capital"]), "USD", today), trades


def _practice(root: Path, d: str, today: str):
    import json
    st_f, eq = root / d / "state.json", _csv(root / d / "equity.csv")
    if not st_f.exists() or eq is None:
        return None, [], ""
    st = json.loads(st_f.read_text())
    f = _csv(root / d / "fills.csv")
    trades = [] if f is None else [("buy" if float(r["units"]) > 0 else "sell", r["pair"]) for _, r in
                                   f[f["time"].astype(str).str.startswith(today) & (f["status"] == "filled")].iterrows()]
    runs = (root / d / "RUNS.md").read_text().splitlines() if (root / d / "RUNS.md").exists() else []
    todays = [l for l in runs if today in l[:16]]
    note = ""
    if todays and "market closed" in todays[-1]:
        note = "market closed"
    elif todays and "not updated recently" in todays[-1]:
        note = "waiting for the paper account"
    return (account_stats(eq["nav"], eq["time"], float(st["start_nav"]), st.get("currency", "USD"), today),
            trades, note)


def strategy_block(root: Path, key: str, title: str, paper_dir: str, prac_dir: str, today: str) -> tuple[str, list]:
    pst, ptr = _paper(root, paper_dir, today)
    qst, qtr, note = _practice(root, prac_dir, today)
    lines = [title,
             account_text("Paper (simulated)", pst, "not started yet"),
             account_text("OANDA practice", qst, "not connected yet")]
    if not ptr and not qtr:
        lines.append("  Trades today: none" + (f" (practice: {note})" if note else ""))
    else:
        if ptr:
            lines.append(f"  Trades today: {trades_text(ptr)}")
        if qst is not None:
            if qtr and set(qtr) == set(ptr):
                lines.append("  Practice: same trades filled at OANDA ✅")
            elif qtr:
                lines.append(f"  Practice trades: {trades_text(qtr)}")
            else:
                lines.append(f"  Practice: no trades ({note or 'nothing needed'})")
    h = holding_text(root, paper_dir)
    if h:
        lines.append(h)
    pcts = [x["day_pct"] for x in (pst, qst) if x and x["day_pct"] is not None]
    return "\n".join(lines), pcts


def gate_text(root: Path) -> str:
    """'🚦 Go-live check: waiting · 3.0 of 26 weeks' per strategy, in plain words."""
    try:
        from .config import load_config
        from .gate import evaluate, verdict
        cfg = load_config(root / "config.toml") if (root / "config.toml").exists() else load_config()
    except Exception:
        return ""
    words = {"WAIT": "⏳ waiting for data", "READY": "✅ READY for a small live trial", "NOT READY": "⛔ not ready"}
    out = ["🚦 GO-LIVE CHECK"]
    for key, name in (("trend", "Trend"), ("ml", "Learning model")):
        try:                                   # a broken section must never stop the daily message
            checks = evaluate(cfg, root, key)
        except Exception as e:
            out.append(f"  {name}: unavailable ({type(e).__name__})")
            continue
        dur = next((c.detail for c in checks if c.name == "duration"), "no practice data yet")
        failed = [c.name for c in checks if c.status == "FAIL"]
        extra = f" · failing: {', '.join(failed)}" if failed else ""
        out.append(f"  {name}: {words[verdict(checks)]} ({dur}){extra}")
    return "\n".join(out)


def daily_summary(root: Path, now: datetime) -> list[str]:
    """Readable blocks for the phone: one per strategy, then the go-live check."""
    today = now.strftime("%Y-%m-%d")
    blocks, pcts = [], []
    for key, title, pd_, qd in STRATEGIES:
        text, p = strategy_block(root, key, title, pd_, qd, today)
        blocks.append(text)
        pcts += p
    g = gate_text(root)
    if g:
        blocks.append(g)
    daily_summary.avg_day_pct = sum(pcts) / len(pcts) if pcts else None
    return blocks


def _check(resp, channel: str) -> None:
    """Raise if the service refused the message (a mock that returns None counts as accepted)."""
    code = getattr(resp, "status_code", 200)
    if code >= 300:
        raise RuntimeError(f"{channel} refused the message: HTTP {code} {getattr(resp, 'text', '')[:200]}")


def send(title: str, body: str, ntfy_topic: str | None = None, webhook: str | None = None,
         post=requests.post, urgent: bool = False) -> list[str]:
    """Send to every configured channel. Raises if any channel fails (the caller logs it).

    ntfy gets JSON, not HTTP headers: header values can't carry emoji (UnicodeEncodeError),
    which is how the daily summaries with a 🟢/🔴/⚠️ title silently failed to send."""
    ntfy_topic = ntfy_topic if ntfy_topic is not None else os.environ.get("ALERT_NTFY_TOPIC", "")
    webhook = webhook if webhook is not None else os.environ.get("ALERT_WEBHOOK_URL", "")
    sent, errors = [], []
    if ntfy_topic:
        try:
            _check(post("https://ntfy.sh/", timeout=20, json={
                "topic": ntfy_topic, "title": title, "message": body,
                "priority": 4 if urgent else 3,
                "tags": ["warning"] if urgent else ["chart_with_upwards_trend"]}), "ntfy")
            sent.append("ntfy")
        except Exception as e:
            errors.append(f"ntfy: {e}")
    if webhook:
        try:
            _check(post(webhook, timeout=20,
                        json={"text": f"*{title}*\n{body}", "content": f"**{title}**\n{body}"}), "webhook")
            sent.append("webhook")
        except Exception as e:
            errors.append(f"webhook: {e}")
    if errors:
        raise RuntimeError("; ".join(errors) + (f" (sent OK: {', '.join(sent)})" if sent else ""))
    return sent


def log_result(root: Path, now: datetime, title: str, result: str) -> None:
    """Keep a record of every send attempt in the repo (results/alert_log.csv)."""
    import csv
    f = root / "results" / "alert_log.csv"
    f.parent.mkdir(exist_ok=True)
    new = not f.exists()
    with open(f, "a", newline="") as fh:
        w = csv.writer(fh)
        if new:
            w.writerow(["time", "title", "result"])
        w.writerow([now.isoformat(timespec="seconds"), title, result])


def run(root: Path, outcomes: dict[str, str], now: datetime | None = None, post=requests.post) -> dict:
    """Daily summary after every run: problems first (high priority), then each strategy's accounts
    (value, today's change, total change, trades), then the go-live check."""
    now = now or datetime.now(timezone.utc)
    probs = problems_today(root, outcomes, now)
    flag = root / "results" / ".gate_changed"                # written by the gate step on a change
    parts = []
    if probs:
        parts.append("⚠️ PROBLEMS\n" + "\n".join(f"  • {p}" for p in probs))
    if flag.exists():
        parts.append(f"🔔 GO-LIVE CHECK CHANGED\n  {flag.read_text()}")
    parts += daily_summary(root, now)
    parts.append("Details: results/GATE.md · paper*/REPORT.md · practice_*/RUNS.md")
    body = "\n\n".join(parts)
    title = headline(now, probs, getattr(daily_summary, "avg_day_pct", None))
    error = None
    try:
        sent = send(title, body, post=post, urgent=bool(probs))
    except Exception as e:                  # recorded and reported, never hidden
        sent, error = [], str(e)[:300]
    configured = bool(os.environ.get("ALERT_NTFY_TOPIC") or os.environ.get("ALERT_WEBHOOK_URL"))
    if configured:
        log_result(root, now, title, f"FAILED: {error}" if error else "sent via " + ", ".join(sent))
    print(f"{title}\n{body}\n" + (f"ALERT FAILED TO SEND: {error}" if error
                                   else f"sent via: {sent or 'nothing configured (printed only)'}"))
    return {"sent": sent, "problems": probs, "message": title, "body": body, "error": error}


def headline(now: datetime, probs: list[str], avg_day_pct: float | None) -> str:
    day = now.strftime("%a %d %b")
    if probs:
        return f"⚠️ FX bot · {day} · {len(probs)} problem(s), please check"
    if avg_day_pct is None:
        return f"FX bot · {day} · daily summary"
    word = "up" if avg_day_pct > 0.005 else "down" if avg_day_pct < -0.005 else "flat"
    return f"FX bot · {day} · {_dot(avg_day_pct)} {word} {abs(avg_day_pct):.2f}% today (avg of accounts)"
