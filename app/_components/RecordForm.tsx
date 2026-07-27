"use client";

import { useEffect, useRef, useState } from "react";
import { ArrowUp } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import type { EmotionChoice } from "@/lib/services/memory";
import { EmotionChips } from "./EmotionChips";

const MAX_HEIGHT_PX = 160;

/** 기록 입력. 파이프라인의 입구다 — 열자마자 한 줄 쓰고 보내는 것이 전부여야 한다.
 * POST /api/memories는 멱등이 아니라 이중 전송이 중복 메모를 만든다(가드 필수).
 * 실패해도 사용자가 쓴 글은 절대 비우지 않는다. */
export function RecordForm({ question }: { question?: string | null }) {
  const [text, setText] = useState("");
  const [emotion, setEmotion] = useState<EmotionChoice | undefined>(undefined);
  const [saving, setSaving] = useState(false);
  const inFlight = useRef(false);
  const areaRef = useRef<HTMLTextAreaElement>(null);

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
      toast("기록했어요");
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
        <p className="rounded-lg bg-muted px-3 py-2 text-[15px] text-muted-foreground">
          {question}
        </p>
      )}
      <div className="flex items-start gap-2">
        <label htmlFor="record-text" className="sr-only">
          오늘의 기록
        </label>
        <Textarea
          id="record-text"
          ref={areaRef}
          rows={1}
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
          className="min-h-11 flex-1 resize-none"
        />
        <Button
          type="button"
          aria-label="기록하기"
          disabled={!canSend}
          onClick={() => void submit()}
          className="min-h-11 min-w-11"
        >
          <ArrowUp className="size-4" aria-hidden />
        </Button>
      </div>
      <EmotionChips
        value={emotion}
        onChange={setEmotion}
        disabled={saving}
      />
      <p className="text-[12px] text-muted-foreground">
        기분은 안 골라도 괜찮아요
      </p>
    </div>
  );
}
