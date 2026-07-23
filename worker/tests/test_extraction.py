from silen_worker.extraction.service import normalize_name, guardrail


def test_원문에_있는_이름은_통과한다():
    out = guardrail([{"type": "person", "name": "민수"}], "민수랑 점심 먹음")
    assert len(out) == 1
    assert out[0].type == "person"
    assert out[0].name == "민수"


def test_원문에_없는_이름은_폐기한다():
    # LLM이 "스벅"을 "스타벅스"로 확장 → 원문에 없으니 폐기(추출자이지 해석자 아님).
    out = guardrail([{"type": "place", "name": "스타벅스"}], "스벅에서 커피")
    assert out == []


def test_스키마_밖_type은_폐기한다():
    out = guardrail([{"type": "emotion", "name": "행복"}], "행복했다")
    assert out == []


def test_빈_후보는_빈_결과():
    assert guardrail([], "아무 텍스트") == []


def test_normalize는_보수적이다():
    # 공백 제거·소문자화 정도만. 과병합 금지.
    assert normalize_name("스타 벅스") == normalize_name("스타벅스")
    assert normalize_name("Cafe") == normalize_name("cafe")
    # 다른 이름은 다른 키(김민수 ≠ 민수).
    assert normalize_name("김민수") != normalize_name("민수")


def test_정규화된_이름이_결과에_담긴다():
    out = guardrail([{"type": "place", "name": "스타 벅스"}], "스타 벅스 감")
    assert out[0].normalized_name == "스타벅스"


def test_공백뿐인_이름은_폐기한다():
    assert guardrail([{"type": "person", "name": "   "}], "누군가 있었다") == []


def test_문자열이_아닌_이름은_폐기한다():
    # 원시 LLM 출력의 신뢰 경계 — 스키마가 깨진 후보는 크래시가 아니라 폐기.
    assert guardrail([{"type": "person", "name": 123}], "123 어쩌고") == []


def test_같은_엔티티_중복은_한_번만():
    out = guardrail(
        [{"type": "thing", "name": "김밥"}, {"type": "thing", "name": "김밥"}],
        "김밥 김밥 또 김밥",
    )
    assert len(out) == 1


def test_빈_이름은_폐기한다():
    assert guardrail([{"type": "place", "name": ""}], "장소 없음") == []
