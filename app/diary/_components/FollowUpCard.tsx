import Link from "next/link";

/** 처음 등장한 것에 대해 한 번 묻는다. 답은 강요하지 않는다 — 탭하면 기록
 * 화면으로 갈 뿐이고, 거기서 평소처럼 메모를 남기면 그게 답이다.
 * URL엔 id만 담는다(질문 텍스트에 사람 이름이 들어갈 수 있다). */
export function FollowUpCard({
  sectionId,
  text,
}: {
  sectionId: string;
  text: string;
}) {
  return (
    <section className="mt-6">
      <p className="mb-2 text-xs text-muted-foreground">덧붙이고 싶다면</p>
      <Link
        href={`/?section=${sectionId}`}
        className="block min-h-11 rounded-lg border px-3 py-2 text-[15px]"
      >
        {text}
      </Link>
      <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
        한 번에 다 적지 않아도 괜찮아요. 같은 질문에서 여러 번 이어 쓸 수
        있어요.
      </p>
    </section>
  );
}
