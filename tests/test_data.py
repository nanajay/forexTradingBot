from datetime import datetime, timezone

import pandas as pd

from fxbot.data import clean_spikes, closed_only, parse_chart


def test_parse_and_closed_only_drop_forming_day_and_weekends():
    # Thu 12 Nov, Fri 13 Nov, Sat 14 Nov (weekend quote, intraday timestamp), plus a duplicate Fri
    ts = [1794441600, 1794528000, 1794528000 + 3600, 1794652068]
    res = {"timestamp": ts, "indicators": {"quote": [{"close": [1.10, 1.11, 1.12, 1.13]}]}}
    s = parse_chart(res)
    assert list(s.index.day) == [12, 13, 14]
    assert s.iloc[1] == 1.12                 # duplicate day keeps the last quote
    out = closed_only(s, now=datetime(2026, 11, 14, 15, tzinfo=timezone.utc))
    assert list(out.index.day) == [12, 13]                     # Saturday dropped
    out = closed_only(s, now=datetime(2026, 11, 13, 15, tzinfo=timezone.utc))
    assert list(out.index.day) == [12]                         # Friday still forming


def test_clean_spikes_removes_reverting_tick_but_keeps_real_shock():
    s = pd.Series([1.00, 1.00, 1.17, 1.00, 1.00, 0.85, 0.86, 0.86])
    out = clean_spikes(s)
    assert out.iloc[2] == 1.00                                  # bad tick replaced
    assert out.iloc[5] == 0.85                                  # shock that sticks is kept
