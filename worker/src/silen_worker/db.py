"""워커 DB 접근. 특권 역할(로컬 postgres)로 psycopg 직접 접속해 RLS를 우회한다.
RLS가 막아주지 않으므로 모든 조회에 user_id 필터를 코드로 강제한다(스펙 §8).
"""

import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

import psycopg

DEFAULT_DSN = "postgresql://postgres:postgres@127.0.0.1:54322/postgres"


def dsn() -> str:
    return os.environ.get("SUPABASE_DB_URL", DEFAULT_DSN)


def connect() -> psycopg.Connection:
    return psycopg.connect(dsn(), autocommit=True)


@dataclass
class Memory:
    id: str
    user_id: str
    raw_text: str | None


def fetch_memory(conn: psycopg.Connection, memory_id: str, user_id: str) -> Memory | None:
    """메모를 조회한다. user_id로도 필터해 교차 사용자 접근을 코드로 막는다.
    잠긴/삭제된 메모는 제외한다(is_locked·deleted_at)."""
    row = conn.execute(
        "select id::text, user_id::text, raw_text "
        "from public.memories "
        "where id = %s and user_id = %s and deleted_at is null and is_locked = false",
        (memory_id, user_id),
    ).fetchone()
    if row is None:
        return None
    return Memory(id=row[0], user_id=row[1], raw_text=row[2])


def upsert_entity(
    conn: psycopg.Connection, user_id: str, entity_type: str, name: str, normalized_name: str
) -> str:
    """(user_id, entity_type, normalized_name) 자연키로 upsert. 멱등."""
    row = conn.execute(
        """
        insert into public.entities (user_id, entity_type, name, normalized_name)
        values (%s, %s, %s, %s)
        on conflict (user_id, entity_type, normalized_name) do update
          set normalized_name = excluded.normalized_name
        returning id::text
        """,
        (user_id, entity_type, name, normalized_name),
    ).fetchone()
    return row[0]


def link_memory_entity(conn: psycopg.Connection, memory_id: str, entity_id: str) -> None:
    """(memory_id, entity_id, relation_type) PK로 upsert. 재처리해도 중복 없음."""
    conn.execute(
        """
        insert into public.memory_entities (memory_id, entity_id, relation_type)
        values (%s, %s, 'mentioned')
        on conflict (memory_id, entity_id, relation_type) do nothing
        """,
        (memory_id, entity_id),
    )


@dataclass
class OccurrenceRow:
    entity_id: str
    entity_type: str
    memory_id: str
    captured_at: datetime
    timezone: str


@dataclass
class ActiveMemoryRow:
    memory_id: str
    captured_at: datetime
    timezone: str


@dataclass
class EmotionRow:
    memory_id: str
    captured_at: datetime
    timezone: str
    valence: float


def fetch_window_active_memories(
    conn: psycopg.Connection,
    user_id: str,
    target_date: date,
    window_days: int,
) -> list[ActiveMemoryRow]:
    """오늘과 앞선 ``window_days``를 덮는 활성 메모를 반환한다.

    엔티티가 추출되지 않은 메모도 활성 기록일 분모와 오늘 부재 근거에 포함한다.
    """
    lower = datetime.combine(
        target_date - timedelta(days=window_days + 2),
        datetime.min.time(),
        timezone.utc,
    )
    upper = datetime.combine(
        target_date + timedelta(days=2),
        datetime.min.time(),
        timezone.utc,
    )
    rows = conn.execute(
        """
        select m.id::text, m.captured_at, u.timezone
        from public.memories m
        join public.users u on u.id = m.user_id
        where m.user_id = %s
          and m.deleted_at is null
          and m.is_locked = false
          and m.captured_at >= %s
          and m.captured_at < %s
        order by m.captured_at
        """,
        (user_id, lower, upper),
    ).fetchall()
    return [ActiveMemoryRow(r[0], r[1], r[2]) for r in rows]


def fetch_window_emotions(
    conn: psycopg.Connection,
    user_id: str,
    target_date: date,
    window_days: int,
) -> list[EmotionRow]:
    """창 안의 잠기지 않은 본인 감정 값만 반환한다."""
    lower = datetime.combine(
        target_date - timedelta(days=window_days + 2),
        datetime.min.time(),
        timezone.utc,
    )
    upper = datetime.combine(
        target_date + timedelta(days=2),
        datetime.min.time(),
        timezone.utc,
    )
    rows = conn.execute(
        """
        select m.id::text, m.captured_at, u.timezone, e.valence
        from public.emotions e
        join public.memories m on m.id = e.memory_id
        join public.users u on u.id = m.user_id
        where m.user_id = %s
          and m.deleted_at is null
          and m.is_locked = false
          and e.valence is not null
          and m.captured_at >= %s
          and m.captured_at < %s
        order by m.captured_at
        """,
        (user_id, lower, upper),
    ).fetchall()
    return [EmotionRow(r[0], r[1], r[2], float(r[3])) for r in rows]


