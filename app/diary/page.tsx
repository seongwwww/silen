import { createServerSupabase } from "@/lib/repositories/supabase";
import { createDiaryRepository } from "@/lib/repositories/diaryRepository";
import { EmptyState } from "@/components/common/StateView";
import { DiaryArticle } from "./_components/DiaryView";

export default async function DiaryPage() {
  const supabase = await createServerSupabase();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  const repo = createDiaryRepository(supabase);
  const diary = user ? await repo.findLatest() : null;
  // 일기가 없을 때, 기록조차 없는 날과 '아직 안 만들어진' 상태를 구분한다.
  // 섞으면 사용자가 "내가 기록을 안 했나?"로 오해한다.
  const hasMemory = user && !diary ? await repo.hasAnyMemory() : false;

  return (
    <main className="mx-auto max-w-md p-4">
      <h1 className="mb-4 text-lg font-medium">일기</h1>
      {diary ? (
        <DiaryArticle diary={diary} />
      ) : hasMemory ? (
        <EmptyState message="아직 일기가 만들어지지 않았어요" />
      ) : (
        <EmptyState message="아직 쌓인 기록이 없어요" />
      )}
    </main>
  );
}
