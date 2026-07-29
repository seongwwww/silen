"""활성 기록일을 기준으로 엔티티 관측의 놀라움(bits)을 계산한다."""

from math import log2


def jeffreys_probability(active_days: int, seen_days: int) -> float:
    """과거 활성일 n 중 엔티티가 보인 날 k의 평활 등장확률을 반환한다.

    달력 경과일이 아닌 실제 기록이 있던 날만 ``active_days``에 포함한다.
    Jeffreys 평활로 이력이 비었거나 매번 등장한 경우에도 확률이 0 또는 1이
    되지 않는다.
    """
    if active_days < 0:
        raise ValueError("active_days must be non-negative")
    if seen_days < 0 or seen_days > active_days:
        raise ValueError("seen_days must be between 0 and active_days")

    return (seen_days + 0.5) / (active_days + 1)


def bits_present(probability: float) -> float:
    """확률 ``probability``인 엔티티가 등장했을 때의 놀라움을 반환한다."""
    _validate_probability(probability)
    return -log2(probability)


def bits_absent(probability: float) -> float:
    """등장확률 ``probability``인 엔티티가 언급되지 않았을 때의 놀라움을 반환한다."""
    _validate_probability(probability)
    return -log2(1 - probability)


def surprisal_bits(
    active_days: int,
    seen_days: int,
    present_today: bool,
) -> float:
    """과거 활성 기록과 오늘 관측 여부를 한 번에 bits로 환산한다."""
    probability = jeffreys_probability(active_days, seen_days)
    return (
        bits_present(probability)
        if present_today
        else bits_absent(probability)
    )


def _validate_probability(probability: float) -> None:
    if not 0 < probability < 1:
        raise ValueError("probability must be between 0 and 1")

