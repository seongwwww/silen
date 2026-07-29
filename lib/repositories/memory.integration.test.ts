import { describe, it, expect, beforeAll, afterAll } from "vitest";
import { Client } from "pg";
import { createClient, type SupabaseClient } from "@supabase/supabase-js";
import {
  adminClient,
  cleanupTestUser,
  SUPABASE_URL,
  ANON_KEY,
} from "./testSupport";
import { createMemoryRepository } from "./memoryRepository";
import { createMemory } from "@/lib/services/memory";

const CONNECTION_STRING =
  process.env.SUPABASE_DB_URL ?? "postgresql://postgres:postgres@127.0.0.1:54322/postgres";

let admin: SupabaseClient;
let db: Client;
let alice: string;
let bob: string;

async function clientFor(email: string): Promise<SupabaseClient> {
  const { data, error } = await admin.auth.admin.generateLink({ type: "magiclink", email });
  if (error) throw error;
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

beforeAll(async () => {
  admin = adminClient();
  db = new Client({ connectionString: CONNECTION_STRING });
  await db.connect();
  const { data: a } = await admin.auth.admin.createUser({
    email: "alice-mem@example.com",
    email_confirm: true,
  });
  const { data: b } = await admin.auth.admin.createUser({
    email: "bob-mem@example.com",
    email_confirm: true,
  });
  alice = a.user!.id;
  bob = b.user!.id;
});

afterAll(async () => {
  await cleanupTestUser(alice, db);
  await cleanupTestUser(bob, db);
  await db.end();
});

describe("메모 생성", () => {
  it("텍스트+감정 메모가 memories·emotions 행으로 생긴다", async () => {
    const client = await clientFor("alice-mem@example.com");
    const repo = createMemoryRepository(client);

    const { memoryId } = await createMemory(repo, {
      userId: alice,
      text: "오늘 그 노래 또 들음",
      emotion: "good",
    });

    const mem = await db.query(
      "select raw_text, memory_type, source_type from public.memories where id = $1",
      [memoryId],
    );
    expect(mem.rows[0]).toEqual({
      raw_text: "오늘 그 노래 또 들음",
      memory_type: "moment",
      source_type: "manual",
    });
    const emo = await db.query(
      "select valence, confirmed_by_user from public.emotions where memory_id = $1",
      [memoryId],
    );
    expect(emo.rows[0]).toEqual({ valence: 1, confirmed_by_user: true });
  });

  it("사진만 있는 메모가 assets 행으로 생긴다", async () => {
    const client = await clientFor("alice-mem@example.com");
    const repo = createMemoryRepository(client);

    const { memoryId } = await createMemory(repo, {
      userId: alice,
      assetPaths: [`${alice}/photo.jpg`],
    });

    const asset = await db.query(
      "select asset_type, file_url, mime_type from public.assets where memory_id = $1",
      [memoryId],
    );
    expect(asset.rows[0]).toEqual({
      asset_type: "photo",
      file_url: `${alice}/photo.jpg`,
      mime_type: "image/jpeg",
    });
  });

  it("남의 user_id로 위조 insert하면 RLS가 막는다", async () => {
    // Alice의 세션 클라이언트로 Bob 소유의 메모를 만들려 하면 with-check 위반.
    const client = await clientFor("alice-mem@example.com");
    const repo = createMemoryRepository(client);

    await expect(
      repo.insertMemory({ userId: bob, rawText: "위조", occurredAt: null }),
    ).rejects.toBeTruthy();
  });
});

describe("회고 검색", () => {
  it("본인 활성 본문만 최신순으로 찾고 잠금·삭제·타 사용자를 제외한다", async () => {
    const rows = [
      [alice, "회고키 오래된 기록", "2026-07-10T00:00:00Z", false, null],
      [alice, "회고키 최신 기록", "2026-07-20T00:00:00Z", false, null],
      [alice, "회고키 잠긴 기록", "2026-07-21T00:00:00Z", true, null],
      [alice, "회고키 삭제 기록", "2026-07-22T00:00:00Z", false, "2026-07-23T00:00:00Z"],
      [bob, "회고키 타인 기록", "2026-07-24T00:00:00Z", false, null],
    ];
    for (const row of rows) {
      await db.query(
        "insert into public.memories " +
          "(user_id, raw_text, captured_at, source_type, memory_type, is_locked, deleted_at) " +
          "values ($1,$2,$3,'manual','moment',$4,$5)",
        row,
      );
    }
    const repo = createMemoryRepository(await clientFor("alice-mem@example.com"));

    const result = await repo.search(alice, "회고키");

    expect(result.map((item) => item.rawText)).toEqual([
      "회고키 최신 기록",
      "회고키 오래된 기록",
    ]);
    await expect(repo.search(bob, "회고키")).resolves.toEqual([]);
  });

  it("%와 _를 전체 패턴이 아니라 문자 그대로 검색한다", async () => {
    await db.query(
      "insert into public.memories " +
        "(user_id, raw_text, source_type, memory_type) " +
        "values ($1,'진행률 100% 기록','manual','moment'), " +
        "($1,'밑줄 없는 기록','manual','moment'), " +
        "($1,'이름_표시 기록','manual','moment')",
      [alice],
    );
    const repo = createMemoryRepository(await clientFor("alice-mem@example.com"));

    const percent = await repo.search(alice, "%");
    const underscore = await repo.search(alice, "_");

    expect(percent.map((item) => item.rawText)).toEqual(["진행률 100% 기록"]);
    expect(underscore.map((item) => item.rawText)).toEqual(["이름_표시 기록"]);
  });
});