def fetch_window_occurrences(
    conn: psycopg.Connection, user_id: str, target_date: date, window_days: int
) -> list[OccurrenceRow]:
    """창을 넉넉히 덮는 UTC 범위의 활성 엔티티 언급을 반환한다. 로컬 날짜 버킷팅은
    호출자가 time.local_date_for로 정밀하게 한다(하루 경계 단일 출처). user_id 강제,
    잠금/삭제 메모 제외."""
    lower = datetime.combine(
        target_date - timedelta(days=window_days + 2), datetime.min.time(), timezone.utc
    )
    upper = datetime.combine(
        target_date + timedelta(days=2), datetime.min.time(), timezone.utc
    )
    rows = conn.execute(
        """
        select me.entity_id::text, e.entity_type, m.id::text, m.captured_at, u.timezone
        from public.memory_entities me
        join public.memories m on m.id = me.memory_id
        join public.entities e on e.id = me.entity_id
        join public.users u on u.id = m.user_id
        where m.user_id = %s
          and m.deleted_at is null
          and m.is_locked = false
          and m.captured_at >= %s
          and m.captured_at < %s
          and e.user_id = %s
        """,
        (user_id, lower, upper, user_id),
    ).fetchall()
    return [OccurrenceRow(r[0], r[1], r[2], r[3], r[4]) for r in rows]


def fetch_latest_prior_occurrences(
    conn: psycopg.Connection,
    user_id: str,
    entity_ids: list[str],
    target_date: date,
) -> dict[str, tuple[datetime, str]]:
    """대상 로컬 날짜보다 앞선 마지막 활성 언급을 엔티티별로 반환한다."""
    if not entity_ids:
        return {}
    rows = conn.execute(
        """
        select distinct on (me.entity_id)
               me.entity_id::text, m.captured_at, u.timezone
        from public.memory_entities me
        join public.memories m on m.id = me.memory_id
        join public.users u on u.id = m.user_id
        join public.entities e on e.id = me.entity_id
        where m.user_id = %s
          and e.user_id = %s
          and m.deleted_at is null
          and m.is_locked = false
          and me.entity_id = any(%s::uuid[])
          and (m.captured_at at time zone u.timezone)::date < %s
        order by me.entity_id, m.captured_at desc
        """,
        (user_id, user_id, entity_ids, target_date),
    ).fetchall()
    return {r[0]: (r[1], r[2]) for r in rows}


def fetch_earliest_occurrence(
    conn: psycopg.Connection, user_id: str, entity_ids: list[str]
) -> dict[str, tuple[datetime, str]]:
    """주어진 엔티티들의 가장 이른 활성 언급 시각+타임존. first_occurrence 판정용
    (전체 이력 존재 여부). user_id 강제."""
    if not entity_ids:
        return {}
    rows = conn.execute(
        """
        select distinct on (me.entity_id)
               me.entity_id::text, m.captured_at, u.timezone
        from public.memory_entities me
        join public.memories m on m.id = me.memory_id
        join public.users u on u.id = m.user_id
        where m.user_id = %s
          and m.deleted_at is null
          and m.is_locked = false
          and me.entity_id = any(%s::uuid[])
        order by me.entity_id, m.captured_at asc
        """,
        (user_id, entity_ids),
    ).fetchall()
    return {r[0]: (r[1], r[2]) for r in rows}


def upsert_difference(
    conn: psycopg.Connection,
    user_id: str,
    target_date: date,
    entity_id: str,
    detection_method: str,
    dimension: str,
    description: str,
    confidence: float,
) -> str:
    """(user_id, date, entity_id, detection_method) 부분 자연키로 멱등 upsert.
    재실행 시 근거를 되살린다(evidence_state=intact)."""
    row = conn.execute(
        """
        insert into public.differences
          (user_id, date, entity_id, dimension, description,
           detection_method, confidence, category, status, evidence_state)
        values (%s, %s, %s, %s, %s, %s, %s, '오늘의다른점', 'candidate', 'intact')
        on conflict (user_id, date, entity_id, detection_method) where entity_id is not null
        do update set description = excluded.description,
                      confidence = excluded.confidence,
                      dimension = excluded.dimension,
                      evidence_state = 'intact',
                      staled_at = null
        returning id::text
        """,
        (user_id, target_date, entity_id, dimension, description, detection_method, confidence),
    ).fetchone()
    return row[0]


