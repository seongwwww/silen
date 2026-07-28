from silen_worker.diary.service import (
    DiaryDifference, DiaryInput, DiaryMemory, build_prompt, guardrail,
)


def _facts(memories=None, differences=None):
    if memories is None:
        memories = [DiaryMemory("m1", "점심 김밥"), DiaryMemory("m2", "오늘 좀 일찍 나옴")]
    if differences is None:
        differences = [DiaryDifference("d1", "평소보다 일찍 퇴근", "퇴근")]
    return DiaryInput("2026-07-24", "u1", memories, differences)


def _raw(one_line="비슷한 하루, 그래도 조금 일찍.",
         body="특별할 것 없는 하루였다. 점심은 김밥. 오늘은 조금 일찍 퇴근했다.",
         used_memory_ids=None, used_difference_ids=None):
    return {
        "one_line": one_line, "body": body,
        "used_memory_ids": ["m1", "m2"] if used_memory_ids is None else used_memory_ids,
        "used_difference_ids": ["d1"] if used_difference_ids is None else used_difference_ids,
    }


def test_정상_출력은_통과한다():
    out = guardrail(_raw(), _facts())
    assert out is not None
    assert out.one_line.startswith("비슷한")
    assert out.used_memory_ids == ["m1", "m2"]


def test_입력_밖_메모id는_폐기한다():
    out = guardrail(_raw(used_memory_ids=["m1", "m99"]), _facts())
    assert out is None


def test_입력_밖_차이id는_폐기한다():
    out = guardrail(_raw(used_difference_ids=["dX"]), _facts())
    assert out is None


def test_body있는데_근거메모_없으면_폐기():
    out = guardrail(_raw(used_memory_ids=[]), _facts())
    assert out is None


def test_조언_표현은_폐기한다():
    out = guardrail(_raw(body="오늘은 김밥을 먹었다. 내일은 다른 걸 해보세요."), _facts())
    assert out is None


def test_인과_창작은_폐기한다():
    out = guardrail(_raw(body="일찍 나온 건 바빴기 때문에 그런 거다."), _facts())
    assert out is None


def test_빈_출력은_폐기한다():
    out = guardrail(_raw(body="  "), _facts())
    assert out is None


def test_비문자열_출력도_크래시없이_폐기():
    out = guardrail({"one_line": 5, "body": "x", "used_memory_ids": [], "used_difference_ids": []}, _facts())
    assert out is None


def test_차이없는_평범한날도_통과():
    out = guardrail(_raw(used_difference_ids=[]), _facts(differences=[]))
    assert out is not None
    assert out.used_difference_ids == []


def test_프롬프트에_메모본문과_차이가_들어간다():
    p = build_prompt(_facts())
    assert "점심 김밥" in p
    assert "평소보다 일찍 퇴근" in p
    assert "2026-07-24" in p


def test_프롬프트에_톤프리셋과_주문이_들어간다():
    facts = DiaryInput(
        "2026-07-24",
        "u1",
        [DiaryMemory("m1", "점심 김밥")],
        [],
        tone_preset="따뜻",
        tone_instruction="더 짧게",
    )
    p = build_prompt(facts)
    assert "톤: 따뜻" in p
    assert "이번 요청: 더 짧게" in p


def test_메타_서술은_폐기한다():
    out = guardrail(_raw(body="일기에 출근이라는 행동이 기록된 것도 오늘이 처음이다."), _facts())
    assert out is None


def test_단어를_기록했다는_표현도_폐기한다():
    out = guardrail(_raw(body="시간이라는 단어를 남긴 것은 오늘이 처음이다."), _facts())
    assert out is None


def test_쓴_차이의_표현을_바꾸면_폐기한다():
    # 입력 엔티티명은 '퇴근'인데 본문이 다른 말로 바꿔 쓰면 안 된다.
    out = guardrail(
        _raw(body="오늘은 평소보다 일찍 회사를 나왔다.", used_difference_ids=["d1"]),
        _facts(),
    )
    assert out is None


def test_쓴_차이의_표현을_그대로_쓰면_통과한다():
    out = guardrail(
        _raw(body="오늘은 평소보다 일찍 퇴근을 했다.", used_difference_ids=["d1"]),
        _facts(),
    )
    assert out is not None


def test_zscore_감정_차이는_엔티티_없이_본문에_쓸_수_있다():
    emotion = DiaryDifference(
        "d2",
        "최근 감정 기록 평균보다 오늘 값이 낮음",
        entity_name=None,
        entity_type=None,
        detection_method="zscore",
    )
    facts = _facts(differences=[emotion])
    out = guardrail(
        _raw(
            body="최근 감정 기록 평균보다 오늘 값이 낮았다.",
            used_difference_ids=["d2"],
        ),
        facts,
    )

    assert out is not None
    assert out.used_difference_ids == ["d2"]


def test_감정_차이_프롬프트에는_None_대신_감정_차원이라고_쓴다():
    emotion = DiaryDifference(
        "d2",
        "최근 5일 평균 0.40, 오늘 -0.60 (z=-4.0)",
        entity_name=None,
        entity_type=None,
        detection_method="zscore",
    )

    prompt = build_prompt(_facts(differences=[emotion]))

    assert "차원: 감정 기록" in prompt
    assert "None" not in prompt


def test_first_occurrence는_본문용_차이로_사용할_수_없다():
    first = DiaryDifference(
        "d3",
        "지은 처음 등장",
        entity_name="지은",
        entity_type="person",
        detection_method="first_occurrence",
    )

    out = guardrail(
        _raw(body="지은을 만났다.", used_difference_ids=["d3"]),
        _facts(differences=[first]),
    )

    assert out is None
    assert "지은 처음 등장" not in build_prompt(_facts(differences=[first]))
