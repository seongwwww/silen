import { createMemoryRepository } from "@/lib/repositories/memoryRepository";
import { createServerSupabase } from "@/lib/repositories/supabase";
import { createUserRepository } from "@/lib/repositories/userRepository";
import { searchRecall } from "@/lib/services/recall";
import { RecallScreen } from "./_components/RecallScreen";

export default async function RecallPage({
  searchParams,
}: {
  searchParams: Promise<{ q?: string }>;
}) {
  const { q = "" } = await searchParams;
  const supabase = await createServerSupabase();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  const results = user
    ? await searchRecall(createMemoryRepository(supabase), user.id, q)
    : [];
  const timeZone = user
    ? await createUserRepository(supabase).findTimeZone()
    : "Asia/Seoul";

  return <RecallScreen query={q} results={results} timeZone={timeZone} />;
}
