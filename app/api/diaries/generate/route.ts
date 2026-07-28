import { NextResponse } from "next/server";
import { createServerSupabase } from "@/lib/repositories/supabase";
import { createUserRepository } from "@/lib/repositories/userRepository";
import { createDiaryRepository } from "@/lib/repositories/diaryRepository";
import { requestTodayDiary } from "@/lib/services/diaryGeneration";

/** 사용자 로컬 오늘의 일기 생성 작업을 요청한다.
 * 같은 날짜를 여러 번 눌러도 RPC가 한 작업으로 멱등 처리한다. */
export async function POST() {
  const supabase = await createServerSupabase();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    return NextResponse.json(
      { error: { code: "unauthorized", message: "세션이 필요합니다" } },
      { status: 401 },
    );
  }

  try {
    const timeZone = await createUserRepository(supabase).findTimeZone();
    const result = await requestTodayDiary(
      createDiaryRepository(supabase),
      { now: new Date(), timeZone },
    );
    return NextResponse.json(result, { status: 202 });
  } catch {
    // DB 세부 정보나 사용자 식별자는 응답·로그에 남기지 않는다.
    return NextResponse.json(
      {
        error: {
          code: "server_error",
          message: "일기 생성 요청에 실패했습니다",
        },
      },
      { status: 500 },
    );
  }
}
