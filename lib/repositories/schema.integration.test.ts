import { describe, it, expect, beforeAll, afterAll, beforeEach } from "vitest";
import { Client } from "pg";

const CONNECTION_STRING =
  process.env.SUPABASE_DB_URL ?? "postgresql://postgres:postgres@127.0.0.1:54322/postgres";

const db = new Client({ connectionString: CONNECTION_STRING });

beforeAll(async () => {
  await db.connect();
});

afterAll(async () => {
  await db.end();
});

// 각 테스트는 깨끗한 상태에서 시작한다. users를 지우면 CASCADE로
// 대부분이 따라 사라지지만, ledger는 FK가 없으므로 따로 지운다.
beforeEach(async () => {
  await db.query("delete from public.deletions");
  await db.query("delete from public.users");
});

async function createUser(email: string): Promise<string> {
  const result = await db.query<{ id: string }>(
    "insert into public.users (email) values ($1) returning id",
    [email],
  );
  return result.rows[0].id;
}

async function createMemory(userId: string): Promise<string> {
  const result = await db.query<{ id: string }>(
    `insert into public.memories (user_id, source_type, memory_type)
     values ($1, 'manual', 'moment') returning id`,
    [userId],
  );
  return result.rows[0].id;
}

async function createDifference(userId: string): Promise<string> {
  const result = await db.query<{ id: string }>(
    `insert into public.differences (user_id, date, dimension, detection_method, category)
     values ($1, '2026-03-01', '퇴근시간', 'zscore', '오늘의다른점') returning id`,
    [userId],
  );
  return result.rows[0].id;
}

describe("삭제 연쇄", () => {
  it("메모를 지우면 근거 링크가 함께 사라진다", async () => {
    const userId = await createUser("cascade@test.local");
    const memoryId = await createMemory(userId);
    const differenceId = await createDifference(userId);
    await db.query(
      "insert into public.difference_evidence (difference_id, memory_id) values ($1, $2)",
      [differenceId, memoryId],
    );

    await db.query("delete from public.memories where id = $1", [memoryId]);

    const links = await db.query(
      "select 1 from public.difference_evidence where difference_id = $1",
      [differenceId],
    );
    expect(links.rowCount).toBe(0);
  });

  it("근거 메모가 사라져도 difference 행은 남는다", async () => {
    // ADR-0002: 삭제가 아니라 무효화. 사용자의 status 판단을 보존한다.
    const userId = await createUser("stale@test.local");
    const memoryId = await createMemory(userId);
    const differenceId = await createDifference(userId);
    await db.query(
      "insert into public.difference_evidence (difference_id, memory_id) values ($1, $2)",
      [differenceId, memoryId],
    );

    await db.query("delete from public.memories where id = $1", [memoryId]);

    const rows = await db.query("select evidence_state from public.differences where id = $1", [
      differenceId,
    ]);
    expect(rows.rowCount).toBe(1);
    expect(rows.rows[0]).toEqual({ evidence_state: "intact" });
  });

  it("메모를 지우면 딸린 asset과 emotion도 사라진다", async () => {
    const userId = await createUser("children@test.local");
    const memoryId = await createMemory(userId);
    await db.query(
      `insert into public.assets (memory_id, asset_type, file_url)
       values ($1, 'photo', 'https://example.invalid/a.jpg')`,
      [memoryId],
    );
    await db.query("insert into public.emotions (memory_id, valence) values ($1, 0.5)", [memoryId]);

    await db.query("delete from public.memories where id = $1", [memoryId]);

    const assets = await db.query("select 1 from public.assets where memory_id = $1", [memoryId]);
    const emotions = await db.query("select 1 from public.emotions where memory_id = $1", [
      memoryId,
    ]);
    expect(assets.rowCount).toBe(0);
    expect(emotions.rowCount).toBe(0);
  });

  it("difference를 지우면 주간 리포트 하이라이트도 사라진다", async () => {
    const userId = await createUser("highlight@test.local");
    const differenceId = await createDifference(userId);
    const report = await db.query<{ id: string }>(
      "insert into public.weekly_reports (user_id, week) values ($1, '2026-W10') returning id",
      [userId],
    );
    await db.query(
      `insert into public.weekly_report_highlights (report_id, difference_id, slot, rank)
       values ($1, $2, '처음한것', 1)`,
      [report.rows[0].id, differenceId],
    );

    await db.query("delete from public.differences where id = $1", [differenceId]);

    const highlights = await db.query(
      "select 1 from public.weekly_report_highlights where difference_id = $1",
      [differenceId],
    );
    expect(highlights.rowCount).toBe(0);
  });
});

