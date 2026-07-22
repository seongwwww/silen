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
