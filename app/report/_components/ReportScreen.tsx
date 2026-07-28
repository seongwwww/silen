type Slot = "가장많이한것" | "처음한것" | "감정순간";

type Report = {
  id: string;
  weekStart: string;
  weekEnd: string;
  days: {
    date: string;
    count: number;
    isSurprising: boolean;
  }[];
  highlights: Record<
    Slot,
    {
      headline: string;
      detail: string;
    } | null
  >;
};

const SLOT_LABELS: { slot: Slot; label: string }[] = [
  { slot: "가장많이한것", label: "가장 많이 기록한 것" },
  { slot: "처음한것", label: "이번 주 처음 기록한 것" },
  { slot: "감정순간", label: "감정이 크게 달랐던 날" },
];

function dateParts(date: string): { month: number; day: number } {
  const [, month, day] = date.split("-");
  return { month: Number(month), day: Number(day) };
}

function dateLabel(date: string): string {
  const { month, day } = dateParts(date);
  return `${month}월 ${day}일`;
}

function weekdayLabel(date: string): string {
  return new Intl.DateTimeFormat("ko-KR", {
    timeZone: "UTC",
    weekday: "narrow",
  }).format(new Date(`${date}T00:00:00Z`));
}

export function ReportScreen({ report }: { report: Report | null }) {
  return (
    <main className="mx-auto min-h-[calc(100svh-3.5rem)] w-full max-w-md px-5 py-10">
      <header className="pt-4">
        <h1
          aria-label="당신이 몰랐던 이번 주"
          className="text-3xl font-semibold tracking-tight"
        >
          당신이 몰랐던
          <br />
          이번 주
        </h1>
        {report && (
          <p className="mt-2 text-[15px] text-muted-foreground">
            {dateLabel(report.weekStart)} – {dateLabel(report.weekEnd)}
          </p>
        )}
      </header>

      {!report ? (
        <p className="py-24 text-center text-[15px] text-muted-foreground">
          아직 묶을 7일 기록이 없어요
        </p>
      ) : (
        <>
          <section className="mt-8" aria-labelledby="weekly-flow-title">
            <div className="flex items-center justify-between">
              <h2 id="weekly-flow-title" className="text-sm font-medium">
                7일의 메모
              </h2>
              <p className="text-xs text-muted-foreground">막대 높이 = 메모 수</p>
            </div>
            <ul
              aria-label="7일 메모 흐름"
              className="mt-4 grid grid-cols-7 gap-2"
            >
              {report.days.map((day) => {
                const maxCount = Math.max(
                  1,
                  ...report.days.map((item) => item.count),
                );
                const height =
                  day.count === 0
                    ? 8
                    : Math.max(18, Math.round((day.count / maxCount) * 100));
                const ariaLabel = `${dateLabel(day.date)} 메모 ${day.count}개${
                  day.isSurprising ? ", 큰 차이 발견" : ""
                }`;
                return (
                  <li
                    key={day.date}
                    aria-label={ariaLabel}
                    className="flex min-w-0 flex-col items-center"
                  >
                    <span
                      className={[
                        "h-4 text-[9px] font-semibold",
                        day.isSurprising
                          ? "text-primary"
                          : "text-transparent",
                      ].join(" ")}
                      aria-hidden={!day.isSurprising}
                    >
                      {day.isSurprising ? "큰 차이" : "·"}
                    </span>
                    <div
                      aria-hidden="true"
                      className="mt-1 flex h-24 w-full items-end rounded-lg bg-muted/60 p-1"
                    >
                      <span
                        style={{ height: `${height}%` }}
                        className={[
                          "block w-full rounded-md",
                          day.isSurprising ? "bg-primary" : "bg-border",
                        ].join(" ")}
                      />
                    </div>
                    <span className="mt-2 text-xs font-medium">
                      {weekdayLabel(day.date)}
                    </span>
                    <span className="text-[10px] text-muted-foreground">
                      {day.count}
                    </span>
                  </li>
                );
              })}
            </ul>
          </section>

          <section aria-label="이번 주의 세 가지 모습" className="mt-8 space-y-3">
            {SLOT_LABELS.map(({ slot, label }, index) => {
              const highlight = report.highlights[slot];
              return (
                <article
                  key={slot}
                  data-testid="weekly-slot"
                  className={[
                    "rounded-2xl border px-5 py-5",
                    index === 0 ? "bg-accent" : "bg-card",
                  ].join(" ")}
                >
                  <h2 className="text-xs font-medium text-muted-foreground">
                    {label}
                  </h2>
                  {highlight ? (
                    <>
                      <p className="mt-2 text-lg font-semibold">
                        {highlight.headline}
                      </p>
                      <p className="mt-2 text-[15px] leading-7 text-muted-foreground">
                        {highlight.detail}
                      </p>
                    </>
                  ) : (
                    <p className="mt-3 text-[15px] text-muted-foreground">
                      이번 7일 기록에서는 찾지 못했어요.
                    </p>
                  )}
                </article>
              );
            })}
          </section>

          <p className="mt-6 rounded-2xl border bg-card px-5 py-5 text-center text-sm text-muted-foreground">
            이번 주 기록에서 찾은 모습이에요
          </p>
        </>
      )}
    </main>
  );
}
