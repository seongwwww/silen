import { afterEach, describe, expect, it } from "vitest";
import { createUserRepository } from "./userRepository";
import { anonClient, cleanupTestUser } from "./testSupport";

const createdUsers: string[] = [];

afterEach(async () => {
  for (const userId of createdUsers.splice(0)) {
    await cleanupTestUser(userId);
  }
});

describe("사용자 일기 시각 저장", () => {
  it("RLS를 지키며 본인의 diary_hour만 바꾼다", async () => {
    const client = anonClient();
    const { data, error } = await client.auth.signInAnonymously();
    expect(error).toBeNull();
    createdUsers.push(data.user!.id);

    const repository = createUserRepository(client);
    expect(await repository.updateDiaryHour(20)).toBe(true);
    expect(await repository.findDiaryHour()).toBe(20);
  });
});
