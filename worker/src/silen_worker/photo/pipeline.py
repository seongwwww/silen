"""사진 한 장을 처리한다 — 캡션·임베딩·앵커 통과 엔티티.

DB와 외부 호출은 주입받은 포트로만 만진다. 실패해도 메모 잡을 되돌리지
않는다(추출은 이미 끝났고 되돌리면 유료 작업이 무한 반복된다).
"""

import psycopg

from silen_worker.db import link_memory_entity, upsert_entity
from silen_worker.extraction.service import guardrail as extraction_guardrail
from silen_worker.photo.caption import (
    anchored_entities,
    caption_guardrail,
    embeddable_text,
)
from silen_worker.photo.repository import (
    fetch_memory_photos,
    fetch_user_vocabulary,
    save_caption,
    upsert_photo_embedding,
)
from silen_worker.photo.service import should_embed


def process_memory_photos(
    conn: psycopg.Connection,
    memory_id: str,
    user_id: str,
    raw_text: str | None,
    *,
    captioner,
    embedder,
    extractor,
    read_image,
) -> str | None:
    """이 메모의 사진을 처리하고, 텍스트 임베딩에 쓸 본문을 돌려준다.

    사진이 없거나 전부 실패하면 raw_text를 그대로 돌려준다.
    """
    captions: list[str] = []
    vocabulary: set[str] | None = None

    for asset_id, file_url, mime_type in fetch_memory_photos(conn, memory_id, user_id):
        if not should_embed("photo", mime_type or None):
            continue
        image = read_image(file_url)
        if image is None:
            continue

        # 벡터: 질문 하나로 사진을 찾기 위한 것. 캡션과 무관하게 저장한다.
        upsert_photo_embedding(
            conn, asset_id, memory_id, user_id, embedder.embed_image(image)
        )

        caption = caption_guardrail(captioner.caption(image, mime_type))
        if caption is None:
            continue
        save_caption(conn, asset_id, caption)
        captions.append(caption)

        # 사진 엔티티는 앵커를 통과한 것만. 사진에서만 보이는 말은 버린다.
        if vocabulary is None:
            vocabulary = fetch_user_vocabulary(conn, user_id)
        for entity in anchored_entities(
            extraction_guardrail(extractor.extract(caption), caption),
            vocabulary,
        ):
            entity_id = upsert_entity(
                conn, user_id, entity.type, entity.name, entity.normalized_name
            )
            link_memory_entity(conn, memory_id, entity_id)

    return embeddable_text(raw_text, "\n".join(captions) if captions else None)
