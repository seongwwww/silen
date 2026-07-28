"use client";

import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import type { EmotionChoice } from "@/lib/services/memory";
import { EmotionChips } from "./EmotionChips";

const MAX_HEIGHT_PX = 160;
const QUESTION_CUES = [
  "같이 떠오르는 장면이 있나요?",
  "미처 남기지 않은 부분이 있나요?",
  "다른 날의 기억도 떠오르나요?",
] as const;

/** 기록 입력. 파이프라인의 입구다 — 열자마자 한 줄 쓰고 보내는 것이 전부여야 한다.
 * POST /api/memories는 멱등이 아니라 이중 전송이 중복 메모를 만든다(가드 필수).
 * 실패해도 사용자가 쓴 글은 절대 비우지 않는다. */
export function RecordForm({
  question,
  onSaved,
}: {
  question?: string | null;
  onSaved?: () => void;
}) {
  const [text, setText] = useState("");
  const [emotion, setEmotion] = useState<EmotionChoice | undefined>(undefined);
  const [saving, setSaving] = useState(false);
  const [cue, setCue] = useState<{ question: string; index: number } | null>(
    null,
  );
  const inFlight = useRef(false);
  const areaRef = useRef<HTMLTextAreaElement>(null);
  const cueIndex = question && cue?.question === question ? cue.index : null;

  useEffect(() => {
    const element = areaRef.current;
    if (!element) return;
    element.style.height = "auto";
    element.style.height = `${Math.min(element.scrollHeight, MAX_HEIGHT_PX)}px`;
  }, [text]);

  const canSend = text.trim().length > 0 && !saving;

  async function submit() {
    if (inFlight.current) return;

    const body = text.trim();
    if (!body) return;

    if (typeof navigator !== "undefined" && navigator.onLine === false) {
      toast.error("지금은 오프라인이에요. 연결되면 다시 시도해 주세요.");
      return;
    }

    inFlight.current = true;
    setSaving(true);

    try {
      const response = await fetch("/api/memories", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ text: body, emotion }),
      });

      if (!response.ok) throw new Error("save failed");

      setText("");
      setEmotion(undefined);
      toast(
        question
          ? "기록했어요. 더 떠오르면 이어 적어도 돼요."
          : "기록했어요",
      );
      onSaved?.();
      areaRef.current?.focus();
    } catch {
      toast.error("기록하지 못했어요. 다시 시도해 주세요.");
    } finally {
      inFlight.current = false;
      setSaving(false);
    }
  }

  return (
    <div className="flex flex-col gap-3">
      {question && (
        <div className="rounded-lg bg-muted px-3 py-3">
          <p className="text-xs text-muted-foreground">
            이 질문에서 이어 쓰는 중
          </p>
          <p className="mt-1 text-[15px]">{question}</p>
          <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
            한 번에 다 적지 않아도 괜찮아요. 같은 질문에서 여러 번 이어 쓸 수
            있어요.
          </p>
        </div>
      )}
      <div>
        <label htmlFor="record-text" className="sr-only">
          오늘의 기록
        </label>
        <Textarea
          id="record-text"
          ref={areaRef}
          rows={4}
          value={text}
          onChange={(event) => setText(event.target.value)}
          onKeyDown={(event) => {
            if (
              event.key === "Enter" &&
              (event.metaKey || event.ctrlKey)
            ) {
              event.preventDefault();
              void submit();
            }
          }}
          placeholder="오늘, 실은…"
          className="min-h-[120px] w-full resize-none text-[15px] leading-relaxed"
        />
      </div>
      <EmotionChips
        value={emotion}
        onChange={setEmotion}
        disabled={saving}
      />
      <p className="text-[12px] text-muted-foreground">
        기분은 안 골라도 괜찮아요
      </p>
      <Button
        type="button"
        disabled={!canSend}
        onClick={() => void submit()}
        className="min-h-14 w-full text-[15px] font-semibold"
      >
        {saving ? "남기는 중이에요" : "남기기"}
      </Button>
      {question && (
        <div className="rounded-lg border border-dashed px-3 py-2">
          <Button
            type="button"
            variant="ghost"
            className="min-h-11 px-2 text-muted-foreground"
            aria-expanded={cueIndex !== null}
            onClick={() => {
              setCue((current) => ({
                question,
                index:
                  current?.question === question
                    ? (current.index + 1) % QUESTION_CUES.length
                    : 0,
              }));
            }}
          >
            {cueIndex === null
              ? "다른 각도로 떠올려보기"
              : "다른 단서 보기"}
          </Button>
          {cueIndex !== null && (
            <p
              className="px-2 pb-2 text-[15px]"
              aria-live="polite"
            >
              {QUESTION_CUES[cueIndex]}
            </p>
          )}
          <p className="px-2 pb-1 text-xs leading-relaxed text-muted-foreground">
            이렇게 남긴 기록도 쌓여, 나중에 작은 차이를 찾는 단서가 돼요.
          </p>
        </div>
      )}
    </div>
  );
}
