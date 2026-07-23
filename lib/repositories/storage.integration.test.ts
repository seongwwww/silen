import { describe, it, expect, beforeAll, afterAll } from "vitest";
import { createClient, type SupabaseClient } from "@supabase/supabase-js";
import { adminClient, SUPABASE_URL, ANON_KEY } from "./testSupport";

let admin: SupabaseClient;
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

const PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
  "base64",
);

beforeAll(async () => {
  admin = adminClient();
  const { data: a } = await admin.auth.admin.createUser({
    email: "alice-storage@example.com",
    email_confirm: true,
  });
  const { data: b } = await admin.auth.admin.createUser({
    email: "bob-storage@example.com",
    email_confirm: true,
  });
  alice = a.user!.id;
  bob = b.user!.id;
});

afterAll(async () => {
  await admin.auth.admin.deleteUser(alice);
  await admin.auth.admin.deleteUser(bob);
});

describe("Storage RLS", () => {
  it("본인 폴더에는 업로드된다", async () => {
    const client = await clientFor("alice-storage@example.com");
    const { error } = await client.storage
      .from("memories")
      .upload(`${alice}/own.png`, PNG, { contentType: "image/png" });
    expect(error).toBeNull();
  });

  it("남의 폴더에는 업로드되지 않는다", async () => {
    const client = await clientFor("alice-storage@example.com");
    const { error } = await client.storage
      .from("memories")
      .upload(`${bob}/intruder.png`, PNG, { contentType: "image/png" });
    expect(error).not.toBeNull();
  });

  it("남의 폴더 객체는 조회되지 않는다", async () => {
    const aliceClient = await clientFor("alice-storage@example.com");
    await aliceClient.storage.from("memories").upload(`${alice}/secret.png`, PNG, {
      contentType: "image/png",
    });

    const bobClient = await clientFor("bob-storage@example.com");
    const { data, error } = await bobClient.storage.from("memories").download(`${alice}/secret.png`);
    // RLS로 막히면 error가 있거나 data가 비어 있다.
    expect(error ?? data === null).toBeTruthy();
  });
});
