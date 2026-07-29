import json
from datetime import datetime
from pathlib import Path

import pytest

from silen_worker.time import local_date_for

FIXTURE_PATH = Path(__file__).resolve().parents[2] / "fixtures" / "day-boundary.json"
CASES = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))["cases"]


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["name"])
def test_local_date_matches_golden_fixture(case):
    instant = datetime.fromisoformat(case["instant"])
    assert local_date_for(instant, case["timezone"]) == case["expectedLocalDate"]


def test_seoul_midnight_boundary_splits_two_local_dates():
    before = datetime.fromisoformat("2026-07-28T14:59:59+00:00")
    after = datetime.fromisoformat("2026-07-28T15:00:00+00:00")

    assert local_date_for(before, "Asia/Seoul") == "2026-07-28"
    assert local_date_for(after, "Asia/Seoul") == "2026-07-29"


def test_same_utc_instant_is_a_different_date_for_two_timezones():
    instant = datetime.fromisoformat("2026-07-29T03:00:00+00:00")

    assert local_date_for(instant, "Asia/Seoul") == "2026-07-29"
    assert local_date_for(instant, "America/Los_Angeles") == "2026-07-28"
