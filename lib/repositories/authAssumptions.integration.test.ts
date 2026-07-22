import { describe, it, expect, beforeEach } from "vitest";
import { anonClient, latestMessageTo, extractTokenHash, clearMailbox } from "./testSupport";

beforeEach(async () => {
  await clearMailbox();
});

describe("스펙 §9 가정", () => {
  it("익명 로그인이 활성화되어 있다", async () => {
    const client = anonClient();
    const { data, error } = await client.auth.signInAnonymously();

    expect(error).toBeNull();
    expect(data.user?.id).toBeTruthy();
    expect(data.user?.is_anonymous).toBe(true);
  });

  it("이메일 연결 후에도 사용자 ID가 바뀌지 않는다", async () => {
    // 이 가정이 깨지면 데이터 이관 설계가 통째로 필요해진다.
    const client = anonClient();
    const { data: anon } = await client.auth.signInAnonymously();
    const anonymousId = anon.user!.id;

    const address = `link-${anonymousId.slice(0, 8)}@test.local`;
    const { error: updateError } = await client.auth.updateUser({ email: address });
    expect(updateError).toBeNull();

    const body = await latestMessageTo(address);
    const tokenHash = extractTokenHash(body);

    const { data: verified, error: verifyError } = await client.auth.verifyOtp({
      token_hash: tokenHash,
      type: "email_change",
    });

    expect(verifyError).toBeNull();
    expect(verified.user!.id).toBe(anonymousId);
    expect(verified.user!.email).toBe(address);
    expect(verified.user!.is_anonymous).toBe(false);
  });

  // "전환 전 데이터가 전환 후에도 유지된다"는 프로필 트리거가 생긴 뒤에야
  // 검증할 수 있다. memories.user_id가 public.users를 참조하는데 그 행을
  // 만드는 트리거가 아직 없기 때문이다. 해당 테스트는 다음 태스크에 있다.
});
