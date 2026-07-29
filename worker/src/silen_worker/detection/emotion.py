"""감정 valence의 일별 평균이 최근 기록 범위에서 벗어났는지 계산한다.

DB·LLM을 모르는 순수 함수다. 호출자가 넘긴 창 안에서 target 이전 감정 활성일을
baseline으로 삼고, 같은 날짜의 여러 감정은 먼저 평균한다.
"""

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from math import isclose, isfinite, log2
from statistics import NormalDist, fmean, pstdev
from typing import Iterable


MIN_BASELINE_DAYS = 5
SD_FLOOR = 0.25
P_FLOOR = 2**-8
CONTINUATION_BITS_MIN = 2.0
ZERO_ABS_TOLERANCE = 1e-12

# 사용자가 실제로 누른 라벨. valence는 내부 표현이므로 서술로 새어나가면 안 된다.
LABEL_THRESHOLD = 1 / 3
GOOD, NEUTRAL, BAD = "좋음", "그냥", "별로"


def emotion_label(value: float) -> str:
    if value > LABEL_THRESHOLD:
        return GOOD
    if value < -LABEL_THRESHOLD:
        return BAD
    return NEUTRAL


def bits_ceiling(days: int) -> float:
    """엔티티 축과 같은 상한. 두 축을 같은 자로 재기 위한 것이다.

    엔티티 축의 최대 놀라움은 Jeffreys 평활 때문에 log2(2*(n+1))로 묶여 있다.
    정규분포 꼬리는 상한이 없어 그대로 두면 감정이 늘 1위를 차지하고 하루 상한
    3개를 잠식한다. 데이터가 뒷받침하는 것 이상을 주장하지 않게 같은 천장을 씌운다.
    """
    return log2(2 * (days + 1))


@dataclass(frozen=True)
class EmotionDifference:
    method: str
    category: str
    description: str
    confidence: float
    z_score: float
    baseline_mean: float
    today_mean: float
    baseline_days: int
    entity_id: None = None
    dimension: str = "emotion"


@dataclass(frozen=True)
class _Score:
    mean: float
    value: float
    z: float
    bits: float
    days: int


def _score(value: float, baseline: list[float]) -> _Score | None:
    if len(baseline) < MIN_BASELINE_DAYS:
        return None

    mean = fmean(baseline)
    sd = pstdev(baseline)
    z = (value - mean) / max(sd, SD_FLOOR)
    if isclose(z, 0.0, abs_tol=ZERO_ABS_TOLERANCE):
        return None

    p = 2 * (1 - NormalDist().cdf(abs(z)))
    bits = min(bits_ceiling(len(baseline)), -log2(max(p, P_FLOOR)))
    return _Score(mean=mean, value=value, z=z, bits=bits, days=len(baseline))


def _same_direction_continuation(
    daily: dict[date, float],
    target_date: date,
    current: _Score,
) -> bool:
    """어제 이미 같은 방향의 의미 있는 이탈이었다면 오늘 카드는 만들지 않는다.

    연속 신호 자체는 버리는 것이 아니라 주간 집계가 다룬다. 달력상 어제가 아닌
    마지막 활성일을 쓰면 기록 공백 뒤 재등장까지 연속으로 오인하므로 정확히
    target-1만 본다.
    """

    previous_date = target_date - timedelta(days=1)
    previous_value = daily.get(previous_date)
    if previous_value is None:
        return False

    previous_baseline = [
        value for local_date, value in daily.items() if local_date < previous_date
    ]
    previous = _score(previous_value, previous_baseline)
    if previous is None:
        return False

    return (
        current.bits >= CONTINUATION_BITS_MIN
        and previous.bits >= CONTINUATION_BITS_MIN
        and current.z * previous.z > 0
    )


def detect_emotion_difference(
    entries: Iterable[tuple[date, float]],
    target_date: date,
) -> EmotionDifference | None:
    """target_date의 감정 변화 1건 또는 None을 반환한다.

    confidence에는 다른 detector와 함께 정렬할 수 있도록 양측 꼬리확률을 변환한
    surprisal bits를 그대로 넣는다.
    """

    grouped: dict[date, list[float]] = defaultdict(list)
    for local_date, valence in entries:
        if local_date <= target_date and isfinite(valence):
            grouped[local_date].append(valence)

    daily = {
        local_date: fmean(values)
        for local_date, values in grouped.items()
        if values
    }
    today = daily.get(target_date)
    if today is None:
        return None

    baseline = [
        value for local_date, value in daily.items() if local_date < target_date
    ]
    score = _score(today, baseline)
    if score is None or _same_direction_continuation(daily, target_date, score):
        return None

    counts = Counter(emotion_label(value) for value in baseline)
    tally = "·".join(
        f"{label} {counts[label]}일"
        for label in (GOOD, NEUTRAL, BAD)
        if counts[label]
    )

    return EmotionDifference(
        method="zscore",
        category="감정전환",
        # 서술자에게 넘어가는 문장이다. valence 수치를 넣으면 사용자가 누른 적
        # 없는 "-1.00" 같은 값이 화면에 그대로 나온다. 라벨로만 말한다.
        description=(
            # 이 설명은 과거 날짜로도 다시 계산된다. "오늘"이라 쓰면 주간
            # 리포트가 지난 날을 오늘이라 부르게 된다.
            f"최근 감정을 남긴 {score.days}일은 {tally}, "
            f"이 날은 '{emotion_label(score.value)}'"
        ),
        confidence=score.bits,
        z_score=score.z,
        baseline_mean=score.mean,
        today_mean=score.value,
        baseline_days=score.days,
    )
