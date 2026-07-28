"use client";
import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  TONE_PRESETS,
  type TonePreset,
} from "@/lib/services/diary";

/** 일기 기본 톤. 사실은 그대로 두고 문체만 바뀐다(기획서 §4-9). */
export function TonePicker({ initial }: { initial: TonePreset }) {
  const [preset, setPreset] = useState<TonePreset>(initial);

  async function pick(next: TonePreset) {
    setPreset(next);
    const res = await fetch("/api/users/me", {
      method: "PATCH",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ tonePreset: next }),
    });
    if (!res.ok) {
      setPreset(preset);
      toast.error("바꾸지 못했어요. 다시 시도해 주세요.");
      return;
    }
    toast("톤을 바꿨어요");
  }

  return (
    <div className="flex gap-2">
      {TONE_PRESETS.map((p) => (
        <Button
          key={p}
          variant="outline"
          aria-pressed={preset === p}
          className={`min-h-11 flex-1 ${
            preset === p
              ? "border-[var(--success-text)] font-medium"
              : ""
          }`}
          onClick={() => void pick(p)}
        >
          {p}
        </Button>
      ))}
    </div>
  );
}
