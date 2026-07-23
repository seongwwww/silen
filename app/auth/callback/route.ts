import { NextResponse, type NextRequest } from "next/server";
import { createServerSupabase } from "@/lib/repositories/supabase";

/**
 * PKCE code를 세션으로 교환한다.
 *
 * 이 라우트는 provider를 모른다. 매직링크도 OAuth도 같은 교환을
 * 거치므로, 소셜을 추가해도 이 파일은 바뀌지 않는다.
 */
export async function GET(request: NextRequest) {
  const { searchParams, origin } = new URL(request.url);
  const code = searchParams.get("code");
  const next = searchParams.get("next") ?? "/";

  if (!code) {
    return NextResponse.redirect(`${origin}/auth/error?reason=missing_code`);
  }

  const supabase = await createServerSupabase();
  const { error } = await supabase.auth.exchangeCodeForSession(code);

  if (error) {
    // 실패를 조용히 삼키지 않는다(frontend.md). 사유는 코드로만 넘기고
    // 본문·이메일 등 식별 정보는 URL에 싣지 않는다.
    return NextResponse.redirect(`${origin}/auth/error?reason=exchange_failed`);
  }

  // 오픈 리다이렉트 방지: 같은 출처의 경로만 허용한다.
  const target = next.startsWith("/") && !next.startsWith("//") ? next : "/";
  return NextResponse.redirect(`${origin}${target}`);
}
