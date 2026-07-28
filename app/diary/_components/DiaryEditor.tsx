"use client";
import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import type { DiaryStatus } from "@/lib/services/diary";

/** 초안을 고치거나 바로 확정한다(기획서 §6). 안 건드리면 draft 그대로다.
 * 편집은 edited_text에만 쓰이고 AI 초안은 남는다. */
export function DiaryEditor({
  id,
  body,
  status,
}: {
  id: string;
  body: string;
  status: DiaryStatus;
}) {
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(body);
  const [saving, setSaving] = useState(false);

  async function send(payload: {
    editedText?: string;
    status: DiaryStatus;
  }) {
    setSaving(true);
    try {
      const res = await fetch(`/api/diaries/${id}`, {
        method: "PATCH",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error("failed");
      setEditing(false);
      toast("저장했어요");
    } catch {
      toast.error("저장하지 못했어요. 다시 시도해 주세요.");
    } finally {
      setSaving(false);
    }
  }

  if (editing) {
    return (
      <div className="mt-3 flex flex-col gap-2">
        <Textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          className="min-h-11"
          aria-label="일기 본문"
        />
        <div className="flex gap-2">
          <Button
            variant="outline"
            className="min-h-11 flex-1"
            disabled={saving}
            onClick={() => setEditing(false)}
          >
            취소
          </Button>
          <Button
            className="min-h-11 flex-1"
            disabled={saving}
            onClick={() =>
              void send({ editedText: text, status: "edited" })
            }
          >
            저장
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="mt-3 flex gap-2">
      <Button
        variant="outline"
        className="min-h-11 flex-1"
        onClick={() => setEditing(true)}
      >
        {status === "confirmed" ? "다시 고치기" : "고치기"}
      </Button>
      {status !== "confirmed" && (
        <Button
          className="min-h-11 flex-1"
          disabled={saving}
          onClick={() => void send({ status: "confirmed" })}
        >
          확정
        </Button>
      )}
    </div>
  );
}
