"""통합 테스트 공용. auth.users를 직접 시드하고(트리거가 public.users 생성),
메모를 만든다. 로컬 postgres 슈퍼유저로 접속하므로 auth 스키마에 쓸 수 있다."""

import uuid

import psycopg
import pytest

from silen_worker.db import dsn


@pytest.fixture
def conn() -> psycopg.Connection:
    c = psycopg.connect(dsn(), autocommit=True)
    yield c
    c.close()


def seed_user(conn: psycopg.Connection) -> str:
    """최소 auth.users 행을 만든다. handle_new_user 트리거가 public.users를 만든다."""
    user_id = str(uuid.uuid4())
    conn.execute(
        """
        insert into auth.users
          (instance_id, id, aud, role, email, encrypted_password,
           email_confirmed_at, raw_app_meta_data, raw_user_meta_data,
           created_at, updated_at, confirmation_token, email_change,
           email_change_token_new, recovery_token)
        values
          ('00000000-0000-0000-0000-000000000000', %s, 'authenticated',
           'authenticated', %s, '', now(),
           '{"provider":"email","providers":["email"]}', '{}',
           now(), now(), '', '', '', '')
        """,
        (user_id, f"worker-{user_id[:8]}@example.com"),
    )
    return user_id


def seed_memory(conn: psycopg.Connection, user_id: str, text: str | None = "메모") -> str:
    row = conn.execute(
        "insert into public.memories (user_id, raw_text, source_type, memory_type) "
        "values (%s, %s, 'manual', 'moment') returning id::text",
        (user_id, text),
    ).fetchone()
    return row[0]


def seed_memory_at(
    conn: psycopg.Connection, user_id: str, captured_at_iso: str, text: str | None = "메모"
) -> str:
    """captured_at을 명시해 메모를 시드한다(타임존 경계 테스트용)."""
    row = conn.execute(
        "insert into public.memories (user_id, raw_text, source_type, memory_type, captured_at) "
        "values (%s, %s, 'manual', 'moment', %s) returning id::text",
        (user_id, text, captured_at_iso),
    ).fetchone()
    return row[0]


def delete_user(conn: psycopg.Connection, user_id: str) -> None:
    # auth.users 삭제가 CASCADE로 public.users·memories를 지운다.
    conn.execute("delete from auth.users where id = %s", (user_id,))
