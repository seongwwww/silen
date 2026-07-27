import type { DiaryView } from "@/lib/services/diary";
import { EmptyState } from "@/components/common/StateView";
import { DiaryArticle } from "./DiaryView";
import { DiaryNav } from "./DiaryNav";

/** /diary와 /diary/[date]가 공유하는 화면. 리다이렉트 대신 이 컴포넌트를
 * 공유해 표시·상태 분기 로직이 두 곳으로 갈라지지 않게 한다. */
export function DiaryScreen({
  diary,
  hasMemory,
  neighbors,
}: {
  diary: DiaryView | null;
  hasMemory: boolean;
  neighbors: { prev: string | null; next: string | null };
}) {
  return (
    <main className="mx-auto max-w-md p-4">
      <h1 className="mb-4 text-lg font-medium">일기</h1>
      {diary ? (
        <>
          <DiaryArticle diary={diary} />
          <DiaryNav prev={neighbors.prev} next={neighbors.next} />
        </>
      ) : hasMemory ? (
        // 일기가 없을 때, 기록조차 없는 경우와 '아직 안 만들어진' 경우를 구분한다.
        // 섞으면 사용자가 "내가 기록을 안 했나?"로 오해한다.
        <EmptyState message="아직 일기가 만들어지지 않았어요" />
      ) : (
        <EmptyState message="아직 쌓인 기록이 없어요" />
      )}
    </main>
  );
}
