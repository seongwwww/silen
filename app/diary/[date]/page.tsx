import { notFound } from "next/navigation";
import { createServerSupabase } from "@/lib/repositories/supabase";
import { createDiaryRepository } from "@/lib/repositories/diaryRepository";
import { DiaryScreen } from "../_components/DiaryScreen";

const DATE_PATTERN = /^\d{4}-\d{2}-\d{2}$/;

export default async function DiaryDatePage({
  params,
}: {
  params: Promise<{ date: string }>;
}) {
  // Next.js 16에서 동적 라우트 params는 Promise다.
  const { date } = await params;
  if (!DATE_PATTERN.test(date)) notFound();

  const supabase = await createServerSupabase();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  const repo = createDiaryRepository(supabase);
  const diary = user ? await repo.findByDate(date) : null;
  // 기준 일기가 없으면 이전/다음의 기준점도 없다 — 빈 상태 대신 404가 맞다.
  if (!diary) notFound();

  const neighbors = await repo.findNeighborDates(diary.date);
  return (
    <DiaryScreen
      diary={diary}
      hasMemory={false}
      neighbors={neighbors}
    />
  );
}
