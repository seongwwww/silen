import Link from "next/link";
import type { DiffStatus } from "@/lib/services/difference";
import type { TodayView } from "@/lib/services/today";
import { ManualDiaryButton } from "./ManualDiaryButton";
import { TodayDifferenceList } from "./TodayDifferenceList";

/** 오늘 화면. 사용자 동작(일기 요청·차이 판단)은 주입받는다 — 화면이
 * 자신의 사용처를 분기하지 않게 한다(frontend.md: 모드 플래그 금지). */
export function TodayScreen({
  view,
  requestDiary,
  decideDifference,
}: {
  view: TodayView;
  requestDiary?: () => Promise<void>;
  decideDifference?: (id: string, status: DiffStatus) => Promise<boolean>;
}) {
  return (
    <main className="mx-auto w-full max-w-md px-5 py-8">
      <header className="mb-8">
        <h1 className="text-3xl font-semibold tracking-tight">오늘</h1>
        <p className="mt-1 text-[15px] text-muted-foreground">
          {view.dateLabel}
        </p>
      </header>

      {view.wrap.state !== "none" && (
        <section
          aria-labelledby="daily-wrap-title"
          className="mb-8 rounded-3xl border bg-accent px-5 py-5"
        >
          {view.wrap.state === "arrived" && (
            <p className="mb-2 text-xs font-semibold tracking-[0.16em] text-muted-foreground">
              {view.wrap.label}
            </p>
          )}
          <h2 id="daily-wrap-title" className="text-xl font-semibold">
            {view.wrap.title}
          </h2>
          <p className="mt-2 text-[15px] leading-relaxed text-muted-foreground">
            {view.wrap.body}
          </p>
          <div className="mt-4">
            {view.wrap.state === "arrived" && (
              <Link
                href={`/diary/${view.dateIso}`}
                className="inline-flex min-h-11 items-center font-semibold underline underline-offset-4"
              >
                열어보기
              </Link>
            )}
            {view.wrap.state === "discovery" && (
              <a
                href="#today-difference-title"
                className="inline-flex min-h-11 items-center font-semibold underline underline-offset-4"
              >
                왜 이렇게 봤는지 보기
              </a>
            )}
            {(view.wrap.state === "available" ||
              view.wrap.state === "closing" ||
              view.wrap.state === "failed") && (
              <ManualDiaryButton requestDiary={requestDiary} />
            )}
          </div>
        </section>
      )}

      {view.isLearning && (
        <section aria-labelledby="today-difference-title" className="mb-8">
          <h2
            id="today-difference-title"
            className="mb-3 text-sm font-medium text-muted-foreground"
          >
            오늘의 다른 점
          </h2>
          <p className="rounded-2xl border bg-card px-4 py-5 text-[15px] text-muted-foreground">
            아직 평소를 익히는 중이에요
          </p>
        </section>
      )}
      {!view.isLearning && view.differences.length > 0 && (
        <TodayDifferenceList
          items={view.differences}
          decideDifference={decideDifference}
        />
      )}

      <section aria-labelledby="today-memory-title" className="mb-6">
        <h2 id="today-memory-title" className="mb-3 text-lg font-semibold">
          오늘의 메모 · {view.memories.count}개
        </h2>
        <div className="rounded-2xl border bg-card px-4 py-4">
          {view.memories.count === 0 ? (
            <p className="text-[15px] text-muted-foreground">
              오늘은 아직 조용하네요
            </p>
          ) : (
            <ul className="divide-y">
              {view.memories.previews.map((item, index) => (
                <li key={`${item}-${index}`} className="py-2 first:pt-0 last:pb-0">
                  <span className="mr-2 text-muted-foreground" aria-hidden="true">
                    ·
                  </span>
                  {item}
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>

      <section aria-labelledby="today-diary-title" className="mb-8">
        <h2 id="today-diary-title" className="mb-3 text-lg font-semibold">
          오늘의 일기
        </h2>
        <div className="rounded-2xl border bg-card px-4 py-4">
          {view.diary.state === "quiet" && (
            <p className="text-[15px] text-muted-foreground">
              오늘은 아직 조용하네요
            </p>
          )}
          {view.diary.state === "processing" && (
            <p className="text-[15px] text-muted-foreground">
              {view.diary.message}
            </p>
          )}
          {view.diary.state === "ready" && (
            <div>
              <p className="leading-relaxed">{view.diary.oneLine}</p>
              <Link
                href={`/diary/${view.dateIso}`}
                className="mt-3 inline-flex min-h-11 items-center font-medium underline underline-offset-4"
              >
                일기 열기
              </Link>
            </div>
          )}
        </div>
      </section>

      <Link
        href="/record"
        className="flex min-h-14 w-full items-center justify-center rounded-2xl bg-foreground px-5 font-semibold text-background"
      >
        + 지금 남기기
      </Link>
    </main>
  );
}
