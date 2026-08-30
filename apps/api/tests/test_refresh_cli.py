"""Phase 18: cooldown-aware refresh CLI contract."""
from __future__ import annotations

import datetime as dt

import pytest

from scripts.refresh import refresh_all


def test_unknown_job_errors():
    with pytest.raises(SystemExit):
        refresh_all.main(["--only", "nope"])


def test_cooldown_skips_recent_success(monkeypatch):
    now = dt.datetime.now(dt.timezone.utc)
    monkeypatch.setattr(refresh_all, "_last_success", lambda job: now)
    monkeypatch.setattr(refresh_all.JOB_BY_KEY["prices_mirror"], "run", lambda: (_ for _ in ()).throw(AssertionError("should not run")))
    assert refresh_all.main(["--only", "prices_mirror"]) == 0


def test_force_bypasses_cooldown(monkeypatch):
    now = dt.datetime.now(dt.timezone.utc)
    monkeypatch.setattr(refresh_all, "_last_success", lambda job: now)
    calls = []
    monkeypatch.setattr(refresh_all.JOB_BY_KEY["weather_era5"], "run",
                        lambda: (calls.append(1) or 0))
    assert refresh_all.main(["--only", "weather_era5", "--force"]) == 0
    assert calls == [1]


def test_failed_job_returns_nonzero(monkeypatch):
    monkeypatch.setattr(refresh_all, "_last_success", lambda job: None)
    monkeypatch.setattr(refresh_all.JOB_BY_KEY["prices_official"], "run",
                        lambda: (_ for _ in ()).throw(SystemExit("2")))
    assert refresh_all.main(["--only", "prices_official"]) == 1


def test_historical_census_never_runs():
    assert refresh_all.JOB_BY_KEY["census"].run is None
    assert refresh_all.main(["--only", "census"]) == 0
