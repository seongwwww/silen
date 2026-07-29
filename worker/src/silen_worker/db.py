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
    effective_at: datetime
    timezone: str


def fetch_memory(conn: psycopg.Connection, memory_id: str, user_id: str) -> Memory | None:
    """메모를 조회한다. user_id로도 필터해 교차 사용자 접근을 코드로 막는다.
    잠긴/삭제된 메모는 제외한다(is_locked·deleted_at)."""
    row = conn.execute(
        "select m.id::text, m.user_id::text, m.raw_text, "
        "m.effective_at, u.timezone "
        "from public.memories m "
        "join public.users u on u.id = m.user_id "
        "where m.id = %s and m.user_id = %s "
        "and m.deleted_at is null and m.is_locked = false",
        (memory_id, user_id),
    ).fetchone()
    if row is None:
        return None
    return Memory(
        id=row[0],
        user_id=row[1],
        raw_text=row[2],
        effective_at=row[3],
        timezone=row[4],
    )


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
    effective_at: datetime
    timezone: str


@dataclass
class ActiveMemoryRow:
    memory_id: str
    effective_at: datetime
    timezone: str


@dataclass
class EmotionRow:
    memory_id: str
    effective_at: datetime
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
        select m.id::text, m.effective_at, u.timezone
        from public.memories m
        join public.users u on u.id = m.user_id
        where m.user_id = %s
          and m.deleted_at is null
          and m.is_locked = false
          and m.effective_at >= %s
          and m.effective_at < %s
        order by m.effective_at
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
        select m.id::text, m.effective_at, u.timezone, e.valence
        from public.emotions e
        join public.memories m on m.id = e.memory_id
        join public.users u on u.id = m.user_id
        where m.user_id = %s
          and m.deleted_at is null
          and m.is_locked = false
          and e.confirmed_by_user = true
          and e.valence is not null
          and m.effective_at >= %s
          and m.effective_at < %s
        order by m.effective_at
        """,
        (user_id, lower, upper),
    ).fetchall()
    return [EmotionRow(r[0], r[1], r[2], float(r[3])) for r in rows]


def fetch_window_occurrences(
    conn: psycopg.Connection,
    user_id: str,
    target_date: date,
    window_days: int,
    excluded_normalized_names: frozenset[str] = frozenset(),
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
        select me.entity_id::text, e.entity_type, m.id::text, m.effective_at, u.timezone
        from public.memory_entities me
        join public.memories m on m.id = me.memory_id
        join public.entities e on e.id = me.entity_id
        join public.users u on u.id = m.user_id
        where m.user_id = %s
          and m.deleted_at is null
          and m.is_locked = false
          and m.effective_at >= %s
          and m.effective_at < %s
          and e.user_id = %s
          and e.normalized_name <> all(%s::text[])
        """,
        (
            user_id,
            lower,
            upper,
            user_id,
            sorted(excluded_normalized_names),
        ),
    ).fetchall()
    return [OccurrenceRow(r[0], r[1], r[2], r[3], r[4]) for r in rows]


def fetch_latest_prior_occurrences(
    conn: psycopg.Connection,
    user_id: str,
    entity_ids: list[str],
    target_date: date,
) -> dict[str, tuple[datetime, str, str]]:
    """대상 로컬 날짜보다 앞선 마지막 활성 언급과 근거 ID를 반환한다."""
    if not entity_ids:
        return {}
    rows = conn.execute(
        """
        select distinct on (me.entity_id)
               me.entity_id::text, m.effective_at, u.timezone, m.id::text
        from public.memory_entities me
        join public.memories m on m.id = me.memory_id
        join public.users u on u.id = m.user_id
        join public.entities e on e.id = me.entity_id
        where m.user_id = %s
          and e.user_id = %s
          and m.deleted_at is null
          and m.is_locked = false
          and me.entity_id = any(%s::uuid[])
          and (m.effective_at at time zone u.timezone)::date < %s
        order by me.entity_id, m.effective_at desc
        """,
        (user_id, user_id, entity_ids, target_date),
    ).fetchall()
    return {r[0]: (r[1], r[2], r[3]) for r in rows}


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
               me.entity_id::text, m.effective_at, u.timezone
        from public.memory_entities me
        join public.memories m on m.id = me.memory_id
        join public.users u on u.id = m.user_id
        where m.user_id = %s
          and m.deleted_at is null
          and m.is_locked = false
          and me.entity_id = any(%s::uuid[])
        order by me.entity_id, m.effective_at asc
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
    category: str = "오늘의다른점",
) -> str:
    """(user_id, date, entity_id, detection_method) 부분 자연키로 멱등 upsert.
    재실행 시 근거를 되살린다(evidence_state=intact)."""
    row = conn.execute(
        """
        insert into public.differences
          (user_id, date, entity_id, dimension, description,
           detection_method, confidence, category, status, evidence_state)
        values (%s, %s, %s, %s, %s, %s, %s, %s, 'candidate', 'intact')
        on conflict (user_id, date, entity_id, detection_method) where entity_id is not null
        do update set description = excluded.description,
                      confidence = excluded.confidence,
                      dimension = excluded.dimension,
                      category = excluded.category,
                      evidence_state = 'intact',
                      staled_at = null
        returning id::text
        """,
        (
            user_id,
            target_date,
            entity_id,
            dimension,
            description,
            detection_method,
            confidence,
            category,
        ),
    ).fetchone()
    return row[0]


