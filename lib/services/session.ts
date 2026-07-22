/**
 * 세션 규칙. 프레임워크·HTTP·Supabase 타입을 모른다(backend.md).
 * 저장소 계층이 AuthPort를 구현해 주입한다.
 */

export type SessionUser = { id: string; isAnonymous: boolean };

export interface AuthPort {
  getUser(): Promise<SessionUser | null>;
  signInAnonymously(): Promise<SessionUser>;
  updateEmail(address: string): Promise<void>;
  signInWithOtp(address: string): Promise<void>;
}

export type SessionResult = {
  userId: string;
  isAnonymous: boolean;
  /** 이 호출이 세션을 새로 만들었는지 */
  created: boolean;
};

/** 이메일 외 수단은 여기에 분기를 추가한다(예: { kind: 'oauth', provider: 'kakao' }). */
export type LinkMethod = { kind: "email"; address: string };

export type LinkResult = { status: "confirmation_sent" | "already_linked" };

/**
 * 세션을 보장한다.
 *
 * 기록을 남기려는 시점에만 호출한다. 미들웨어처럼 모든 요청에 걸리는
 * 곳에서 부르면 크롤러가 auth.users를 유령 계정으로 채운다.
 */
export async function ensureSession(auth: AuthPort): Promise<SessionResult> {
  const existing = await auth.getUser();
  if (existing) {
    return { userId: existing.id, isAnonymous: existing.isAnonymous, created: false };
  }

  const created = await auth.signInAnonymously();
  return { userId: created.id, isAnonymous: created.isAnonymous, created: true };
}

/**
 * 계정을 연결한다. 수단이 무엇이든 "identity를 연결한다"는 같은 동작이므로
 * 여기 한 곳으로 모은다. 호출부가 수단별로 갈라지지 않게 한다.
 */
export async function linkAccount(auth: AuthPort, method: LinkMethod): Promise<LinkResult> {
  const user = await auth.getUser();

  if (user && !user.isAnonymous) {
    return { status: "already_linked" };
  }

  if (user) {
    // 익명 사용자에게 이메일을 붙인다. 사용자 ID는 그대로다.
    await auth.updateEmail(method.address);
  } else {
    // 세션이 없다 — 새 기기에서의 로그인이다.
    await auth.signInWithOtp(method.address);
  }

  return { status: "confirmation_sent" };
}
