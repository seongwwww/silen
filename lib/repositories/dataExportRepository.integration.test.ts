import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { Client } from "pg";
import { createClient, type SupabaseClient } from "@supabase/supabase-js";
import {
  adminClient,
  ANON_KEY,
  cleanupTestUser,
  SUPABASE_URL,
} from "./testSupport";
import { createDataExportRepository } from "./dataExportRepository";

const CONNECTION_STRING =
  process.env.SUPABASE_DB_URL ??
  "postgresql://postgres:postgres@127.0.0.1:54322/postgres";

let admin: SupabaseClient;
let db: Client;
let aliceId: string;
let bobId: string;
let aliceEmail: string;
let bobEmail: string;
type GraphIds = {
  memoryId: string;
  entityId: string;
  differenceId: string;
  diaryId: string;
  reportId: string;
};
let aliceGraph: GraphIds;
let bobGraph: GraphIds;

async function clientFor(email: string): Promise<SupabaseClient> {
  const { data, error } = await admin.auth.admin.generateLink({
    type: "magiclink",
    email,
  });
  if (error || !data.properties) throw error ?? new Error("magiclink 실패");

  const client = createClient(SUPABASE_URL, ANON_KEY, {
    auth: { autoRefreshToken: false, persistSession: false },
  });
  const { error: verifyError } = await client.auth.verifyOtp({
    token_hash: data.properties.hashed_token,
    type: "magiclink",
  });
  if (verifyError) throw verifyError;
  return client;
}

async function seedExportGraph(
  userId: string,
  marker: string,
): Promise<GraphIds> {
  const memory = await db.query<{ id: string }>(
    `insert into public.memories
       (user_id, raw_text, source_type, memory_type)
     values ($1, $2, 'manual', 'moment')
     returning id`,
    [userId, `${marker}-memory`],
  );
  const memoryId = memory.rows[0].id;
  await db.query(
    `insert into public.emotions
       (memory_id, valence, tags, confidence, confirmed_by_user)
     values ($1, 0.5, array['calm'], 0.9, true)`,
    [memoryId],
  );
  await db.query(
    `insert into public.assets
       (memory_id, asset_type, file_url, extracted_text, mime_type)
     values ($1, 'photo', $2, $3, 'image/jpeg')`,
    [memoryId, `${userId}/photo.jpg`, `${marker}-ocr-private`],
  );

  const entity = await db.query<{ id: string }>(
    `insert into public.entities
       (user_id, entity_type, name, normalized_name)
     values ($1, 'thing', $2, $2)
     returning id`,
    [userId, `${marker}-entity`],
  );
  const entityId = entity.rows[0].id;
  await db.query(
    `insert into public.memory_entities
       (memory_id, entity_id, relation_type, confidence)
     values ($1, $2, 'did', 0.8)`,
    [memoryId, entityId],
  );

  const difference = await db.query<{ id: string }>(
    `insert into public.differences
       (user_id, date, entity_id, dimension, description,
        detection_method, confidence, category)
     values ($1, '2026-07-20', $2, 'thing', '통계 근거',
             'freq_shift', 3.2, '오늘의다른점')
     returning id`,
    [userId, entityId],
  );
  const differenceId = difference.rows[0].id;
  await db.query(
    `insert into public.difference_narrations
       (user_id, difference_id, headline, body, evidence_text, model)
     values ($1, $2, $3, $4, '통계 비교', 'stub')`,
    [
      userId,
      differenceId,
      `${marker}-headline`,
      `${marker}-narration`,
    ],
  );
  await db.query(
    `insert into public.difference_evidence (difference_id, memory_id)
     values ($1, $2)`,
    [differenceId, memoryId],
  );

  const diary = await db.query<{ id: string }>(
    `insert into public.diaries
       (user_id, date, generated_text)
     values ($1, '2026-07-20', $2)
     returning id`,
    [userId, `${marker}-diary`],
  );
  const diaryId = diary.rows[0].id;
  await db.query(
    `insert into public.diary_sections
       (diary_id, difference_id, section_type, content)
     values ($1, $2, '본문', $3)`,
    [diaryId, differenceId, `${marker}-section`],
  );
  await db.query(
    `insert into public.diary_sources (diary_id, memory_id)
     values ($1, $2)`,
    [diaryId, memoryId],
  );

  const report = await db.query<{ id: string }>(
    `insert into public.weekly_reports (user_id, week)
     values ($1, '2026-W30')
     returning id`,
    [userId],
  );
  await db.query(
    `insert into public.weekly_report_highlights
       (report_id, difference_id, slot, rank)
     values ($1, $2, '처음한것', 1)`,
    [report.rows[0].id, differenceId],
  );
  return {
    memoryId,
    entityId,
    differenceId,
    diaryId,
    reportId: report.rows[0].id,
  };
}