def refresh_difference_description(
    conn: psycopg.Connection,
    difference_id: str,
    user_id: str,
    description: str,
    confidence: float,
) -> None:
    """이미 있는 차이의 통계 근거를 최신 규칙으로 다시 쓴다.

    사용자의 확인·기각(status)은 건드리지 않는다 — 판단은 사용자 것이다."""
    conn.execute(
        """
        update public.differences
           set description = %s,
               confidence = %s
         where id = %s
           and user_id = %s
        """,
        (description, confidence, difference_id, user_id),
    )


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
            and dimension = 'emotion'
            and detection_method = 'zscore'
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
    target_date: date,
) -> dict[tuple[str | None, str, str], int]:
    """대상일까지 최근 intact 기각 횟수를 자연키별로 반환한다."""
    rows = conn.execute(
        """
        select entity_id::text, dimension, detection_method, count(*)::int
        from public.differences
        where user_id = %s
          and date >= %s
          and date <= %s
          and status = 'dismissed'
          and evidence_state = 'intact'
        group by entity_id, dimension, detection_method
        """,
        (user_id, since_date, target_date),
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
    user_id: str,
    difference_id: str,
    memory_ids: list[str],
) -> None:
    """본인 차이의 근거를 본인 활성 메모 집합으로만 교체한다."""
    conn.execute(
        """
        delete from public.difference_evidence de
        using public.differences d
        where de.difference_id = d.id
          and d.id = %s
          and d.user_id = %s
        """,
        (difference_id, user_id),
    )
    for memory_id in dict.fromkeys(memory_ids):
        conn.execute(
            """
            insert into public.difference_evidence (difference_id, memory_id)
            select d.id, m.id
            from public.differences d
            join public.memories m on m.id = %s
            where d.id = %s
              and d.user_id = %s
              and m.user_id = %s
              and m.deleted_at is null
              and m.is_locked = false
            on conflict (difference_id, memory_id) do nothing
            """,
            (memory_id, difference_id, user_id, user_id),
        )


def reconcile_daily_differences(
    conn: psycopg.Connection,
    user_id: str,
    target_date: date,
    keep_ids: list[str],
) -> None:
    """재탐지 결과에서 밀린 당일 차이를 stale 처리한다.

    사용자의 confirmed/dismissed 판단은 바꾸지 않고 근거 유효성만 갱신한다.
    """
    conn.execute(
        """
        update public.differences
        set evidence_state = 'stale', staled_at = now()
        where user_id = %s
          and date = %s
          and evidence_state = 'intact'
          and not (id = any(%s::uuid[]))
        """,
        (user_id, target_date, keep_ids),
    )


@dataclass
class DifferenceFacts:
    difference_id: str
    user_id: str
    entity_id: str | None
    entity_name: str | None
    entity_type: str | None
    dimension: str
    detection_method: str
    description: str
    date_iso: str
    evidence_ids: tuple[str, ...]


