import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { createClient, type SupabaseClient } from "@supabase/supabase-js";
import { Client } from "pg";
import {
  adminClient,
  ANON_KEY,
  cleanupTestUser,
  SUPABASE_URL,
} from "./testSupport";
import { createWeeklyRepository } from "./weeklyRepository";

const CONNECTION_STRING =
  process.env.SUPABASE_DB_URL ??
  "postgresql://postgres:postgres@127.0.0.1:54322/postgres";

let admin: SupabaseClient;
let db: Client;
let alice: string;
let bob: string;

async function clientFor(email: string): Promise<SupabaseClient> {
  const { data } = await admin.auth.admin.generateLink({
    type: "magiclink",
    email,
  });
  if (!data.properties) throw new Error("magiclink 발급 실패");
  const client = createClient(SUPABASE_URL, ANON_KEY, {
    auth: { autoRefreshToken: false, persistSession: false },
  });
  await client.auth.verifyOtp({
    token_hash: data.properties.hashed_token,
    type: "magiclink",
  });
  return client;
}

async function seedDifference({
  userId,
  date,
  method,
  category,
  description,
  confidence,
  entityName,
  evidenceState = "intact",
}: {
  userId: string;
  date: string;
  method: "pattern" | "first_occurrence" | "zscore";
  category: "패턴" | "오늘의다른점" | "감정전환";
  description: string;
  confidence: number;
  entityName?: string;
  evidenceState?: "intact" | "stale";
}): Promise<string> {
  let entityId: string | null = null;
  if (entityName) {
    entityId = (
      await db.query(
        `insert into public.entities
           (user_id, entity_type, name, normalized_name)
         values ($1, 'thing', $2, $3)
         returning id`,
        [userId, entityName, entityName.toLowerCase()],
      )
    ).rows[0].id;
  }
  return (
    await db.query(
      `insert into public.differences
         (user_id, date, entity_id, dimension, description,
          detection_method, confidence, category, evidence_state)
       values ($1, $2, $3, 'weekly', $4, $5, $6, $7, $8)
       returning id`,
      [
        userId,
        date,
        entityId,
        description,
        method,
        confidence,
        category,
        evidenceState,
      ],
    )
  ).rows[0].id;
}

beforeAll(async () => {
  admin = adminClient();
  db = new Client({ connectionString: CONNECTION_STRING });
  await db.connect();
  alice = (
    await admin.auth.admin.createUser({
      email: "weekly-report-alice@example.com",
      email_confirm: true,
    })
  ).data.user!.id;
  bob = (
    await admin.auth.admin.createUser({
      email: "weekly-report-bob@example.com",
      email_confirm: true,
    })
  ).data.user!.id;

  for (const capturedAt of [
    "2026-07-21T09:00:00Z",
    "2026-07-22T09:00:00Z",
    "2026-07-22T10:00:00Z",
    "2026-07-22T11:00:00Z",
  ]) {
    await db.query(
      `insert into public.memories
         (user_id, captured_at, raw_text, source_type, memory_type)
       values ($1, $2, '주간 리포트용 기록', 'manual', 'moment')`,
      [alice, capturedAt],
    );
  }
  await db.query(
    `insert into public.memories
       (user_id, captured_at, raw_text, source_type, memory_type)
     values ($1, '2026-07-21T10:00:00Z', null, 'manual', 'moment')`,
    [alice],
  );
  await db.query(
    `insert into public.memories
       (user_id, captured_at, raw_text, source_type, memory_type, is_locked)
     values ($1, '2026-07-22T12:00:00Z', '잠긴 기록', 'manual', 'moment', true)`,
    [alice],
  );
  await db.query(
    `insert into public.memories
       (user_id, captured_at, raw_text, source_type, memory_type, deleted_at)
     values ($1, '2026-07-22T13:00:00Z', '삭제 기록', 'manual', 'moment', now())`,
    [alice],
  );

  const reportId = (
    await db.query(
      "insert into public.weekly_reports (user_id, week) values ($1, '2026-07-21') returning id",
      [alice],
    )
  ).rows[0].id;
  const most = await seedDifference({
    userId: alice,
    date: "2026-07-21",
    method: "pattern",
    category: "패턴",
    description: "7일 기록에서 3회 언급",
    confidence: 2.2,
    entityName: "김밥",
  });
  const first = await seedDifference({
    userId: alice,
    date: "2026-07-22",
    method: "first_occurrence",
    category: "오늘의다른점",
    description: "처음 등장",
    confidence: 4.8,
    entityName: "새 노래",
  });
  const stale = await seedDifference({
    userId: alice,
    date: "2026-07-23",
    method: "zscore",
    category: "감정전환",
    description: "근거가 사라진 감정 차이",
    confidence: 8,
    evidenceState: "stale",
  });
  await db.query(
    `insert into public.weekly_report_highlights
       (report_id, difference_id, slot, rank)
     values ($1, $2, '가장많이한것', 1),
            ($1, $3, '처음한것', 1),
            ($1, $4, '감정순간', 1)`,
    [reportId, most, first, stale],
  );

  await db.query(
    "insert into public.weekly_reports (user_id, week) values ($1, '2026-07-21')",
    [bob],
  );
});

afterAll(async () => {
  await cleanupTestUser(alice, db);
  await cleanupTestUser(bob, db);
  await db.end();
});

describe("weeklyRepository", () => {
  it("본인 최신 리포트의 7일 막대와 intact 슬롯만 조회한다", async () => {
    const repo = createWeeklyRepository(
      await clientFor("weekly-report-alice@example.com"),
    );

    const report = await repo.findLatest(alice, "UTC");

    expect(report?.weekStart).toBe("2026-07-21");
    expect(report?.weekEnd).toBe("2026-07-27");
    expect(report?.days).toHaveLength(7);
    expect(report?.days[0]).toMatchObject({ date: "2026-07-21", count: 2 });
    expect(report?.days[1]).toMatchObject({
      date: "2026-07-22",
      count: 3,
      isSurprising: true,
    });
    expect(report?.highlights.가장많이한것?.headline).toBe("김밥");
    expect(report?.highlights.가장많이한것?.detail).toBe(
      "7일 기록에서 3번 언급됐어요.",
    );
    expect(report?.highlights.처음한것?.headline).toBe("새 노래");
    expect(report?.highlights.감정순간).toBeNull();
  });

  it("요청 user_id와 RLS가 모두 타 사용자 리포트를 차단한다", async () => {
    const repo = createWeeklyRepository(
      await clientFor("weekly-report-bob@example.com"),
    );

    expect(await repo.findLatest(alice, "UTC")).toBeNull();
  });
});
