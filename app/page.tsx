import { TodayScreen } from "./_components/TodayScreen";
import { createDiaryRepository } from "@/lib/repositories/diaryRepository";
import { createDifferenceRepository } from "@/lib/repositories/differenceRepository";
import { createMemoryRepository } from "@/lib/repositories/memoryRepository";
import { createServerSupabase } from "@/lib/repositories/supabase";
import { createUserRepository } from "@/lib/repositories/userRepository";
import {
  buildTodayView,
  type TodayDiaryPort,
  type TodayDifferencePort,
  type TodayMemoryPort,
} from "@/lib/services/today";

const emptyMemory: TodayMemoryPort = {
  listBetween: async () => [],
  listActiveCapturedAt: async () => [],
};
const emptyDifference: TodayDifferencePort = {
  listForDate: async () => [],
};
const emptyDiary: TodayDiaryPort = {
  findByDate: async () => null,
  findGenerationRequest: async () => null,
};

export default async function Home() {
  const supabase = await createServerSupabase();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  const userRepository = createUserRepository(supabase);
  const [timeZone, diaryHour] = user
    ? await Promise.all([
        userRepository.findTimeZone(),
        userRepository.findDiaryHour(),
      ])
    : (["Asia/Seoul", 21] as const);
  const view = await buildTodayView({
    now: new Date(),
    timeZone,
    diaryHour,
    memory: user ? createMemoryRepository(supabase) : emptyMemory,
    difference: user
      ? createDifferenceRepository(supabase)
      : emptyDifference,
    diary: user ? createDiaryRepository(supabase) : emptyDiary,
  });

  return <TodayScreen view={view} />;
}
