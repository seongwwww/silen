import { RecordForm } from "./_components/RecordForm";
import { createServerSupabase } from "@/lib/repositories/supabase";
import { createDiaryRepository } from "@/lib/repositories/diaryRepository";

export default async function Home({
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

  return (
    <main className="mx-auto flex min-h-svh max-w-md flex-col justify-center p-4">
      <h1 className="mb-3 text-lg font-medium">오늘, 실은</h1>
      <RecordForm question={question} />
    </main>
  );
}
