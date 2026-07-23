import { createClient, type SupabaseClient } from "@supabase/supabase-js";

// Supabase 로컬 스택의 공개 기본값. 루프백 전용이며 비밀이 아니다.
// 원격을 대상으로 돌릴 때는 환경변수로 덮어쓴다.
export const SUPABASE_URL = process.env.SUPABASE_URL ?? "http://127.0.0.1:54321";
export const MAILPIT_URL = process.env.MAILPIT_URL ?? "http://127.0.0.1:54324";
export const SERVICE_ROLE_KEY =
  process.env.SUPABASE_SERVICE_ROLE_KEY ??
  "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImV4cCI6MTk4MzgxMjk5Nn0.EGIM96RAZx35lJzdJsyH-qQwv8Hdp7fsn3W0YpN81IU";
export const ANON_KEY =
  process.env.SUPABASE_ANON_KEY ??
  "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6ImFub24iLCJleHAiOjE5ODM4MTI5OTZ9.CRXP1A7WOeoJeXxjNni43kdQwgnWNReilDMblYTn_I0";

/** RLS를 우회하는 관리자 클라이언트. 테스트 준비·정리에만 쓴다. */
export function adminClient(): SupabaseClient {
  return createClient(SUPABASE_URL, SERVICE_ROLE_KEY, {
    auth: { autoRefreshToken: false, persistSession: false },
  });
}

/** 실제 사용자와 같은 권한의 클라이언트. 세션마다 새로 만든다. */
export function anonClient(): SupabaseClient {
  return createClient(SUPABASE_URL, ANON_KEY, {
    auth: { autoRefreshToken: false, persistSession: false },
  });
}

type MailpitSummary = { ID: string; To: { Address: string }[] };
type MailpitMessage = { Text: string; HTML: string };

/** Mailpit에서 해당 주소로 온 가장 최근 메일의 본문을 가져온다. */
export async function latestMessageTo(address: string): Promise<string> {
  const list = await fetch(`${MAILPIT_URL}/api/v1/messages?limit=50`);
  if (!list.ok) throw new Error(`Mailpit 목록 조회 실패: ${list.status}`);
  const { messages } = (await list.json()) as { messages: MailpitSummary[] };

  const found = messages.find((m) =>
    m.To.some((to) => to.Address.toLowerCase() === address.toLowerCase()),
  );
  if (!found) throw new Error(`${address} 로 온 메일이 없다`);

  const detail = await fetch(`${MAILPIT_URL}/api/v1/message/${found.ID}`);
  if (!detail.ok) throw new Error(`Mailpit 본문 조회 실패: ${detail.status}`);
  const body = (await detail.json()) as MailpitMessage;
  return `${body.Text}\n${body.HTML}`;
}

/**
 * 메일 본문에서 확인 토큰 해시를 뽑는다.
 *
 * Supabase 기본 템플릿은 {{ .ConfirmationURL }}만 쓰므로 본문에 6자리
 * OTP가 없다. 대신 확인 링크에 token=<hash>가 실려 있고, 이 값을
 * verifyOtp({ token_hash, type })로 그대로 검증할 수 있다.
 */
export function extractTokenHash(body: string): string {
  const match = body.match(/[?&]token=([a-f0-9]+)/i);
  if (!match) throw new Error("본문에서 확인 토큰을 찾지 못했다");
  return match[1];
}

/** Mailpit 사서함을 비운다. 테스트 간 간섭을 막는다. */
export async function clearMailbox(): Promise<void> {
  await fetch(`${MAILPIT_URL}/api/v1/messages`, { method: "DELETE" });
}
