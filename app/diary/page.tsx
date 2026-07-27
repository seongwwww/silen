import { createServerSupabase } from "@/lib/repositories/supabase";
import { createDiaryRepository } from "@/lib/repositories/diaryRepository";
import { DiaryScreen } from "./_components/DiaryScreen";

export default async function DiaryPage() {
  const supabase = await createServerSupabase();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  const repo = createDiaryRepository(supabase);
  const diary = user ? await repo.findLatest() : null;
  const hasMemory = user && !diary ? await repo.hasAnyMemory() : false;
  const neighbors = diary
    ? await repo.findNeighborDates(diary.date)
    : { prev: null, next: null };

  return (
    <DiaryScreen
      diary={diary}
      hasMemory={hasMemory}
      neighbors={neighbors}
    />
  );
}
