from datetime import datetime, timezone

from silen_worker.recall.service import (
    NO_RECALL_RESULT,
    RecallCandidate,
    build_grounded_response,
    merge_hybrid_candidates,
)


def _candidate(memory_id: str, text: str, day: int) -> RecallCandidate:
    return RecallCandidate(
        memory_id=memory_id,
        raw_text=text,
        captured_at=datetime(2026, 7, day, tzinfo=timezone.utc),
    )


def test_벡터와_키워드_후보를_중복_없이_결정적으로_합친다():
    shared = _candidate("m-shared", "김밥을 먹고 카페에 갔다", 21)
    vector_only = _candidate("m-vector", "조용한 곳에서 쉬었다", 20)
    keyword_only = _candidate("m-keyword", "김밥", 22)

    first = merge_hybrid_candidates(
        [shared, vector_only],
        [keyword_only, shared],
        limit=8,
    )
    second = merge_hybrid_candidates(
        [shared, vector_only],
        [keyword_only, shared],
        limit=8,
    )

    assert [item.memory_id for item in first] == [
        "m-shared",
        "m-keyword",
        "m-vector",
    ]
    assert first == second


def test_회고_응답은_실제_후보의_원문_인용만_허용한다():
    candidates = [_candidate("m1", "그 카페에서 오래 이야기했다.", 14)]

    response = build_grounded_response(
        candidates,
        [{"memory_id": "m1", "quote": "카페에서 오래 이야기했다"}],
    )

    assert response["answer"] == "기록에서 이런 내용을 찾았어요."
    assert response["confirmation"] == "이거 맞으세요?"
    assert response["evidence"] == [
        {
            "memoryId": "m1",
            "capturedAt": "2026-07-14T00:00:00+00:00",
            "quote": "카페에서 오래 이야기했다",
        }
    ]


def test_후보에_없는_id나_지어낸_인용은_전체_응답을_폐기한다():
    candidates = [_candidate("m1", "그 카페에서 오래 이야기했다.", 14)]

    unknown = build_grounded_response(
        candidates,
        [{"memory_id": "m2", "quote": "카페"}],
    )
    fabricated = build_grounded_response(
        candidates,
        [{"memory_id": "m1", "quote": "매우 행복했다"}],
    )

    assert unknown == {
        "answer": NO_RECALL_RESULT,
        "confirmation": None,
        "evidence": [],
    }
    assert fabricated == unknown


def test_후보가_없으면_LLM_결과와_상관없이_정확한_빈_문구를_쓴다():
    assert build_grounded_response([], []) == {
        "answer": "그런 기록은 찾지 못했어요",
        "confirmation": None,
        "evidence": [],
    }

