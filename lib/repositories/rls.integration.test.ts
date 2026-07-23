import { describe, it, expect, beforeAll, afterAll } from "vitest";
import { createClient, type SupabaseClient } from "@supabase/supabase-js";
import { adminClient, SUPABASE_URL, ANON_KEY } from "./testSupport";

let admin: SupabaseClient;
let alice: string;
let bob: string;
let aliceMemory: string;
let aliceDifference: string;
let aliceDiary: string;

const ALICE_EMAIL = "alice@example.com";
const BOB_EMAIL = "bob@example.com";

/**
 * 해당 이메일의 사용자로 로그인한 클라이언트를 만든다. 실제 RLS를 통과한다.
 * generateLink가 이메일로 사용자를 찾아 검증 토큰을 내주고, 그 토큰으로
 * 세션을 연다.
 */
async function clientFor(email: string): Promise<SupabaseClient> {
  const { data, error } = await admin.auth.admin.generateLink({
    type: "magiclink",
    email,
  });
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

  const { data: a } = await admin.auth.admin.createUser({
    email: ALICE_EMAIL,
    email_confirm: true,
  });
  const { data: b } = await admin.auth.admin.createUser({
    email: BOB_EMAIL,
    email_confirm: true,
  });
  alice = a.user!.id;
  bob = b.user!.id;

  const { data: mem } = await admin
    .from("memories")
    .insert({ user_id: alice, source_type: "manual", memory_type: "moment" })
    .select("id")
    .single();
  aliceMemory = mem!.id;

  const { data: diff } = await admin
    .from("differences")
    .insert({
      user_id: alice,
      date: "2026-03-01",
      dimension: "퇴근시간",
      detection_method: "zscore",
      category: "오늘의다른점",
    })
    .select("id")
    .single();
  aliceDifference = diff!.id;

  const { data: diary } = await admin
    .from("diaries")
    .insert({ user_id: alice, date: "2026-03-01" })
    .select("id")
    .single();
  aliceDiary = diary!.id;

  await admin.from("difference_evidence").insert({
    difference_id: aliceDifference,
    memory_id: aliceMemory,
  });
  await admin.from("diary_sources").insert({
    diary_id: aliceDiary,
    memory_id: aliceMemory,
  });
});

afterAll(async () => {
  await admin.auth.admin.deleteUser(alice);
  await admin.auth.admin.deleteUser(bob);
});

describe("교차 사용자 격리 — 소유자 직접", () => {
  it("Bob은 Alice의 메모를 볼 수 없다", async () => {
    const bobClient = await clientFor(BOB_EMAIL);
    const { data } = await bobClient.from("memories").select("id");
    expect(data).toEqual([]);
  });

  it("Bob은 Alice의 일기를 볼 수 없다", async () => {
    const bobClient = await clientFor(BOB_EMAIL);
    const { data } = await bobClient.from("diaries").select("id");
    expect(data).toEqual([]);
  });

  it("Alice는 자기 메모를 볼 수 있다", async () => {
    const aliceClient = await clientFor(ALICE_EMAIL);
    const { data } = await aliceClient.from("memories").select("id");
    expect(data?.map((r) => r.id)).toEqual([aliceMemory]);
  });

  it("Bob은 Alice 소유로 메모를 만들 수 없다", async () => {
    const bobClient = await clientFor(BOB_EMAIL);
    const { error } = await bobClient
      .from("memories")
      .insert({ user_id: alice, source_type: "manual", memory_type: "moment" });
    expect(error).not.toBeNull();
  });
});

describe("교차 사용자 격리 — 부모 경유", () => {
  it("Bob은 Alice의 근거 링크를 볼 수 없다", async () => {
    const bobClient = await clientFor(BOB_EMAIL);
    const { data } = await bobClient.from("difference_evidence").select("difference_id");
    expect(data).toEqual([]);
  });

  it("Bob은 Alice의 일기 출처를 볼 수 없다", async () => {
    const bobClient = await clientFor(BOB_EMAIL);
    const { data } = await bobClient.from("diary_sources").select("diary_id");
    expect(data).toEqual([]);
  });

  it("Alice는 자기 근거 링크를 볼 수 있다", async () => {
    const aliceClient = await clientFor(ALICE_EMAIL);
    const { data } = await aliceClient.from("difference_evidence").select("difference_id");
    expect(data?.length).toBe(1);
  });
});

describe("deletions 쓰기 차단", () => {
  it("사용자는 ledger에 행을 만들 수 없다", async () => {
    const aliceClient = await clientFor(ALICE_EMAIL);
    const { error } = await aliceClient
      .from("deletions")
      .insert({ user_id: alice, trigger: "memory", target_type: "memory" });
    expect(error).not.toBeNull();
  });

  it("사용자는 자기 ledger를 조회할 수는 있다", async () => {
    await admin
      .from("deletions")
      .insert({ user_id: alice, trigger: "memory", target_type: "memory" });

    const aliceClient = await clientFor(ALICE_EMAIL);
    const { data, error } = await aliceClient.from("deletions").select("id");
    expect(error).toBeNull();
    expect(data?.length).toBe(1);
  });
});
