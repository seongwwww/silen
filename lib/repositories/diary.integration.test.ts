import { describe, it, expect, beforeAll, afterAll } from "vitest";
import { Client } from "pg";
import { createClient, type SupabaseClient } from "@supabase/supabase-js";
import { adminClient, SUPABASE_URL, ANON_KEY } from "./testSupport";
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
  await client.auth.verifyOtp({
    token_hash: data.properties.hashed_token,
    type: "magiclink",
  });
  return client;
}

/** 메모 1건 + 일기(섹션·출처 포함)를 만든다. 반환: diary id */
async function seedDiary(
  user: string,
  opts: {
    body?: string;
    edited?: string | null;
    status?: string;
    memo?: string;
    locked?: boolean;
  } = {},
): Promise<string> {
  const {
    body = "특별할 것 없는 하루였다.",
    edited = null,
    status = "draft",
    memo = "점심 김밥",
    locked = false,
  } = opts;
  const mem = (
    await db.query(
      "insert into public.memories (user_id, raw_text, source_type, memory_type, is_locked) " +
        "values ($1,$2,'manual','moment',$3) returning id",
      [user, memo, locked],
    )
  ).rows[0].id;
  const diary = (
    await db.query(
      "insert into public.diaries (user_id, date, status, generated_text, edited_text) " +
        "values ($1, current_date, $2, $3, $4) returning id",
      [user, status, body, edited],
    )
  ).rows[0].id;
  await db.query(
    "insert into public.diary_sections (diary_id, section_type, content) " +
      "values ($1,'오늘의한문장',$2), ($1,'본문',$3)",
    [diary, "비슷한 하루.", body],
  );
  await db.query(
    "insert into public.diary_sections (diary_id, section_type, content) " +
      "values ($1,'다른점',$2)",
    [diary, "평소보다 일찍 퇴근"],
  );
  await db.query(
    "insert into public.diary_sources (diary_id, memory_id) values ($1,$2)",
    [diary, mem],
  );
  return diary;
}

beforeAll(async () => {
  admin = adminClient();
  db = new Client({ connectionString: CONNECTION_STRING });
  await db.connect();
  alice = (
    await admin.auth.admin.createUser({
      email: "diary-alice@example.com",
      email_confirm: true,
    })
  ).data.user!.id;
  bob = (
    await admin.auth.admin.createUser({
      email: "diary-bob@example.com",
      email_confirm: true,
    })
  ).data.user!.id;
});

afterAll(async () => {
  await admin.auth.admin.deleteUser(alice);
  await admin.auth.admin.deleteUser(bob);
  await db.end();
});

describe("diaryRepository", () => {
  it("최신 일기를 섹션·근거와 함께 가져온다", async () => {
    await seedDiary(alice);
    const repo = createDiaryRepository(
      await clientFor("diary-alice@example.com"),
    );
    const view = await repo.findLatest();
    expect(view).not.toBeNull();
    expect(view!.oneLine).toBe("비슷한 하루.");
    expect(view!.body).toBe("특별할 것 없는 하루였다.");
    expect(view!.differences).toContain("평소보다 일찍 퇴근");
    expect(view!.evidence).toContain("점심 김밥");
    expect(view!.isEdited).toBe(false);
  });

  it("편집본이 있으면 그것을 본문으로 쓴다", async () => {
    await db.query("delete from public.diaries where user_id = $1", [bob]);
    await seedDiary(bob, {
      edited: "내가 고친 본문",
      status: "edited",
      memo: "저녁 산책",
    });
    const repo = createDiaryRepository(
      await clientFor("diary-bob@example.com"),
    );
    const view = await repo.findLatest();
    expect(view!.body).toBe("내가 고친 본문");
    expect(view!.isEdited).toBe(true);
  });

  it("잠긴 메모는 근거에서 빠진다", async () => {
    await db.query("delete from public.diaries where user_id = $1", [bob]);
    await db.query("delete from public.memories where user_id = $1", [bob]);
    await seedDiary(bob, { memo: "비밀 기록", locked: true });
    const repo = createDiaryRepository(
      await clientFor("diary-bob@example.com"),
    );
    const view = await repo.findLatest();
    expect(view!.evidence).toEqual([]);
  });

  it("타 사용자 일기는 보이지 않는다", async () => {
    await db.query("delete from public.diaries where user_id = $1", [bob]);
    await db.query("delete from public.memories where user_id = $1", [bob]);
    const repo = createDiaryRepository(
      await clientFor("diary-bob@example.com"),
    );
    expect(await repo.findLatest()).toBeNull();
  });

  it("일기 재료가 될 메모가 있는지 판정한다", async () => {
    await db.query("delete from public.memories where user_id = $1", [bob]);
    const repo = createDiaryRepository(
      await clientFor("diary-bob@example.com"),
    );
    expect(await repo.hasAnyMemory()).toBe(false);
    await db.query(
      "insert into public.memories (user_id, raw_text, source_type, memory_type) " +
        "values ($1,'뭔가 남김','manual','moment')",
      [bob],
    );
    expect(await repo.hasAnyMemory()).toBe(true);
  });
});
