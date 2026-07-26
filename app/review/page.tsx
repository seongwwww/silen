import { createServerSupabase } from "@/lib/repositories/supabase";
import { createDifferenceRepository } from "@/lib/repositories/differenceRepository";
import { EmptyState } from "@/components/common/StateView";
import { ReviewList } from "./_components/ReviewList";

export default async function ReviewPage() {
  const supabase = await createServerSupabase();
  const { data: { user } } = await supabase.auth.getUser();
  const items = user ? await createDifferenceRepository(supabase).listCandidatesForReview() : [];
  return (
    <main className="mx-auto max-w-md p-4">
      <h1 className="mb-4 text-lg font-medium">오늘의 다른 점</h1>
      {items.length === 0 ? <EmptyState /> : <ReviewList items={items} />}
    </main>
  );
}
