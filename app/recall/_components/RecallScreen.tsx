import type { RecallResult } from "@/lib/services/recall";
import { RECALL_QUERY_MAX } from "@/lib/services/recall";
import { localDateFor } from "@/lib/time/day";

function dateTag(iso: string, timeZone: string): string {
  const [, month, day] = localDateFor(new Date(iso), timeZone).split("-");
  return `${Number(month)}.${Number(day)}`;
}

export function RecallScreen({
  query,
  results,
  timeZone = "Asia/Seoul",
}: {
  query: string;
  results: RecallResult[];
  timeZone?: string;
}) {
  const searched = query.trim().length > 0;

  return (
    <main className="mx-auto min-h-[calc(100svh-3.5rem)] w-full max-w-md px-5 py-10">
      <header className="pt-4">
        <h1 className="text-3xl font-semibold tracking-tight">그거 뭐였지</h1>
        <p className="mt-2 text-[15px] text-muted-foreground">
          기록에게 물어보세요
        </p>
      </header>

      <form
        role="search"
        className="mt-8 grid grid-cols-[minmax(0,1fr)_auto] gap-2"
      >
        <label className="sr-only" htmlFor="recall-query">
          기록 검색
        </label>
        <input
          id="recall-query"
          name="q"
          type="search"
          defaultValue={query}
          maxLength={RECALL_QUERY_MAX}
          placeholder="기억나는 단어나 문장"
          className="min-h-11 min-w-0 flex-1 rounded-xl border bg-card px-4 text-[15px] outline-none focus-visible:ring-2"
        />
        <button
          type="submit"
          className="min-h-11 rounded-xl bg-foreground px-5 text-sm font-medium text-background"
        >
          찾기
        </button>
      </form>

      <section aria-live="polite" className="mt-8">
        {!searched ? (
          <p className="py-16 text-center text-[15px] text-muted-foreground">
            찾고 싶은 말을 적어보세요
          </p>
        ) : results.length === 0 ? (
          <p className="py-16 text-center text-[15px] text-muted-foreground">
            그런 기록은 아직 없어요
          </p>
        ) : (
          <ul aria-label="검색 결과" className="space-y-3">
            {results.map((result) => (
              <li
                key={result.id}
                className="rounded-2xl border bg-card px-4 py-4"
              >
                <time
                  dateTime={result.capturedAt}
                  className="inline-flex rounded-full bg-accent px-2.5 py-1 text-xs font-medium"
                >
                  {dateTag(result.capturedAt, timeZone)}
                </time>
                <p className="mt-3 text-[15px] leading-7">{result.excerpt}</p>
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}