def fetch_difference_for_narration(
    conn: psycopg.Connection, difference_id: str
) -> DifferenceFacts | None:
    """소유자와 활성 근거가 일치하는 카드용 차이만 서술 재료로 읽는다."""
    row = conn.execute(
        """
        select d.id::text, d.user_id::text, d.entity_id::text,
               e.name, e.entity_type, d.dimension, d.detection_method,
               coalesce(d.description, ''), d.date::text,
               array(
                 select de.memory_id::text
                 from public.difference_evidence de
                 join public.memories m on m.id = de.memory_id
                 where de.difference_id = d.id
                   and m.user_id = d.user_id
                   and m.deleted_at is null
                   and m.is_locked = false
                 order by de.memory_id
               )
        from public.differences d
        left join public.entities e
          on e.id = d.entity_id and e.user_id = d.user_id
        where d.id = %s
          and d.evidence_state = 'intact'
          and d.status = 'candidate'
          and d.detection_method <> 'first_occurrence'
          and (d.entity_id is null or e.id is not null)
          and exists (
            select 1
            from public.difference_evidence de
            join public.memories m on m.id = de.memory_id
            where de.difference_id = d.id
              and m.user_id = d.user_id
              and m.deleted_at is null
              and m.is_locked = false
          )
          and not exists (
            select 1
            from public.difference_evidence de
            join public.memories m on m.id = de.memory_id
            where de.difference_id = d.id
              and (
                m.user_id <> d.user_id
                or m.deleted_at is not null
                or m.is_locked = true
              )
          )
        """,
        (difference_id,),
    ).fetchone()
    if row is None:
        return None
    return DifferenceFacts(
        row[0],
        row[1],
        row[2],
        row[3],
        row[4],
        row[5],
        row[6],
        row[7],
        row[8],
        tuple(row[9]),
    )


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
    effective_at: datetime
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
        select m.id::text, m.effective_at, u.timezone, m.raw_text
        from public.memories m
        join public.users u on u.id = m.user_id
        where m.user_id = %s
          and m.deleted_at is null
          and m.is_locked = false
          and m.raw_text is not null
          and length(btrim(m.raw_text)) > 0
          and m.effective_at >= %s
          and m.effective_at < %s
        order by m.effective_at
        """,
        (user_id, lower, upper),
    ).fetchall()
    return [DiaryMemoryRow(r[0], r[1], r[2], r[3]) for r in rows]


@dataclass
class UsableDifference:
    difference_id: str
    headline: str
    detection_method: str
    entity_type: str | None
    entity_name: str | None


def fetch_usable_differences(
    conn: psycopg.Connection, user_id: str, target_date: date
) -> list[UsableDifference]:
    """그날 기각되지 않은 intact 차이.

    candidate와 confirmed는 사용하고 dismissed·stale은 제외한다. user_id와 날짜를
    함께 강제해 특권 워커의 교차 사용자·교차 날짜 조회를 막는다.
    """
    rows = conn.execute(
        """
        select d.id::text, coalesce(n.headline, d.description, ''),
               d.detection_method, e.entity_type, e.name
        from public.differences d
        left join public.entities e
          on e.id = d.entity_id and e.user_id = d.user_id
        left join public.difference_narrations n
          on n.difference_id = d.id and n.user_id = d.user_id
        where d.user_id = %s
          and d.date = %s
          and d.status <> 'dismissed'
          and d.evidence_state = 'intact'
        order by d.id
        """,
        (user_id, target_date),
    ).fetchall()
    return [UsableDifference(r[0], r[1], r[2], r[3], r[4]) for r in rows]


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
        "regenerate_requested_at = null, regenerate_reason = null "
        "where id = %s",
        (diary_id,),
    )


def fetch_regenerate_requests(
    conn: psycopg.Connection,
) -> list[tuple[str, str]]:
    """다시 만들기 요청이 대기 중인 (user_id, date)만 반환한다.

    요청 유무를 보지 않으면 매 주기가 일기를 새로 만들어, 마감 탐지가 끝나기
    전에 차이 0건짜리 일기가 굳는다."""
    rows = conn.execute(
        """
        select user_id::text, date::text
          from public.diaries
         where regenerate_requested_at is not null
        """
    ).fetchall()
    return [(row[0], row[1]) for row in rows]


def request_late_diary_regeneration(
    conn: psycopg.Connection,
    user_id: str,
    target_date: date,
) -> bool:
    """Mark an existing owner-scoped diary without changing its body."""

    row = conn.execute(
        """
        update public.diaries
           set regenerate_requested_at = now(),
               regenerate_reason = 'late_record'
         where user_id = %s
           and date = %s
        returning id
        """,
        (user_id, target_date),
    ).fetchone()
    return row is not None


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


@dataclass(frozen=True)
class WeeklyMemoryRow:
    memory_id: str
    local_date: date


@dataclass(frozen=True)
class WeeklyOccurrenceRow:
    entity_id: str
    entity_type: str
    normalized_name: str
    memory_id: str
    local_date: date


@dataclass(frozen=True)
class WeeklyFirstOccurrenceRow:
    difference_id: str
    local_date: date
    entity_id: str
    normalized_name: str


@dataclass(frozen=True)
class WeeklyEmotionRow:
    memory_id: str
    local_date: date
    valence: float


@dataclass(frozen=True)
class WeeklyEmotionDifferenceRow:
    difference_id: str
    local_date: date


def fetch_weekly_anchor(conn: psycopg.Connection, user_id: str) -> date | None:
    """Return the owner's first active memory date in their own timezone."""

    row = conn.execute(
        """
        select min((m.effective_at at time zone u.timezone)::date)
        from public.memories m
        join public.users u on u.id = m.user_id
        where m.user_id = %s
          and m.deleted_at is null
          and m.is_locked = false
        """,
        (user_id,),
    ).fetchone()
    return row[0] if row and row[0] is not None else None