def upsert_dimension_difference(
    conn: psycopg.Connection,
    user_id: str,
    target_date: date,
    dimension: str,
    detection_method: str,
    category: str,
    description: str,
    confidence: float,
) -> str:
    """엔티티 없는 차원을 부분 자연키로 멱등 upsert한다."""
    row = conn.execute(
        """
        insert into public.differences
          (user_id, date, entity_id, dimension, description,
           detection_method, confidence, category, status, evidence_state)
        values (%s, %s, null, %s, %s, %s, %s, %s, 'candidate', 'intact')
        on conflict (user_id, date, dimension, detection_method)
          where entity_id is null
        do update set description = excluded.description,
                      confidence = excluded.confidence,
                      category = excluded.category,
                      evidence_state = 'intact',
                      staled_at = null
        returning id::text
        """,
        (
            user_id,
            target_date,
            dimension,
            description,
            detection_method,
            confidence,
            category,
        ),
    ).fetchone()
    return row[0]


def fetch_dismiss_counts(
    conn: psycopg.Connection,
    user_id: str,
    since_date: date,
) -> dict[tuple[str | None, str, str], int]:
    """최근 기각 횟수를 엔티티/차원/방법 자연키로 반환한다."""
    rows = conn.execute(
        """
        select entity_id::text, dimension, detection_method, count(*)::int
        from public.differences
        where user_id = %s
          and date >= %s
          and status = 'dismissed'
        group by entity_id, dimension, detection_method
        """,
        (user_id, since_date),
    ).fetchall()
    return {(row[0], row[1], row[2]): row[3] for row in rows}


def link_difference_evidence(
    conn: psycopg.Connection, difference_id: str, memory_id: str
) -> None:
    """(difference_id, memory_id) PK로 멱등 링크."""
    conn.execute(
        "insert into public.difference_evidence (difference_id, memory_id) "
        "values (%s, %s) on conflict (difference_id, memory_id) do nothing",
        (difference_id, memory_id),
    )


def replace_difference_evidence(
    conn: psycopg.Connection,
    difference_id: str,
    memory_ids: list[str],
) -> None:
    """재탐지 시 현재 근거 집합으로 교체해 잠금·삭제된 옛 링크를 남기지 않는다."""
    conn.execute(
        "delete from public.difference_evidence where difference_id = %s",
        (difference_id,),
    )
    for memory_id in dict.fromkeys(memory_ids):
        link_difference_evidence(conn, difference_id, memory_id)


@dataclass
class DifferenceFacts:
    difference_id: str
    user_id: str
    entity_id: str
    entity_name: str
    entity_type: str
    detection_method: str
    description: str
    date_iso: str


def fetch_difference_for_narration(
    conn: psycopg.Connection, difference_id: str
) -> DifferenceFacts | None:
    """서술 재료를 엔티티 조인으로 읽는다. 엔티티 차이(entity_id 있음)이고
    근거가 살아있는(intact) 것만 대상. 서술 대상은 status=candidate로 한정한다
    (스펙 §1) — 사용자가 '아니에요'(dismissed) 한 차이는 서술하지 않는다.
    저장은 여기서 읽은 user_id로 귀속한다."""
    row = conn.execute(
        """
        select d.id::text, d.user_id::text, d.entity_id::text,
               e.name, e.entity_type, d.detection_method,
               coalesce(d.description, ''), d.date::text
        from public.differences d
        join public.entities e on e.id = d.entity_id
        where d.id = %s
          and d.entity_id is not null
          and d.evidence_state = 'intact'
          and d.status = 'candidate'
        """,
        (difference_id,),
    ).fetchone()
    if row is None:
        return None
    return DifferenceFacts(row[0], row[1], row[2], row[3], row[4], row[5], row[6], row[7])


def upsert_narration(
    conn: psycopg.Connection,
    user_id: str,
    difference_id: str,
    headline: str,
    body: str,
    evidence_text: str,
    model: str,
) -> str:
    """difference_id 자연키로 멱등 upsert. 재서술은 덮어쓴다."""
    row = conn.execute(
        """
        insert into public.difference_narrations
          (user_id, difference_id, headline, body, evidence_text, model)
        values (%s, %s, %s, %s, %s, %s)
        on conflict (difference_id) do update
          set headline = excluded.headline,
              body = excluded.body,
              evidence_text = excluded.evidence_text,
              model = excluded.model
        returning id::text
        """,
        (user_id, difference_id, headline, body, evidence_text, model),
    ).fetchone()
    return row[0]


