import pytest

from silen_worker.narration.service import NarrationInput, build_prompt, guardrail


def _facts(**kw):
    base = dict(
        difference_id="d1",
        user_id="u1",
        entity_id="e1",
        entity_name="김밥",
        entity_type="thing",
        detection_method="freq_shift",
        description="최근 활성일 4일 중 3일 기록됨, 오늘 기록에는 언급 없음",
        date_iso="2026-07-24",
        dimension="thing",
        evidence_ids=("m1", "m2"),
    )
    base.update(kw)
    return NarrationInput(**base)


def _emotion_facts(**kw):
    base = dict(
        entity_name=None,
        entity_type=None,
        entity_id=None,
        dimension="emotion",
        detection_method="zscore",
        description="최근 5일 평균 0.20, 오늘 -0.60 (z=-3.2)",
        evidence_ids=("m1", "m2", "m3"),
    )
    base.update(kw)
    return _facts(**base)


def _raw(
    headline="김밥 언급의 변화",
    body="최근 활성 기록에 자주 있던 김밥이 오늘 기록에는 없었어요.",
    evidence_text="최근 활성일 4일 중 3일에 기록돼 있어 찾았어요.",
):
    return {"headline": headline, "body": body, "evidence_text": evidence_text}


def test_정상_출력은_통과한다():
    out = guardrail(_raw(), _facts())
    assert out is not None
    assert out.headline == "김밥 언급의 변화"


def test_엔티티명_없는_출력은_폐기한다():
    # headline+body 어디에도 '김밥'이 없으면 그 차이를 가리키지 않는다.
    out = guardrail(_raw(headline="오늘의 반복", body="비슷한 게 이어졌어요."), _facts())
    assert out is None


def test_조언_표현은_폐기한다():
    out = guardrail(
        _raw(body="김밥을 자주 드시네요. 내일은 다른 걸 해보세요."),
        _facts(),
    )
    assert out is None


def test_인과_창작은_폐기한다():
    out = guardrail(
        _raw(body="김밥 언급이 달라진 건 바빴기 때문에 그런 거예요."),
        _facts(),
    )
    assert out is None


def test_빈_필드는_폐기한다():
    out = guardrail(_raw(evidence_text="  "), _facts())
    assert out is None


def test_길이_초과는_폐기한다():
    out = guardrail(_raw(headline="김밥" * 30), _facts())
    assert out is None


def test_비문자열_필드는_크래시없이_처리한다():
    # raw가 JSON 숫자 등 비문자열 값을 담고 있어도(예: headline이 int) 가드레일은
    # AttributeError로 죽지 않고 str()로 강건하게 변환해 정상 처리해야 한다.
    raw = {
        "headline": 5,
        "body": "최근 활성 기록에 자주 있던 김밥이 오늘 기록에는 없었어요.",
        "evidence_text": "최근 기록과 비교해 찾았어요.",
    }
    out = guardrail(raw, _facts())  # 크래시하지 않는 것 자체가 핵심 검증
    assert out is not None
    assert out.headline == "5"


def test_모든_필드가_비문자열이어도_크래시없이_폐기한다():
    raw = {"headline": 5, "body": 10, "evidence_text": None}
    out = guardrail(raw, _facts())
    assert out is None


def test_프롬프트에_본문은_없고_사실은_있다():
    p = build_prompt(_facts())
    assert "김밥" in p
    assert "최근 활성일 4일 중 3일 기록됨" in p
    assert "2026-07-24" in p
    assert "근거 ID: m1, m2" in p


def test_엔티티_차이는_이름과_유형을_프롬프트에_유지한다():
    prompt = build_prompt(_facts())

    assert "엔티티: 김밥 (thing)" in prompt
    assert "반드시 엔티티 이름을 넣어라" in prompt
    assert "차원: 감정 기록" not in prompt


def test_엔티티_차이에_이름이_없으면_출력을_폐기한다():
    facts = _facts(entity_name=None)

    assert guardrail(_raw(), facts) is None


def test_근거_id가_없으면_프롬프트를_만들지_않는다():
    with pytest.raises(ValueError):
        build_prompt(_facts(evidence_ids=()))


def test_감정_프롬프트는_엔티티_대신_감정_차원과_수치_근거만_쓴다():
    prompt = build_prompt(_emotion_facts())

    assert "차원: 감정 기록" in prompt
    assert "최근 5일 평균 0.20, 오늘 -0.60 (z=-3.2)" in prompt
    assert "근거 ID: m1, m2, m3" in prompt
    assert "엔티티:" not in prompt
    assert "None" not in prompt
    assert "원인·위로·권유를 만들지 마라" in prompt


def test_감정_출력은_엔티티명_없이도_통과한다():
    raw = _raw(
        headline="감정 기록의 차이",
        body="최근 감정 기록 평균보다 오늘 값이 낮았어요.",
        evidence_text="최근 5일 평균 0.20과 오늘 -0.60을 비교했어요.",
    )

    assert guardrail(raw, _emotion_facts()) is not None


@pytest.mark.parametrize(
    "body",
    [
        "많이 힘드시겠어요.",
        "괜찮아요. 잘 이겨낼 수 있어요.",
        "오늘은 우울한 하루였어요.",
        "스트레스 때문에 감정 값이 낮아졌어요.",
        "잠시 쉬어가세요.",
    ],
)
def test_감정_출력의_위로_해석_인과_조언은_폐기한다(body: str):
    raw = _raw(
        headline="감정 기록의 차이",
        body=body,
        evidence_text="최근 감정 기록과 오늘 값을 비교했어요.",
    )

    assert guardrail(raw, _emotion_facts()) is None


def test_감정_출력에_description에_없는_수치를_만들면_폐기한다():
    raw = _raw(
        headline="감정 기록의 차이",
        body="최근 평균 0.20보다 오늘 값이 -0.90으로 낮았어요.",
        evidence_text="최근 5일 기록과 비교했어요.",
    )

    assert guardrail(raw, _emotion_facts()) is None