def fetch_weekly_memories(
    conn: psycopg.Connection,
    user_id: str,
    start_date: date,
    end_date: date,
) -> list[WeeklyMemoryRow]:
    rows = conn.execute(
        """
        select m.id::text, (m.effective_at at time zone u.timezone)::date
        from public.memories m
        join public.users u on u.id = m.user_id
        where m.user_id = %s
          and m.deleted_at is null
          and m.is_locked = false
          and (m.effective_at at time zone u.timezone)::date between %s and %s
        order by (m.effective_at at time zone u.timezone)::date, m.id
        """,
        (user_id, start_date, end_date),
    ).fetchall()
    return [WeeklyMemoryRow(row[0], row[1]) for row in rows]


def fetch_weekly_occurrences(
    conn: psycopg.Connection,
    user_id: str,
    start_date: date,
    end_date: date,
) -> list[WeeklyOccurrenceRow]:
    rows = conn.execute(
        """
        select e.id::text, e.entity_type, e.normalized_name, m.id::text,
               (m.effective_at at time zone u.timezone)::date
        from public.memory_entities me
        join public.memories m on m.id = me.memory_id
        join public.entities e on e.id = me.entity_id
        join public.users u on u.id = m.user_id
        where m.user_id = %s
          and e.user_id = %s
          and m.deleted_at is null
          and m.is_locked = false
          and (m.effective_at at time zone u.timezone)::date between %s and %s
        order by (m.effective_at at time zone u.timezone)::date, m.id, e.id
        """,
        (user_id, user_id, start_date, end_date),
    ).fetchall()
    return [WeeklyOccurrenceRow(*row) for row in rows]


def fetch_weekly_first_occurrences(
    conn: psycopg.Connection,
    user_id: str,
    start_date: date,
    end_date: date,
) -> list[WeeklyFirstOccurrenceRow]:
    rows = conn.execute(
        """
        select d.id::text, d.date, e.id::text, e.normalized_name
        from public.differences d
        join public.entities e
          on e.id = d.entity_id and e.user_id = d.user_id
        where d.user_id = %s
          and d.date between %s and %s
          and d.detection_method = 'first_occurrence'
          and d.status <> 'dismissed'
          and d.evidence_state = 'intact'
        order by d.date, e.normalized_name, e.id, d.id
        """,
        (user_id, start_date, end_date),
    ).fetchall()
    return [WeeklyFirstOccurrenceRow(*row) for row in rows]


def fetch_weekly_emotions(
    conn: psycopg.Connection,
    user_id: str,
    start_date: date,
    end_date: date,
) -> list[WeeklyEmotionRow]:
    rows = conn.execute(
        """
        select m.id::text, (m.effective_at at time zone u.timezone)::date,
               e.valence
        from public.emotions e
        join public.memories m on m.id = e.memory_id
        join public.users u on u.id = m.user_id
        where m.user_id = %s
          and m.deleted_at is null
          and m.is_locked = false
          and e.confirmed_by_user = true
          and e.valence is not null
          and (m.effective_at at time zone u.timezone)::date between %s and %s
        order by (m.effective_at at time zone u.timezone)::date, m.id
        """,
        (user_id, start_date, end_date),
    ).fetchall()
    return [WeeklyEmotionRow(row[0], row[1], float(row[2])) for row in rows]


