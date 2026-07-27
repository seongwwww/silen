"use client";

import { Button } from "@/components/ui/button";
import type { EmotionChoice } from "@/lib/services/memory";

const CHOICES: { value: EmotionChoice; label: string }[] = [
  { value: "good", label: "좋았어요" },
  { value: "neutral", label: "그냥" },
  { value: "bad", label: "별로" },
];

/** 감정 칩. 선택은 의무가 아니라 거들 뿐 — 미선택이 기본이고 다시 누르면 해제된다.
 * 선택 상태를 aria-pressed로도 전달한다(색만으로 의미 전달 금지, frontend.md). */
export function EmotionChips({
  value,
  onChange,
  disabled,
}: {
  value: EmotionChoice | undefined;
  onChange: (next: EmotionChoice | undefined) => void;
  disabled?: boolean;
}) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="mr-0.5 text-[13px] text-muted-foreground">기분</span>
      {CHOICES.map((choice) => {
        const selected = value === choice.value;
        return (
          <Button
            key={choice.value}
            type="button"
            variant="outline"
            size="sm"
            aria-pressed={selected}
            disabled={disabled}
            onClick={() => onChange(selected ? undefined : choice.value)}
            className={`min-h-9 rounded-full px-3 text-[13px] ${
              selected
                ? "border-foreground font-medium"
                : "text-muted-foreground"
            }`}
          >
            {choice.label}
          </Button>
        );
      })}
    </div>
  );
}