@dataclass
class DiaryMemoryRow:
    memory_id: str
    captured_at: datetime
    timezone: str
    raw_text: str


def fetch_diary_memories(
    conn: psycopg.Connection, user_id: str, target_date: date
) -> list[DiaryMemoryRow]:
    """대상 로컬 날짜를 덮는 UTC 창의 활성 메모(본문 있음)를 반환한다. 로컬 날짜
    필터는 호출자가 time.local_date_for로 정밀하게 한다. user_id 강제, 잠금/삭제 제외."""
    lower = datetime.combine(target_date - timedelta(days=1), datetime.min.time(), timezone.utc)
    upper = datetime.combine(target_date + timedelta(days=2), datetime.min.time(), timezone.utc)
    rows = conn.execute(
        """
        select m.id::text, m.captured_at, u.timezone, m.raw_text
        from public.memories m
        join public.users u on u.id = m.user_id
        where m.user_id = %s
          and m.deleted_at is null
          and m.is_locked = false
          and m.raw_text is not null
          and length(btrim(m.raw_text)) > 0
          and m.captured_at >= %s
          and m.captured_at < %s
        order by m.captured_at
        """,
        (user_id, lower, upper),
    ).fetchall()
    return [DiaryMemoryRow(r[0], r[1], r[2], r[3]) for r in rows]


@dataclass
class ConfirmedDifference:
    difference_id: str
    headline: str
    detection_method: str
    entity_type: str
    entity_name: str


def fetch_confirmed_differences(
    conn: psycopg.Connection, user_id: str, target_date: date
) -> list[ConfirmedDifference]:
    """그날 confirmed(intact) 차이. detection_method로 본문용(freq_shift)과
    recap용(first_occurrence)을 가르고, entity_name은 가드레일에 쓴다."""
    rows = conn.execute(
        """
        select d.id::text, coalesce(n.headline, d.description, ''),
               d.detection_method, e.entity_type, e.name
        from public.differences d
        join public.entities e on e.id = d.entity_id
        left join public.difference_narrations n on n.difference_id = d.id
        where d.user_id = %s
          and d.date = %s
          and d.status = 'confirmed'
          and d.evidence_state = 'intact'
        order by d.id
        """,
        (user_id, target_date),
    ).fetchall()
    return [ConfirmedDifference(r[0], r[1], r[2], r[3], r[4]) for r in rows]


def fetch_existing_diary(
    conn: psycopg.Connection, user_id: str, target_date: date
) -> tuple[str, str, str | None, bool] | None:
    """(diary_id, status, tone_instruction, regenerate_requested) 또는 None."""
    row = conn.execute(
        "select id::text, status, tone_instruction, "
        "regenerate_requested_at is not null "
        "from public.diaries where user_id = %s and date = %s",
        (user_id, target_date),
    ).fetchone()
    return (row[0], row[1], row[2], row[3]) if row is not None else None


def fetch_tone_preset(conn: psycopg.Connection, user_id: str) -> str:
    """사용자 기본 톤. 없으면 담백."""
    row = conn.execute(
        "select style_profile->>'preset' from public.users where id = %s",
        (user_id,),
    ).fetchone()
    return row[0] if row and row[0] in ("담백", "따뜻") else "담백"


def clear_regenerate_request(conn: psycopg.Connection, diary_id: str) -> None:
    """요청을 1회 소비한다. 자동 재생성이 아니므로 반드시 비운다."""
    conn.execute(
        "update public.diaries set tone_instruction = null, "
        "regenerate_requested_at = null where id = %s",
        (diary_id,),
    )


def upsert_diary(
    conn: psycopg.Connection,
    user_id: str,
    target_date: date,
    generated_text: str,
    reset_edit: bool = False,
) -> str | None:
    """(user_id, date) 자연키로 멱등 upsert. reset_edit이면 편집본을 비우고
    draft로 되돌린다 — 사용자가 '다시 만들기'로 명시 요청한 경우다.
    요청 없는 force는 status='draft'일 때만 갱신해 사용자 편집을 보호한다."""
    row = conn.execute(
        """
        insert into public.diaries (user_id, date, status, style_profile, generated_text)
        values (%s, %s, 'draft', '{"preset":"담백"}'::jsonb, %s)
        on conflict (user_id, date) do update
          set generated_text = excluded.generated_text,
              status = 'draft',
              edited_text = case when %s then null else public.diaries.edited_text end
          where %s or public.diaries.status = 'draft'
        returning id::text
        """,
        (user_id, target_date, generated_text, reset_edit, reset_edit),
    ).fetchone()
    return row[0] if row is not None else None


