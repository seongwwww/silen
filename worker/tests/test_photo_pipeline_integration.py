"""사진 처리 전체를 실제 Postgres로 검증한다. 외부 호출은 스텁이다."""

import pytest

from silen_worker.photo.pipeline import process_memory_photos
from silen_worker.photo.service import PHOTO_EMBEDDING_DIMENSION
from tests.conftest import delete_user, seed_memory_at, seed_user


class _Captioner:
    def __init__(self, text: str):
        self.text = text

    def caption(self, image, mime_type):
        return self.text


class _Embedder:
    def embed_image(self, image):
        return [0.5] * PHOTO_EMBEDDING_DIMENSION


class _Extractor:
    def __init__(self, names):
        self.names = names

    def extract(self, text):
        return [{"type": "thing", "name": n} for n in self.names]


def _photo(conn, memory_id, user_id, path="a.png"):
    return conn.execute(
        "insert into public.assets (memory_id, asset_type, file_url, mime_type) "
        "values (%s, 'photo', %s, 'image/png') returning id::text",
        (memory_id, f"{user_id}/{path}"),
    ).fetchone()[0]


def _run(conn, memory_id, user_id, raw_text, caption, names):
    return process_memory_photos(
        conn,
        memory_id,
        user_id,
        raw_text,
        captioner=_Captioner(caption),
        embedder=_Embedder(),
        extractor=_Extractor(names),
        read_image=lambda path: b"\x89PNG",
    )


@pytest.mark.integration
def test_캡션은_원본이_아니라_자산에_저장한다(conn):
    """사용자가 쓴 글에 AI 문장을 섞으면 원본과 생성물이 뒤엉킨다."""
    alice = seed_user(conn)
    try:
        memory = seed_memory_at(conn, alice, "2026-07-19T03:00:00+00", "라떼 마셨다")
        asset = _photo(conn, memory, alice)

        _run(conn, memory, alice, "라떼 마셨다", "컵, 창문", [])

        raw = conn.execute(
            "select raw_text from public.memories where id = %s", (memory,)
        ).fetchone()[0]
        cap = conn.execute(
            "select extracted_text from public.assets where id = %s", (asset,)
        ).fetchone()[0]
        assert raw == "라떼 마셨다"
        assert cap == "컵, 창문"
    finally:
        delete_user(conn, alice)


@pytest.mark.integration
def test_사진만_있는_기록도_검색_본문이_생긴다(conn):
    """지금까지 사진만 남기면 임베딩조차 안 돼 검색에서 사라졌다."""
    alice = seed_user(conn)
    try:
        memory = seed_memory_at(conn, alice, "2026-07-19T03:00:00+00", None)
        _photo(conn, memory, alice)

        assert _run(conn, memory, alice, None, "컵, 창문", []) == "컵, 창문"
    finally:
        delete_user(conn, alice)


@pytest.mark.integration
def test_사용자가_쓴_적_없는_말은_엔티티가_되지_않는다(conn):
    """사진 엔티티의 앵커. 없으면 검증 안 된 말로 차이가 뜬다."""
    alice = seed_user(conn)
    try:
        # 사용자 어휘: "카페"만 텍스트로 존재한다.
        text_memory = seed_memory_at(
            conn, alice, "2026-07-18T03:00:00+00", "그 카페에 갔다"
        )
        cafe = conn.execute(
            "insert into public.entities (user_id, entity_type, name, normalized_name) "
            "values (%s, 'place', '카페', '카페') returning id::text",
            (alice,),
        ).fetchone()[0]
        conn.execute(
            "insert into public.memory_entities (memory_id, entity_id, relation_type) "
            "values (%s, %s, 'visited')",
            (text_memory, cafe),
        )

        memory = seed_memory_at(conn, alice, "2026-07-19T03:00:00+00", "사진")
        _photo(conn, memory, alice)

        _run(conn, memory, alice, "사진", "카페, 창문", ["카페", "창문"])

        linked = conn.execute(
            "select e.normalized_name from public.memory_entities me "
            "join public.entities e on e.id = me.entity_id where me.memory_id = %s",
            (memory,),
        ).fetchall()
        assert [row[0] for row in linked] == ["카페"]
    finally:
        delete_user(conn, alice)


@pytest.mark.integration
def test_추측이_섞인_캡션은_저장하지_않는다(conn):
    alice = seed_user(conn)
    try:
        memory = seed_memory_at(conn, alice, "2026-07-19T03:00:00+00", "글")
        asset = _photo(conn, memory, alice)

        _run(conn, memory, alice, "글", "행복해 보인다", [])

        cap = conn.execute(
            "select extracted_text from public.assets where id = %s", (asset,)
        ).fetchone()[0]
        assert cap is None
    finally:
        delete_user(conn, alice)