def fetch_weekly_existing_emotion_differences(
    conn: psycopg.Connection,
    user_id: str,
    start_date: date,
    end_date: date,
) -> list[WeeklyEmotionDifferenceRow]:
    rows = conn.execute(
        """
        select id::text, date
        from public.differences
        where user_id = %s
          and date between %s and %s
          and entity_id is null
          and dimension = 'emotion'
          and detection_method = 'zscore'
          and status <> 'dismissed'
          and evidence_state = 'intact'
        order by date, id
        """,
        (user_id, start_date, end_date),
    ).fetchall()
    return [WeeklyEmotionDifferenceRow(*row) for row in rows]


def upsert_weekly_report(
    conn: psycopg.Connection,
    user_id: str,
    week_start: date,
) -> str:
    row = conn.execute(
        """
        insert into public.weekly_reports (user_id, week)
        values (%s, %s)
        on conflict (user_id, week) do update set week = excluded.week
        returning id::text
        """,
        (user_id, week_start.isoformat()),
    ).fetchone()
    return row[0]


def replace_weekly_highlights(
    conn: psycopg.Connection,
    user_id: str,
    report_id: str,
    highlights: list[tuple[str, str, int]],
) -> None:
    """Atomically replace highlights, linking only same-owner differences."""

    with conn.transaction():
        conn.execute(
            """
            delete from public.weekly_report_highlights h
            using public.weekly_reports w
            where h.report_id = w.id
              and w.id = %s
              and w.user_id = %s
            """,
            (report_id, user_id),
        )
        for difference_id, slot, rank in highlights:
            conn.execute(
                """
                insert into public.weekly_report_highlights
                  (report_id, difference_id, slot, rank)
                select w.id, d.id, %s, %s
                from public.weekly_reports w
                join public.differences d on d.id = %s
                where w.id = %s
                  and w.user_id = %s
                  and d.user_id = %s
                  and d.status <> 'dismissed'
                  and d.evidence_state = 'intact'
                on conflict (report_id, difference_id) do update
                  set slot = excluded.slot, rank = excluded.rank
                """,
                (
                    slot,
                    rank,
                    difference_id,
                    report_id,
                    user_id,
                    user_id,
                ),
            )


def fetch_active_users(conn: psycopg.Connection) -> list[tuple[str, str]]:
    """모든 사용자를 (user_id, timezone)으로 반환한다. 배치 대상 열거용.
    사용자별 '하루' 경계 계산에 timezone이 필요하다(time.local_date_for)."""
    rows = conn.execute(
        "select id::text, timezone from public.users order by id"
    ).fetchall()
    return [(r[0], r[1]) for r in rows]


def fetch_scheduled_users(
    conn: psycopg.Connection,
) -> list[tuple[str, str, int]]:
    """자동 일기 예약 계산에 필요한 최소 사용자 설정만 가져온다."""
    rows = conn.execute(
        "select id::text, timezone, diary_hour from public.users order by id"
    ).fetchall()
    return [(r[0], r[1], r[2]) for r in rows]


def insert_scheduled_diary_request(
    conn: psycopg.Connection,
    user_id: str,
    target_date_iso: str,
) -> str | None:
    """기록이 있고 일기가 없는 본인 날짜에 기존 요청 원장을 한 번만 만든다."""
    row = conn.execute(
        """
        insert into public.diary_generation_requests (user_id, date)
        select u.id, %s::date
          from public.users u
         where u.id = %s
           and not exists (
             select 1
               from public.diaries d
              where d.user_id = u.id
                and d.date = %s::date
           )
           and exists (
             select 1
               from public.memories m
              where m.user_id = u.id
                and m.is_locked = false
                and m.deleted_at is null
                and nullif(btrim(m.raw_text), '') is not null
                and (m.effective_at at time zone u.timezone)::date = %s::date
           )
        on conflict (user_id, date) do nothing
        returning id::text
        """,
        (target_date_iso, user_id, target_date_iso, target_date_iso),
    ).fetchone()
    return row[0] if row is not None else None


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
