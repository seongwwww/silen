import { describe, it, expect, beforeAll, afterAll } from "vitest";
import { Client } from "pg";
import { createClient, type SupabaseClient } from "@supabase/supabase-js";
import { adminClient, SUPABASE_URL, ANON_KEY } from "./testSupport";
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
  await admin.auth.admin.deleteUser(alice);
  await admin.auth.admin.deleteUser(bob);
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
