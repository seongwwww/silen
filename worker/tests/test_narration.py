from silen_worker.narration.service import NarrationInput, build_prompt, guardrail


def _facts(**kw):
    base = dict(
        difference_id="d1", user_id="u1", entity_name="김밥", entity_type="thing",
        detection_method="freq_shift", description="최근 3일 연속 등장", date_iso="2026-07-24",
    )
    base.update(kw)
    return NarrationInput(**base)


def _raw(headline="3일째 김밥", body="김밥을 최근 3일 연속으로 남기셨네요.",
         evidence_text="요즘 자주 등장해서 찾았어요."):
    return {"headline": headline, "body": body, "evidence_text": evidence_text}


def test_정상_출력은_통과한다():
    out = guardrail(_raw(), _facts())
    assert out is not None
    assert out.headline == "3일째 김밥"


def test_엔티티명_없는_출력은_폐기한다():
    # headline+body 어디에도 '김밥'이 없으면 그 차이를 가리키지 않는다.
    out = guardrail(_raw(headline="오늘의 반복", body="비슷한 게 이어졌어요."), _facts())
    assert out is None


def test_조언_표현은_폐기한다():
    out = guardrail(_raw(body="김밥을 자주 드시네요. 내일은 다른 걸 해보세요."), _facts())
    assert out is None


def test_인과_창작은_폐기한다():
    out = guardrail(_raw(body="김밥을 3일 연속 먹은 건 바빴기 때문에 그런 거예요."), _facts())
    assert out is None


def test_빈_필드는_폐기한다():
    out = guardrail(_raw(evidence_text="  "), _facts())
    assert out is None


def test_길이_초과는_폐기한다():
    out = guardrail(_raw(headline="김밥" * 30), _facts())
    assert out is None


def test_프롬프트에_본문은_없고_사실은_있다():
    p = build_prompt(_facts())
    assert "김밥" in p
    assert "최근 3일 연속 등장" in p
    assert "2026-07-24" in p
