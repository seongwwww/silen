from datetime import datetime, timezone

from silen_worker.recall.service import (
    PHOTO_EVIDENCE_LIMIT,
    empty_recall_response,
    with_photo_evidence,
    NO_RECALL_RESULT,
    RecallCandidate,
    build_grounded_response,
    merge_hybrid_candidates,
)


def _candidate(
    memory_id: str,
    text: str,
    day: int,
    photo_path: str | None = None,
) -> RecallCandidate:
    return RecallCandidate(
        memory_id=memory_id,
        raw_text=text,
        effective_at=datetime(2026, 7, day, tzinfo=timezone.utc),
        photo_path=photo_path,
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
    candidates = [
        _candidate(
            "m1",
            "그 카페에서 오래 이야기했다.",
            14,
            "user-1/photo.png",
        )
    ]

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
            "photoPath": "user-1/photo.png",
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


class TestPhotoEvidence:
    """사진은 LLM이 고르지 않는다. 인용 가드레일이 raw_text 대조를 요구하는데
    사진만 있는 기록은 대조할 원문이 없어, LLM이 고르면 응답 전체가 폐기된다."""

    def _c(self, mid, text, day, photo=None):
        return RecallCandidate(mid, text, datetime(2026, 7, day, tzinfo=timezone.utc), photo)

    def test_사진_근거는_인용_없이_붙는다(self):
        text_only = [self._c("m1", "그 카페에서 커피", 15)]
        photos = [self._c("m2", "", 20, "u1/a.png")]

        out = with_photo_evidence(
            build_grounded_response(text_only, [{"memory_id": "m1", "quote": "그 카페에서 커피"}]),
            photos,
        )

        assert [e["memoryId"] for e in out["evidence"]] == ["m1", "m2"]
        assert out["evidence"][1]["quote"] == ""
        assert out["evidence"][1]["photoPath"] == "u1/a.png"

    def test_이미_인용된_기록은_사진으로_중복되지_않는다(self):
        both = [self._c("m1", "카페 사진을 찍었다", 15, "u1/a.png")]

        out = with_photo_evidence(
            build_grounded_response(both, [{"memory_id": "m1", "quote": "카페 사진을 찍었다"}]),
            both,
        )

        assert len(out["evidence"]) == 1

    def test_글_결과가_없어도_사진만으로_답한다(self):
        photos = [self._c("m2", "", 20, "u1/a.png")]

        out = with_photo_evidence(empty_recall_response(), photos)

        assert len(out["evidence"]) == 1
        assert out["answer"] != empty_recall_response()["answer"]

    def test_사진도_없으면_빈_결과_그대로다(self):
        out = with_photo_evidence(empty_recall_response(), [])
        assert out == empty_recall_response()

    def test_사진_개수를_제한한다(self):
        photos = [self._c(f"m{i}", "", 20, f"u1/{i}.png") for i in range(10)]
        out = with_photo_evidence(empty_recall_response(), photos)
        assert len(out["evidence"]) <= PHOTO_EVIDENCE_LIMIT
