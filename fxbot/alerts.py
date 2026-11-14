"""Alerts: tell the owner when a run fails or something looks wrong, so a broken week doesn't
silently spoil the evidence for the go-live decision.

Channels (set either or both as GitHub secrets; with neither set, alerts are only printed):
  ALERT_NTFY_TOPIC   push notification to a phone through ntfy.sh (free app, no account).
                     Pick a long random topic name: anyone who knows it can read the messages.
  ALERT_WEBHOOK_URL  Slack, Discord or any webhook accepting JSON {"text": ...} / {"content": ...}

What triggers an alert (python -m fxbot alert --outcomes "paper=success ml=failure ..."):
  * any workflow step that failed (the paper run, the model, OANDA practice, the git push)
  * in today's practice runs: a position MISMATCH, a HALT, rejected/errored orders, or a crash
  * the go-live gate turning NOT READY or READY (a change worth a look either way)
Plus a short "all OK" summary on Mondays, so silence never hides a dead workflow.
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


def send(title: str, body: str, ntfy_topic: str | None = None, webhook: str | None = None,
         post=requests.post) -> list[str]:
    ntfy_topic = ntfy_topic if ntfy_topic is not None else os.environ.get("ALERT_NTFY_TOPIC", "")
    webhook = webhook if webhook is not None else os.environ.get("ALERT_WEBHOOK_URL", "")
    sent = []
    if ntfy_topic:
        post(f"https://ntfy.sh/{ntfy_topic}", data=body.encode(), timeout=15,
             headers={"Title": title, "Tags": "chart_with_downwards_trend"})
        sent.append("ntfy")
    if webhook:
        post(webhook, json={"text": f"*{title}*\n{body}", "content": f"**{title}**\n{body}"}, timeout=15)
        sent.append("webhook")
    return sent


def run(root: Path, outcomes: dict[str, str], now: datetime | None = None, post=requests.post) -> dict:
    now = now or datetime.now(timezone.utc)
    probs = problems_today(root, outcomes, now)
    gate = gate_summary(root)
    flag = root / "results" / ".gate_changed"                # written by the gate step on a change
    gate_changed = flag.exists()
    if probs:
        title, body = "FX bot: problem in today's run", "\n".join(f"- {p}" for p in probs)
    elif gate_changed:
        title, body = "FX bot: go-live gate changed", flag.read_text()
    elif now.weekday() == 0:
        title, body = "FX bot: weekly check-in, all runs OK", gate or "gate not computed yet"
    else:
        print("alerts: no problems today, nothing sent")
        return {"sent": [], "problems": [], "message": "nothing to report"}
    body += "\n(see results/GATE.md, paper*/REPORT.md, practice_*/RUNS.md)"
    try:
        sent = send(title, body, post=post)
    except Exception as e:                                   # never fail the workflow over an alert
        sent = [f"failed: {e}"]
    print(f"{title}\n{body}\nsent via: {sent or 'nothing configured (printed only)'}")
    return {"sent": sent, "problems": probs, "message": title}