def replace_diary_sections(
    conn: psycopg.Connection,
    diary_id: str,
    one_line: str,
    body: str,
    used_differences: list[tuple[str, str]],
) -> None:
    """기존 섹션을 지우고 오늘의한문장·본문 + used 차이별 다른점을 다시 쓴다."""
    conn.execute("delete from public.diary_sections where diary_id = %s", (diary_id,))
    conn.execute(
        "insert into public.diary_sections (diary_id, section_type, content) "
        "values (%s, '오늘의한문장', %s), (%s, '본문', %s)",
        (diary_id, one_line, diary_id, body),
    )
    for diff_id, headline in used_differences:
        conn.execute(
            "insert into public.diary_sections (diary_id, difference_id, section_type, content) "
            "values (%s, %s, '다른점', %s)",
            (diary_id, diff_id, headline),
        )


def replace_diary_sources(
    conn: psycopg.Connection, diary_id: str, memory_ids: list[str]
) -> None:
    """기존 출처를 지우고 used 메모를 다시 링크한다."""
    conn.execute("delete from public.diary_sources where diary_id = %s", (diary_id,))
    for memory_id in memory_ids:
        conn.execute(
            "insert into public.diary_sources (diary_id, memory_id) values (%s, %s) "
            "on conflict (diary_id, memory_id) do nothing",
            (diary_id, memory_id),
        )


def fetch_active_users(conn: psycopg.Connection) -> list[tuple[str, str]]:
    """모든 사용자를 (user_id, timezone)으로 반환한다. 배치 대상 열거용.
    사용자별 '하루' 경계 계산에 timezone이 필요하다(time.local_date_for)."""
    rows = conn.execute(
        "select id::text, timezone from public.users order by id"
    ).fetchall()
    return [(r[0], r[1]) for r in rows]


def fetch_narration_id(conn: psycopg.Connection, difference_id: str) -> str | None:
    """이 차이에 이미 서술이 있으면 그 id, 없으면 None.
    재실행 시 LLM 재호출(반복 과금)을 막는 판정에 쓴다."""
    row = conn.execute(
        "select id::text from public.difference_narrations where difference_id = %s",
        (difference_id,),
    ).fetchone()
    return row[0] if row is not None else None


def insert_diary_question(
    conn: psycopg.Connection, diary_id: str, difference_id: str, content: str
) -> None:
    """일기의 꼬리 질문 하나. replace_diary_sections가 섹션을 지운 뒤에 부른다."""
    conn.execute(
        "insert into public.diary_sections (diary_id, difference_id, section_type, content) "
        "values (%s, %s, '질문', %s)",
        (diary_id, difference_id, content),
    )


def claim_diary_generation_request(
    conn: psycopg.Connection,
    request_id: str,
    user_id: str,
) -> bool:
    """본인 요청을 processing으로 전환한다. 오래 멈춘 claim은 재시도할 수 있다."""
    row = conn.execute(
        """
        update public.diary_generation_requests
           set status = 'processing',
               attempts = attempts + 1,
               started_at = now(),
               error_code = null
         where id = %s
           and user_id = %s
           and (
             status = 'queued'
             or (status = 'processing' and started_at < now() - interval '60 seconds')
           )
        returning id
        """,
        (request_id, user_id),
    ).fetchone()
    return row is not None


def complete_diary_generation_request(
    conn: psycopg.Connection,
    request_id: str,
    user_id: str,
    diary_id: str,
) -> None:
    """일기 저장까지 끝난 뒤에만 done으로 바꾼다."""
    conn.execute(
        """
        update public.diary_generation_requests
           set status = 'done',
               diary_id = %s,
               error_code = null,
               completed_at = now()
         where id = %s
           and user_id = %s
           and status = 'processing'
        """,
        (diary_id, request_id, user_id),
    )


def fail_diary_generation_request(
    conn: psycopg.Connection,
    request_id: str,
    user_id: str,
    error_code: str,
    terminal: bool,
) -> None:
    """재시도 가능 실패는 queued, 상한 도달 실패는 failed로 기록한다."""
    conn.execute(
        """
        update public.diary_generation_requests
           set status = case when %s then 'failed' else 'queued' end,
               error_code = %s,
               completed_at = case when %s then now() else null end
         where id = %s
           and user_id = %s
           and status = 'processing'
        """,
        (terminal, error_code, terminal, request_id, user_id),
    )
