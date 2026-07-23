import { NextResponse, type NextRequest } from "next/server";
import { createMiddlewareSupabase } from "@/lib/repositories/supabase";

export async function middleware(request: NextRequest) {
  const response = NextResponse.next({ request });
  const supabase = createMiddlewareSupabase(request, response);

  // 기존 세션 토큰 갱신만 한다. 세션이 없어도 만들지 않는다.
  // 미들웨어는 모든 요청에 걸리므로, 여기서 익명 세션을 만들면
  // 크롤러·프리페치가 auth.users를 유령 계정으로 채운다.
  await supabase.auth.getUser();

  return response;
}

export const config = {
  matcher: [
    // 정적 자산과 이미지 최적화 요청은 건드리지 않는다.
    "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)",
  ],
};