beforeAll(async () => {
  admin = adminClient();
  db = new Client({ connectionString: CONNECTION_STRING });
  await db.connect();

  const unique = `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  aliceEmail = `export-alice-${unique}@test.local`;
  bobEmail = `export-bob-${unique}@test.local`;
  const { data: alice } = await admin.auth.admin.createUser({
    email: aliceEmail,
    email_confirm: true,
  });
  const { data: bob } = await admin.auth.admin.createUser({
    email: bobEmail,
    email_confirm: true,
  });
  aliceId = alice.user!.id;
  bobId = bob.user!.id;

  aliceGraph = await seedExportGraph(aliceId, "alice-export");
  bobGraph = await seedExportGraph(bobId, "bob-export");

  // 서비스 역할이 잘못 연결한 교차 사용자 FK가 있어도 export가 ID를 누출하지
  // 않는지 검증한다. 부모 RLS만으로는 반대편 소유자를 보장하지 못한다.
  await db.query(
    `insert into public.memory_entities
       (memory_id, entity_id, relation_type)
     values ($1, $2, 'visited')`,
    [aliceGraph.memoryId, bobGraph.entityId],
  );
  await db.query(
    `insert into public.difference_evidence (difference_id, memory_id)
     values ($1, $2)`,
    [aliceGraph.differenceId, bobGraph.memoryId],
  );
  await db.query(
    `insert into public.diary_sources (diary_id, memory_id)
     values ($1, $2)`,
    [aliceGraph.diaryId, bobGraph.memoryId],
  );
  await db.query(
    `insert into public.weekly_report_highlights
       (report_id, difference_id, slot, rank)
     values ($1, $2, '감정순간', 2)`,
    [aliceGraph.reportId, bobGraph.differenceId],
  );
  await db.query(
    `insert into public.diary_sections
       (diary_id, difference_id, section_type, content)
     values ($1, $2, '다른점', 'alice-owned-cross-reference')`,
    [aliceGraph.diaryId, bobGraph.differenceId],
  );
});

afterAll(async () => {
  await cleanupTestUser(aliceId, db);
  await cleanupTestUser(bobId, db);
  await db.end();
});

describe("dataExportRepository", () => {
  it("본인의 전체 기록 그래프를 읽되 사진 바이너리·추출 본문은 싣지 않는다", async () => {
    const repository = createDataExportRepository(
      await clientFor(aliceEmail),
    );

    const data = await repository.findAllByUserId(aliceId);

    expect(data.memories[0].raw_text).toBe("alice-export-memory");
    expect(data.emotions).toHaveLength(1);
    expect(data.assets).toHaveLength(1);
    expect(data.assets[0]).not.toHaveProperty("extracted_text");
    expect(data.assets[0]).not.toHaveProperty("transcription");
    expect(data.entities[0].name).toBe("alice-export-entity");
    expect(data.memory_entities).toHaveLength(1);
    expect(data.memory_entities[0].entity_id).toBe(aliceGraph.entityId);
    expect(data.differences).toHaveLength(1);
    expect(data.difference_narrations[0].body).toBe(
      "alice-export-narration",
    );
    expect(data.difference_evidence).toHaveLength(1);
    expect(data.difference_evidence[0].memory_id).toBe(
      aliceGraph.memoryId,
    );
    expect(data.diaries[0].generated_text).toBe("alice-export-diary");
    expect(data.diary_sections[0].content).toBe("alice-export-section");
    expect(data.diary_sources).toHaveLength(1);
    expect(data.diary_sources[0].memory_id).toBe(aliceGraph.memoryId);
    expect(data.weekly_reports).toHaveLength(1);
    expect(data.weekly_report_highlights).toHaveLength(1);
    expect(data.weekly_report_highlights[0].difference_id).toBe(
      aliceGraph.differenceId,
    );
    expect(
      data.diary_sections.find(
        (row) => row.content === "alice-owned-cross-reference",
      )?.difference_id,
    ).toBeNull();
    expect(JSON.stringify(data)).not.toContain("bob-export");
  });

  it("Alice 세션으로 Bob id를 요청해도 RLS가 모든 컬렉션을 비운다", async () => {
    const repository = createDataExportRepository(
      await clientFor(aliceEmail),
    );

    const forged = await repository.findAllByUserId(bobId);

    for (const rows of Object.values(forged)) {
      expect(rows).toEqual([]);
    }
  });
});
