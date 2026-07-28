import {
  describe,
  it,
  expect,
  beforeAll,
  afterAll,
  beforeEach,
} from "vitest";
import { Client } from "pg";
import { createClient, type SupabaseClient } from "@supabase/supabase-js";
import {
  adminClient,
  cleanupTestUser,
  SUPABASE_URL,
  ANON_KEY,
} from "./testSupport";
import { createDiaryRepository } from "./diaryRepository";

const CONNECTION_STRING =
  process.env.SUPABASE_DB_URL ??
  "postgresql://postgres:postgres@127.0.0.1:54322/postgres";

let admin: SupabaseClient, db: Client, alice: string, bob: string;

async function clientFor(email: string): Promise<SupabaseClient> {
  const { data } = await admin.auth.admin.generateLink({
    type: "magiclink",
    email,
  });
  const client = createClient(SUPABASE_URL, ANON_KEY, {
    auth: { autoRefreshToken: false, persistSession: false },
  });
  if (!data.properties) throw new Error("magiclink 발급 실패");
  await client.auth.verifyOtp({
    token_hash: data.properties.hashed_token,
    type: "magiclink",
  });
  return client;
}

async function seedDiary(
  user: string,
  opts: { body?: string; edited?: string | null; status?: string } = {},
): Promise<string> {
  const {
    body = "AI 초안",
    edited = null,
    status = "draft",
  } = opts;
  return (
    await db.query(
      "insert into public.diaries (user_id, date, status, generated_text, edited_text) " +
        "values ($1, current_date, $2, $3, $4) returning id",
      [user, status, body, edited],
    )
  ).rows[0].id;
}

beforeAll(async () => {
  admin = adminClient();
  db = new Client({ connectionString: CONNECTION_STRING });
  await db.connect();
  alice = (
    await admin.auth.admin.createUser({
      email: "edit-alice@example.com",
      email_confirm: true,
    })
  ).data.user!.id;
  bob = (
    await admin.auth.admin.createUser({
      email: "edit-bob@example.com",
      email_confirm: true,
    })
  ).data.user!.id;
});

beforeEach(async () => {
  await db.query("delete from public.diaries where user_id in ($1, $2)", [
    alice,
    bob,
  ]);
});

afterAll(async () => {
  await cleanupTestUser(alice, db);
  await cleanupTestUser(bob, db);
  await db.end();
});

describe("diaryRepository 편집", () => {
  it("편집 본문과 상태를 저장한다", async () => {
    const diaryId = await seedDiary(alice);
    const repo = createDiaryRepository(
      await clientFor("edit-alice@example.com"),
    );

    expect(
      await repo.updateDraft(
        diaryId,
        "내가 고친 본문",
        "edited",
        "draft",
      ),
    ).toBe(true);
    const view = await repo.findLatest();
    expect(view!.body).toBe("내가 고친 본문");
    expect(view!.status).toBe("edited");
  });

  it("기대 상태가 다르면 실패한다(TOCTOU)", async () => {
    const diaryId = await seedDiary(alice, {
      edited: "이미 고친 본문",
      status: "edited",
    });
    const repo = createDiaryRepository(
      await clientFor("edit-alice@example.com"),
    );

    expect(
      await repo.updateDraft(
        diaryId,
        "다른 본문",
        "confirmed",
        "draft",
      ),
    ).toBe(false);
  });

  it("AI 초안은 덮어쓰지 않는다", async () => {
    const diaryId = await seedDiary(alice, { body: "보존할 AI 초안" });
    const repo = createDiaryRepository(
      await clientFor("edit-alice@example.com"),
    );

    expect(
      await repo.updateDraft(
        diaryId,
        "내가 고친 본문",
        "edited",
        "draft",
      ),
    ).toBe(true);
    const result = await db.query(
      "select generated_text from public.diaries where id = $1",
      [diaryId],
    );
    expect(result.rows[0].generated_text).toBe("보존할 AI 초안");
  });

  it("타 사용자 일기는 바꿀 수 없다", async () => {
    const aliceDiaryId = await seedDiary(alice);
    const repo = createDiaryRepository(
      await clientFor("edit-bob@example.com"),
    );

    expect(
      await repo.updateDraft(
        aliceDiaryId,
        "침입",
        "edited",
        "draft",
      ),
    ).toBe(false);
  });
});
