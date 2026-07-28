import pytest

from silen_worker.db import ConfirmedDifference
from silen_worker.diary.question import (
    build_question_prompt, pick_question_target, question_guardrail,
)


def _diff(method="first_occurrence", etype="person", name="지은", did="d1"):
    return ConfirmedDifference(did, f"{name} 처음", method, etype, name)


def test_사람이_있으면_사람을_고른다():
    target = pick_question_target([_diff(etype="activity", did="d2"), _diff(etype="person")])
    assert target.entity_type == "person"


def test_사람이_없으면_장소_다음_활동():
    assert pick_question_target([_diff(etype="activity", did="d2"), _diff(etype="place", did="d3")]).entity_type == "place"
    assert pick_question_target([_diff(etype="activity")]).entity_type == "activity"


def test_사물은_대상이_아니다():
    assert pick_question_target([_diff(etype="thing")]) is None


def test_반복차이는_대상이_아니다():
    assert pick_question_target([_diff(method="freq_shift")]) is None


def test_대상이_없으면_None():
    assert pick_question_target([]) is None


def test_프롬프트에_엔티티명이_들어간다():
    assert "지은" in build_question_prompt(_diff())


def test_정상_질문은_통과한다():
    assert question_guardrail({"question": "지은은 어떤 사람이었어요?"}, _diff()) is not None


def test_엔티티명_없는_질문은_폐기한다():
    assert question_guardrail({"question": "오늘 어땠어요?"}, _diff()) is None


def test_심문조_질문은_폐기한다():
    assert question_guardrail({"question": "지은과 무엇을 했는지 말해보세요."}, _diff()) is None


def test_빈_질문은_폐기한다():
    assert question_guardrail({"question": "   "}, _diff()) is None


def test_엔티티_없는_zscore_감정은_질문_대상이_아니다():
    emotion = _diff(method="zscore", etype=None, name=None)

    assert pick_question_target([emotion]) is None


def test_이름_없는_first_occurrence도_질문_대상이_아니다():
    nameless = _diff(method="first_occurrence", etype="person", name=None)

    assert pick_question_target([nameless]) is None


def test_엔티티_없는_대상은_프롬프트에_None을_넣지_않는다():
    nameless = _diff(method="first_occurrence", etype="person", name=None)

    with pytest.raises(ValueError, match="entity"):
        build_question_prompt(nameless)
    assert question_guardrail({"question": "None은 어떤 사람이었어요?"}, nameless) is None
