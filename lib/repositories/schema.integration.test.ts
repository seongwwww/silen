import { describe, it, expect, beforeAll, afterAll, beforeEach } from "vitest";
import { Client } from "pg";
import { adminClient } from "./testSupport";

const CONNECTION_STRING =
  process.env.SUPABASE_DB_URL ?? "postgresql://postgres:postgres@127.0.0.1:54322/postgres";

const db = new Client({ connectionString: CONNECTION_STRING });

beforeAll(async () => {
  await db.connect();
});

afterAll(async () => {
  await db.end();
});

// 각 테스트는 깨끗한 상태에서 시작한다. auth.users를 지우면 CASCADE로
// public.users와 그 하위가 따라 사라지지만, ledger는 FK가 없으므로 따로 지운다.
beforeEach(async () => {
  await db.query("delete from public.deletions");
  const admin = adminClient();
  const { data } = await admin.auth.admin.listUsers({ perPage: 1000 });
  for (const user of data?.users ?? []) {
    await admin.auth.admin.deleteUser(user.id);
  }
});

async function createUser(label: string): Promise<string> {
  // public.users는 트리거가 만든다. 직접 insert하면 FK 위반이다.
  const admin = adminClient();
  const { data, error } = await admin.auth.admin.createUser({
    email: `${label}-${Date.now()}@test.local`,
    email_confirm: true,
  });
  if (error) throw error;
  return data.user.id;
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
    const userId = await createUser("cascade");
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
    const userId = await createUser("stale");
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
    const userId = await createUser("children");
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
    const userId = await createUser("highlight");
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
    const userId = await createUser("diary");
    await db.query("insert into public.diaries (user_id, date) values ($1, '2026-03-01')", [
      userId,
    ]);

    await expect(
      db.query("insert into public.diaries (user_id, date) values ($1, '2026-03-01')", [userId]),
    ).rejects.toThrow(/duplicate key/);
  });

  it("같은 대상에 진행 중인 삭제가 둘 존재할 수 없다", async () => {
    const userId = await createUser("ledger");
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
    const userId = await createUser("ledger2");
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
    const userId = await createUser("account");
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

describe("프로필 자동 생성", () => {
  it("auth 사용자가 생기면 public.users 행이 따라 생긴다", async () => {
    const userId = await createUser("profile");

    const rows = await db.query("select id from public.users where id = $1", [userId]);
    expect(rows.rowCount).toBe(1);
  });

  it("auth 사용자를 지우면 public.users 행도 사라진다", async () => {
    const userId = await createUser("cascade-auth");
    const admin = adminClient();

    await admin.auth.admin.deleteUser(userId);

    const rows = await db.query("select id from public.users where id = $1", [userId]);
    expect(rows.rowCount).toBe(0);
  });

  it("익명 전환 전에 남긴 기록이 전환 후에도 같은 사용자 것이다", async () => {
    // Task 1에서 옮겨왔다. 프로필 트리거가 있어야 memories 삽입이 가능하다.
    const { anonClient, latestMessageTo, extractTokenHash, clearMailbox } = await import(
      "./testSupport"
    );
    await clearMailbox();

    const client = anonClient();
    const { data: anon } = await client.auth.signInAnonymously();
    const anonymousId = anon.user!.id;

    const admin = adminClient();
    const { error: insertError } = await admin
      .from("memories")
      .insert({ user_id: anonymousId, source_type: "manual", memory_type: "moment" });
    expect(insertError).toBeNull();

    const address = `keep-${anonymousId.slice(0, 8)}@test.local`;
    await client.auth.updateUser({ email: address });
    const tokenHash = extractTokenHash(await latestMessageTo(address));
    await client.auth.verifyOtp({ token_hash: tokenHash, type: "email_change" });

    const { data: rows } = await admin.from("memories").select("id").eq("user_id", anonymousId);
    expect(rows?.length).toBe(1);
  });
});
