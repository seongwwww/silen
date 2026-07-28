import { NextResponse } from "next/server";
import { createServerSupabase } from "@/lib/repositories/supabase";
import { exportUserDataForSession } from "@/lib/services/dataExportServer";

const NO_STORE_HEADERS = {
  "Cache-Control": "no-store",
};

export async function GET() {
  const supabase = await createServerSupabase();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) {
    return NextResponse.json(
      {
        error: {
          code: "unauthorized",
          message: "세션이 필요합니다",
        },
      },
      { status: 401, headers: NO_STORE_HEADERS },
    );
  }

  try {
    const document = await exportUserDataForSession(supabase, user.id);
    const date = document.exportedAt.slice(0, 10);
    return NextResponse.json(document, {
      headers: {
        ...NO_STORE_HEADERS,
        "Content-Disposition": `attachment; filename="silen-records-${date}.json"`,
        "X-Content-Type-Options": "nosniff",
      },
    });
  } catch {
    // 사용자 본문이나 DB 오류 객체를 로그·응답에 남기지 않는다.
    return NextResponse.json(
      {
        error: {
          code: "server_error",
          message: "내보내기에 실패했습니다",
        },
      },
      { status: 500, headers: NO_STORE_HEADERS },
    );
  }
}
