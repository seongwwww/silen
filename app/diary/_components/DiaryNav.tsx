import Link from "next/link";

/** 존재하는 이전/다음 일기로 이동한다(날짜-1이 아니다).
 * 없는 방향은 숨기지 않고 비활성으로 둔다 — 경계임을 알리고 레이아웃도 안 흔들린다.
 * 방향을 화살표만으로 전달하지 않고 텍스트 라벨을 쓴다(frontend.md). */
const ITEM = "min-h-11 flex-1 rounded-lg border px-3 py-2 text-[15px]";

export function DiaryNav({
  prev,
  next,
}: {
  prev: string | null;
  next: string | null;
}) {
  return (
    <nav className="mt-8 flex gap-2">
      {prev ? (
        <Link href={`/diary/${prev}`} className={`${ITEM} text-left`}>
          이전 일기
        </Link>
      ) : (
        <span
          aria-disabled="true"
          className={`${ITEM} text-left text-muted-foreground opacity-50`}
        >
          이전 일기
        </span>
      )}
      {next ? (
        <Link href={`/diary/${next}`} className={`${ITEM} text-right`}>
          다음 일기
        </Link>
      ) : (
        <span
          aria-disabled="true"
          className={`${ITEM} text-right text-muted-foreground opacity-50`}
        >
          다음 일기
        </span>
      )}
    </nav>
  );
}
