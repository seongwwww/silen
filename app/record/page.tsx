import { createDiaryRepository } from "@/lib/repositories/diaryRepository";
import { createServerSupabase } from "@/lib/repositories/supabase";
import { RecordScreen } from "./_components/RecordScreen";

export default async function RecordPage({
  searchParams,
}: {
  searchParams: Promise<{ section?: string }>;
}) {
  const { section } = await searchParams;
  let question: string | null = null;

  if (section) {
    const supabase = await createServerSupabase();
    const {
      data: { user },
    } = await supabase.auth.getUser();
    if (user) {
      question = await createDiaryRepository(supabase).findQuestionById(section);
    }
  }

  return <RecordScreen question={question} />;
}
