"use client";

import { useState } from "react";
import { toast } from "sonner";
import { formatDiaryHour } from "@/lib/services/schedule";

export function DiaryHourPicker({ initial }: { initial: number }) {
  const [hour, setHour] = useState(initial);
  const [saving, setSaving] = useState(false);

  async function changeHour(nextHour: number) {
    const previous = hour;
    setHour(nextHour);
    setSaving(true);
    try {
      const response = await fetch("/api/users/me", {
        method: "PATCH",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ diaryHour: nextHour }),
      });
      if (!response.ok) throw new Error("diary_hour_update_failed");
      toast.success("하루를 묶는 시간을 바꿨어요");
    } catch {
      setHour(previous);
      toast.error("시간을 바꾸지 못했어요");
    } finally {
      setSaving(false);
    }
  }

  return (
    <label className="grid gap-2 text-[15px]">
      <span>몇 시에 하루를 묶어드릴까요</span>
      <select
        value={hour}
        disabled={saving}
        onChange={(event) => void changeHour(Number(event.target.value))}
        className="min-h-11 rounded-xl border bg-card px-3"
      >
        {Array.from({ length: 24 }, (_, value) => (
          <option key={value} value={value}>
            {formatDiaryHour(value)}
          </option>
        ))}
      </select>
    </label>
  );
}
