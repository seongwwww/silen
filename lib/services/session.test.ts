import { describe, it, expect, vi } from "vitest";
import { ensureSession, linkAccount, type AuthPort } from "./session";

function stubAuth(overrides: Partial<AuthPort> = {}): AuthPort {
  return {
    getUser: vi.fn().mockResolvedValue(null),
    signInAnonymously: vi.fn().mockResolvedValue({ id: "anon-1", isAnonymous: true }),
    updateEmail: vi.fn().mockResolvedValue(undefined),
    signInWithOtp: vi.fn().mockResolvedValue(undefined),
    ...overrides,
  };
}

describe("ensureSession", () => {
  it("세션이 없으면 익명 세션을 만든다", async () => {
    const auth = stubAuth();

    const result = await ensureSession(auth);

    expect(auth.signInAnonymously).toHaveBeenCalledOnce();
    expect(result).toEqual({ userId: "anon-1", isAnonymous: true, created: true });
  });

  it("세션이 있으면 새로 만들지 않는다", async () => {
    const auth = stubAuth({
      getUser: vi.fn().mockResolvedValue({ id: "existing", isAnonymous: false }),
    });

    const result = await ensureSession(auth);

    expect(auth.signInAnonymously).not.toHaveBeenCalled();
    expect(result).toEqual({ userId: "existing", isAnonymous: false, created: false });
  });
});

describe("linkAccount", () => {
  it("익명 사용자에게 이메일을 붙인다", async () => {
    const auth = stubAuth({
      getUser: vi.fn().mockResolvedValue({ id: "anon-1", isAnonymous: true }),
    });

    const result = await linkAccount(auth, { kind: "email", address: "me@example.com" });

    expect(auth.updateEmail).toHaveBeenCalledWith("me@example.com");
    expect(result).toEqual({ status: "confirmation_sent" });
  });

  it("이미 영구 계정이면 다시 연결하지 않는다", async () => {
    const auth = stubAuth({
      getUser: vi.fn().mockResolvedValue({ id: "user-1", isAnonymous: false }),
    });

    const result = await linkAccount(auth, { kind: "email", address: "me@example.com" });

    expect(auth.updateEmail).not.toHaveBeenCalled();
    expect(result).toEqual({ status: "already_linked" });
  });

  it("세션이 없으면 로그인으로 처리한다", async () => {
    const auth = stubAuth();

    const result = await linkAccount(auth, { kind: "email", address: "me@example.com" });

    expect(auth.signInWithOtp).toHaveBeenCalledWith("me@example.com");
    expect(auth.updateEmail).not.toHaveBeenCalled();
    expect(result).toEqual({ status: "confirmation_sent" });
  });
});
