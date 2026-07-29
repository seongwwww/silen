from evals.diary.run import _facts, validate


def _case():
    return {
        "memories": [["m1", "시험 결과 나옴"]],
        "differences": [],
    }


def _raw(body: str):
    return {
        "one_line": "시험 결과가 나왔다.",
        "body": body,
        "used_memory_ids": ["m1"],
        "used_difference_ids": [],
    }


def test_eval은_입력_밖_사건_부재를_자동_실패시킨다():
    failures = validate(
        _raw("시험 결과가 나왔다. 다른 일은 없었다."),
        _facts(_case()),
    )

    assert any("사건 부재 단정" in failure for failure in failures)


def test_eval은_톤이_덧붙인_기능_효과_해석을_자동_실패시킨다():
    failures = validate(
        _raw("점심에 에너지를 충전하고 산책으로 소비했다."),
        _facts(_case()),
    )

    assert any("기능·효과 해석" in failure for failure in failures)
