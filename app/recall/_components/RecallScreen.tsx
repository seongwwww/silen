"use client";

import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import {
  RECALL_QUERY_MAX,
  type RecallAnswer,
  type RecallPollResult,
} from "@/lib/services/recall";
import { localDateFor } from "@/lib/time/day";

type ViewState = "empty" | "processing" | "done" | "error" | "offline";

function dateTag(iso: string, timeZone: string): string {
  const [, month, day] = localDateFor(new Date(iso), timeZone).split("-");
  return `${Number(month)}.${Number(day)}`;
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

export function RecallScreen({
  timeZone = "Asia/Seoul",
  pollIntervalMs = 800,
}: {
  timeZone?: string;
  pollIntervalMs?: number;
}) {
  const [question, setQuestion] = useState("");
  const [submittedQuestion, setSubmittedQuestion] = useState("");
  const [answer, setAnswer] = useState<RecallAnswer | null>(null);
  const [state, setState] = useState<ViewState>("empty");
  const mounted = useRef(true);

  useEffect(
    () => () => {
      mounted.current = false;
    },
    [],
  );

  const ask = useCallback(
    async (rawQuestion: string) => {
      const trimmed = rawQuestion.trim();
      if (!trimmed) return;
      if (!navigator.onLine) {
        setState("offline");
        return;
      }
      setSubmittedQuestion(trimmed);
      setAnswer(null);
      setState("processing");
      const requestId = crypto.randomUUID();
      try {
        const accepted = await fetch("/api/recall", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ requestId, question: trimmed }),
        });
        if (!accepted.ok) throw new Error("recall_request_failed");

        for (;;) {
          const response = await fetch(
            `/api/recall?requestId=${encodeURIComponent(requestId)}`,
            { cache: "no-store" },
          );
          if (!response.ok) throw new Error("recall_poll_failed");
          const result = (await response.json()) as RecallPollResult;
          if (!mounted.current) return;
          if (result.status === "done") {
            setAnswer(result.response);
            setState("done");
            return;
          }
          if (result.status === "error" || result.status === "missing") {
            setState("error");
            return;
          }
          await delay(pollIntervalMs);
        }
      } catch {
        if (mounted.current) {
          setState(navigator.onLine ? "error" : "offline");
        }
      }
    },
    [pollIntervalMs],
  );

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void ask(question);
  }

  return (
    <main className="mx-auto min-h-[calc(100svh-3.5rem)] w-full max-w-md px-5 py-10">
      <header className="pt-4">
        <h1 className="text-3xl font-semibold tracking-tight">그거 뭐였지</h1>
        <p className="mt-2 text-[15px] text-muted-foreground">
          기록에게 물어보세요
        </p>
      </header>

      <section aria-live="polite" className="mt-8 min-h-56">
        {state === "empty" && (
          <p className="py-16 text-center text-[15px] text-muted-foreground">
            찾고 싶은 일을 물어보세요
          </p>
        )}
        {submittedQuestion && state !== "empty" && (
          <p className="ml-auto max-w-[85%] rounded-2xl rounded-br-md bg-foreground px-4 py-3 text-[15px] leading-6 text-background">
            {submittedQuestion}
          </p>
        )}
        {state === "processing" && (
          <div
            role="status"
            className="mt-4 rounded-2xl border bg-card px-5 py-8 text-center text-[15px] text-muted-foreground"
          >
            기록에서 찾고 있어요
          </div>
        )}
        {state === "offline" && (
          <p className="mt-4 rounded-xl border bg-card px-4 py-3 text-center text-sm text-muted-foreground">
            인터넷 연결을 확인해 주세요
          </p>
        )}
        {state === "error" && (
          <div className="mt-4 rounded-2xl border bg-card px-5 py-8 text-center">
            <p className="text-[15px] text-muted-foreground">
              기록을 찾지 못했어요
            </p>
            <button
              type="button"
              onClick={() => void ask(submittedQuestion)}
              className="mt-3 min-h-11 px-3 text-sm font-medium underline"
            >
              다시 시도
            </button>
          </div>
        )}
        {state === "done" && answer && (
          <article className="mt-4 rounded-2xl border bg-card px-4 py-5">
            <p className="text-[15px] leading-7">{answer.answer}</p>
            {answer.evidence.length > 0 && (
              <ul aria-label="근거 기록" className="mt-4 space-y-3">
                {answer.evidence.map((evidence) => (
                  <li
                    key={evidence.memoryId}
                    className="rounded-xl bg-accent/70 px-3.5 py-3"
                  >
                    <time
                      dateTime={evidence.capturedAt}
                      className="text-xs font-medium text-muted-foreground"
                    >
                      {dateTag(evidence.capturedAt, timeZone)}
                    </time>
                    <p className="mt-1.5 text-[15px] leading-6">
                      {evidence.quote}
                    </p>
                  </li>
                ))}
              </ul>
            )}
            {answer.confirmation && (
              <p className="mt-5 text-[15px] font-medium">
                {answer.confirmation}
              </p>
            )}
          </article>
        )}
      </section>

      <form onSubmit={submit} className="mt-6 grid grid-cols-[minmax(0,1fr)_auto] gap-2">
        <label className="sr-only" htmlFor="recall-question">
          기록에게 질문
        </label>
        <input
          id="recall-question"
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          maxLength={RECALL_QUERY_MAX}
          placeholder="예: 카페 언제 갔지"
          className="min-h-11 min-w-0 rounded-xl border bg-card px-4 text-[15px] outline-none focus-visible:ring-2"
        />
        <button
          type="submit"
          disabled={!question.trim() || state === "processing"}
          className="min-h-11 rounded-xl bg-foreground px-4 text-sm font-medium text-background disabled:opacity-40"
        >
          물어보기
        </button>
      </form>
    </main>
  );
}

