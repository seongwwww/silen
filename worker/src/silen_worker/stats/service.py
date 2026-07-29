from dataclasses import dataclass


@dataclass(frozen=True)
class StatsSnapshot:
    confirmed_differences: int
    dismissed_differences: int
    card_differences: int
    active_days: int
    confirmed_diaries: int
    total_diaries: int
    users_three_days: int
    users_seven_days: int


def _percent(numerator: int, denominator: int) -> str:
    if denominator == 0:
        return "집계 전"
    return f"{round(numerator / denominator * 100)}%"


def _average(numerator: int, denominator: int) -> str:
    if denominator == 0:
        return "집계 전"
    return f"{numerator / denominator:.1f}건"


def format_stats(snapshot: StatsSnapshot) -> list[str]:
    """opt-out 지표를 오해하지 않도록 명시적 피드백이라는 뜻을 함께 출력한다."""
    feedback_total = (
        snapshot.confirmed_differences + snapshot.dismissed_differences
    )
    return [
        (
            "명시적 긍정 비율 "
            f"{_percent(snapshot.confirmed_differences, feedback_total)}  "
            f"(confirmed {snapshot.confirmed_differences} / "
            f"dismissed {snapshot.dismissed_differences})"
        ),
        (
            "하루 평균 차이   "
            f"{_average(snapshot.card_differences, snapshot.active_days)}"
        ),
        (
            "일기 확정률      "
            f"{_percent(snapshot.confirmed_diaries, snapshot.total_diaries)}"
        ),
        (
            "관측일수 분포    "
            f"3일+ {snapshot.users_three_days}명 · "
            f"7일+ {snapshot.users_seven_days}명"
        ),
        (
            "설명: 명시적 긍정 비율은 응답한 피드백 안의 비율이며 "
            "카드 전체 정확도가 아닙니다."
        ),
    ]