describe("멱등성 제약", () => {
  it("같은 날짜에 일기를 두 번 만들 수 없다", async () => {
    const userId = await createUser("diary@test.local");
    await db.query("insert into public.diaries (user_id, date) values ($1, '2026-03-01')", [
      userId,
    ]);

    await expect(
      db.query("insert into public.diaries (user_id, date) values ($1, '2026-03-01')", [userId]),
    ).rejects.toThrow(/duplicate key/);
  });

  it("같은 대상에 진행 중인 삭제가 둘 존재할 수 없다", async () => {
    const userId = await createUser("ledger@test.local");
    const targetId = "00000000-0000-0000-0000-000000000001";
    await db.query(
      `insert into public.deletions (user_id, trigger, target_type, target_id)
       values ($1, 'memory', 'memory', $2)`,
      [userId, targetId],
    );

    await expect(
      db.query(
        `insert into public.deletions (user_id, trigger, target_type, target_id)
         values ($1, 'memory', 'memory', $2)`,
        [userId, targetId],
      ),
    ).rejects.toThrow(/duplicate key/);
  });

  it("완료된 삭제는 같은 대상의 새 요청을 막지 않는다", async () => {
    const userId = await createUser("ledger2@test.local");
    const targetId = "00000000-0000-0000-0000-000000000002";
    await db.query(
      `insert into public.deletions (user_id, trigger, target_type, target_id, status, completed_at)
       values ($1, 'memory', 'memory', $2, 'completed', now())`,
      [userId, targetId],
    );

    const result = await db.query(
      `insert into public.deletions (user_id, trigger, target_type, target_id)
       values ($1, 'memory', 'memory', $2) returning id`,
      [userId, targetId],
    );
    expect(result.rowCount).toBe(1);
  });

  it("계정을 지워도 ledger는 남는다", async () => {
    // ADR-0002: ledger에 users FK가 없는 이유. 삭제가 끝나기 전에
    // 진행 상태를 잃으면 재개가 불가능해진다.
    const userId = await createUser("account@test.local");
    await db.query(
      `insert into public.deletions (user_id, trigger, target_type, target_id)
       values ($1, 'account', 'user', $1)`,
      [userId],
    );

    await db.query("delete from public.users where id = $1", [userId]);

    const rows = await db.query("select 1 from public.deletions where user_id = $1", [userId]);
    expect(rows.rowCount).toBe(1);
  });
});

describe("RLS", () => {
  it("모든 사용자 데이터 테이블에 RLS가 켜져 있다", async () => {
    // 확장이 만든 테이블은 제외한다. PostGIS가 public에 spatial_ref_sys를
    // 만드는데 이건 우리 소유가 아니고 RLS 대상도 아니다.
    const result = await db.query<{ tablename: string }>(
      `select t.tablename
         from pg_tables t
        where t.schemaname = 'public'
          and t.rowsecurity = false
          and not exists (
            select 1
              from pg_depend d
              join pg_class c on c.oid = d.objid
             where c.relname = t.tablename
               and c.relnamespace = 'public'::regnamespace
               and d.deptype = 'e'
          )`,
    );
    expect(result.rows.map((row) => row.tablename)).toEqual([]);
  });
});
