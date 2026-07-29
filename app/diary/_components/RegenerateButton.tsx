"use client";
import { useRef, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import {
  QUICK_TONE_ORDERS,
  TONE_INSTRUCTION_MAX_LENGTH,
  type DiaryStatus,
  type QuickToneOrder,
} from "@/lib/services/diary";

/** 늦은 메모를 반영하려 다시 만든다(기획서 §6 "다시 만들기 1회").
 * 즉시 반영이 아니라 요청을 남기고 다음 생성이 반영한다.
 * 편집본이면 고친 내용이 사라지므로 한 번 더 확인받는다. */
export function RegenerateButton({
  id,
  status,
  initialToneInstruction = null,
  initialRequested = false,
}: {
  id: string;
  status: DiaryStatus;
  initialToneInstruction?: string | null;
  initialRequested?: boolean;
}) {
  const [confirming, setConfirming] = useState(false);
  const [requested, setRequested] = useState(initialRequested);
  const [sending, setSending] = useState(false);
  const [quickOrder, setQuickOrder] = useState<QuickToneOrder | null>(null);
  const [freeOrder, setFreeOrder] = useState("");
  const inFlight = useRef(false);

  const trimmedFreeOrder = freeOrder.trim();
  const toneInstruction = trimmedFreeOrder || quickOrder;
  const selectionLabel = trimmedFreeOrder
    ? "선택: 자유 주문"
    : quickOrder
      ? `선택: ${quickOrder}`
      : "선택: 기본 톤 그대로";

  async function send() {
    if (inFlight.current) return;
    if (typeof navigator !== "undefined" && navigator.onLine === false) {
      toast.error("지금은 오프라인이에요. 연결되면 다시 시도해 주세요.");
      return;
    }

    inFlight.current = true;
    setSending(true);
    try {
      const res = await fetch(`/api/diaries/${id}/regenerate`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ toneInstruction }),
      });
      if (!res.ok) throw new Error("failed");
      setRequested(true);
      setConfirming(false);
    } catch {
      toast.error("다시 만들기를 요청하지 못했어요. 다시 시도해 주세요.");
    } finally {
      inFlight.current = false;
      setSending(false);
    }
  }

  if (requested) {
    return (
      <div
        role="status"
        className="mt-3 rounded-xl border bg-accent px-4 py-3"
      >
        <p className="text-[15px]">다음 일기를 만들 때 반영돼요.</p>
        {initialRequested && initialToneInstruction && (
          <p className="mt-1 text-xs text-muted-foreground">
            주문: {initialToneInstruction}
          </p>
        )}
        {!initialRequested && toneInstruction && (
          <p className="mt-1 text-xs text-muted-foreground">
            주문: {toneInstruction}
          </p>
        )}
      </div>
    );
  }

  return (
    <section className="mt-5" aria-labelledby="tone-order-title">
      <h3 id="tone-order-title" className="text-sm font-medium">
        이번 일기 톤 바꾸기
      </h3>
      <p className="mt-1 text-xs text-muted-foreground">
        기본 톤은 그대로 두고, 다음 한 번에만 반영해요.
      </p>

      <fieldset className="mt-3">
        <legend className="text-xs text-muted-foreground">빠른 주문</legend>
        <div className="mt-2 flex gap-2">
          {QUICK_TONE_ORDERS.map((order) => {
            const selected = quickOrder === order && !trimmedFreeOrder;
            return (
              <Button
                key={order}
                type="button"
                variant="outline"
                aria-pressed={selected}
                disabled={sending}
                className={`min-h-11 flex-1 ${
                  selected
                    ? "border-primary bg-accent font-semibold"
                    : ""
                }`}
                onClick={() => {
                  setQuickOrder((current) =>
                    current === order ? null : order,
                  );
                  setFreeOrder("");
                }}
              >
                {order}
                {selected && (
                  <span className="ml-1 text-xs">선택됨</span>
                )}
              </Button>
            );
          })}
        </div>
      </fieldset>

      <div className="mt-3">
        <label
          htmlFor={`tone-order-${id}`}
          className="text-xs text-muted-foreground"
        >
          자유 주문
        </label>
        <Textarea
          id={`tone-order-${id}`}
          value={freeOrder}
          maxLength={TONE_INSTRUCTION_MAX_LENGTH}
          disabled={sending}
          placeholder="예: 더 짧고 건조하게"
          className="mt-2 min-h-11"
          onChange={(event) => {
            setFreeOrder(event.target.value);
            if (event.target.value.trim()) setQuickOrder(null);
          }}
        />
        <div className="mt-1 flex justify-between gap-2 text-xs text-muted-foreground">
          <p aria-live="polite">{selectionLabel}</p>
          <p>
            {freeOrder.length} / {TONE_INSTRUCTION_MAX_LENGTH}자
          </p>
        </div>
      </div>

      {confirming && (
        <p className="mt-3 text-[15px] text-muted-foreground">
          고친 내용이 사라져요. 그래도 다시 만들까요?
        </p>
      )}
      <Button
        type="button"
        variant="outline"
        className="mt-3 min-h-11 w-full"
        disabled={sending}
        onClick={() => {
          if (status !== "draft" && !confirming) {
            setConfirming(true);
            return;
          }
          void send();
        }}
      >
        {sending ? "요청하는 중" : "다시 만들기"}
      </Button>
    </section>
  );
}
