import { describe, it, expect, beforeAll, afterAll } from "vitest";
import { Client } from "pg";
import { createClient, type SupabaseClient } from "@supabase/supabase-js";
import { adminClient, cleanupTestUser, SUPABASE_URL, ANON_KEY } from "./testSupport";
import { createDifferenceRepository } from "./differenceRepository";

const CONNECTION_STRING =
  process.env.SUPABASE_DB_URL ?? "postgresql://postgres:postgres@127.0.0.1:54322/postgres";

let admin: SupabaseClient, db: Client, alice: string, bob: string;

async function clientFor(email: string): Promise<SupabaseClient> {
  const { data } = await admin.auth.admin.generateLink({ type: "magiclink", email });
  const c = createClient(SUPABASE_URL, ANON_KEY, { auth: { autoRefreshToken: false, persistSession: false } });
  if (!data.properties) throw new Error("magiclink 발급 실패");
  await c.auth.verifyOtp({ token_hash: data.properties.hashed_token, type: "magiclink" });
  return c;
}

async function seedCandidate(user: string, headline: string, memoText: string): Promise<string> {
  const ent = (await db.query(
    "insert into public.entities (user_id, entity_type, name, normalized_name) values ($1,'thing',$2,$2) returning id",
    [user, headline])).rows[0].id;
  const diff = (await db.query(
    "insert into public.differences (user_id, date, entity_id, dimension, description, detection_method, category, status, evidence_state) " +
    "values ($1, current_date, $2, 'thing', 'x', 'freq_shift', '오늘의다른점', 'candidate', 'intact') returning id",
    [user, ent])).rows[0].id;
  await db.query("insert into public.difference_narrations (user_id, difference_id, headline, body, evidence_text, model) values ($1,$2,$3,'b','e','m')",
    [user, diff, headline]);
  const mem = (await db.query("insert into public.memories (user_id, raw_text, source_type, memory_type) values ($1,$2,'manual','moment') returning id",
    [user, memoText])).rows[0].id;
  await db.query("insert into public.difference_evidence (difference_id, memory_id) values ($1,$2)", [diff, mem]);
  return diff;
}

beforeAll(async () => {
  admin = adminClient();
  db = new Client({ connectionString: CONNECTION_STRING }); await db.connect();
  alice = (await admin.auth.admin.createUser({ email: "alice-diff@example.com", email_confirm: true })).data.user!.id;
  bob = (await admin.auth.admin.createUser({ email: "bob-diff@example.com", email_confirm: true })).data.user!.id;
});
afterAll(async () => {
  await cleanupTestUser(alice, db);
  await cleanupTestUser(bob, db);
  await db.end();
});

describe("차이 확인 저장소", () => {
  it("narrated candidate + 근거 메모를 조회한다", async () => {
    const diff = await seedCandidate(alice, "3일째 김밥", "점심에 김밥");
    const repo = createDifferenceRepository(await clientFor("alice-diff@example.com"));
    const items = await repo.listCandidatesForReview();
    const item = items.find((i) => i.id === diff);
    expect(item).toBeTruthy();
    expect(item!.headline).toBe("3일째 김밥");
    expect(item!.evidence).toContain("점심에 김밥");
  });

  it("본인 차이 status를 바꾼다", async () => {
    const diff = await seedCandidate(alice, "새 카페", "처음 간 카페");
    const repo = createDifferenceRepository(await clientFor("alice-diff@example.com"));
    expect(await repo.updateStatus(diff, "confirmed", "candidate")).toBe(true);
    const row = await db.query("select status from public.differences where id=$1", [diff]);
    expect(row.rows[0].status).toBe("confirmed");
  });

  it("타인 차이는 RLS로 못 바꾼다(0행)", async () => {
    const diff = await seedCandidate(alice, "앨리스 차이", "앨리스 메모");
    const bobRepo = createDifferenceRepository(await clientFor("bob-diff@example.com"));
    expect(await bobRepo.updateStatus(diff, "confirmed", "candidate")).toBe(false);
    const row = await db.query("select status from public.differences where id=$1", [diff]);
    expect(row.rows[0].status).toBe("candidate"); // 안 바뀜
  });

  it("기대한 현재 상태와 다르면 바꾸지 않는다(TOCTOU 방어)", async () => {
    // 읽은 뒤 update 사이에 다른 요청이 status를 바꾼 상황을 재현한다.
    const diff = await seedCandidate(alice, "경쟁 차이", "경쟁 메모");
    const repo = createDifferenceRepository(await clientFor("alice-diff@example.com"));
    expect(await repo.updateStatus(diff, "confirmed", "candidate")).toBe(true);

    // 이제 confirmed인데, candidate를 기대한 두 번째 요청이 도착 → 미갱신.
    expect(await repo.updateStatus(diff, "dismissed", "candidate")).toBe(false);
    const row = await db.query("select status from public.differences where id=$1", [diff]);
    expect(row.rows[0].status).toBe("confirmed"); // 직접 전이 우회 차단
  });
});
