"use client";

import { Download, X } from "lucide-react";
import { useMemo, useState } from "react";
import { toast } from "sonner";
import {
  buildShareCardItems,
  SHARE_CARD_SLOTS,
  type ShareCardHighlights,
  type ShareCardSelection,
  type ShareCardSlot,
} from "@/lib/services/shareCard";
import {
  downloadShareCard,
  type DownloadShareCard,
} from "@/lib/services/shareCardClient";

function initialSelection(
  highlights: ShareCardHighlights,
): ShareCardSelection {
  return {
    가장많이한것: highlights.가장많이한것 !== null,
    처음한것: highlights.처음한것 !== null,
    감정순간: highlights.감정순간 !== null,
  };
}

export function ShareCardPanel({
  highlights,
  weekStart,
  download = downloadShareCard,
}: {
  highlights: ShareCardHighlights;
  weekStart: string;
  download?: DownloadShareCard;
}) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [selection, setSelection] = useState(() =>
    initialSelection(highlights),
  );
  const items = useMemo(
    () => buildShareCardItems(highlights, selection),
    [highlights, selection],
  );
  if (Object.values(highlights).every((item) => item === null)) return null;

  function toggle(slot: ShareCardSlot) {
    setSelection((current) => ({ ...current, [slot]: !current[slot] }));
  }

  async function savePng() {
    if (busy || items.length === 0) return;
    setBusy(true);
    try {
      await download(items, weekStart);
      toast("PNG를 저장했어요");
    } catch {
      toast.error("PNG를 저장하지 못했어요. 다시 시도해 주세요.");
    } finally {
      setBusy(false);
    }
  }

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="mt-6 inline-flex min-h-11 w-full items-center justify-center rounded-xl bg-foreground px-4 text-sm font-medium text-background"
      >
        공유 카드 만들기
      </button>
    );
  }

  return (
    <section
      aria-label="공유 카드 만들기"
      className="mt-6 rounded-2xl border bg-card p-4"
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">공유 카드</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            남길 항목을 고르고 미리 확인해 보세요
          </p>
        </div>
        <button
          type="button"
          onClick={() => setOpen(false)}
          className="inline-flex size-11 shrink-0 items-center justify-center rounded-lg text-muted-foreground hover:bg-muted"
        >
          <X aria-hidden="true" className="size-5" />
          <span className="sr-only">공유 카드 닫기</span>
        </button>
      </div>

      <fieldset className="mt-5 space-y-2">
        <legend className="text-sm font-medium">카드에 남길 항목</legend>
        {SHARE_CARD_SLOTS.map(({ slot, label }) => {
          const highlight = highlights[slot];
          if (!highlight) return null;
          return (
            <label
              key={slot}
              className="flex min-h-11 cursor-pointer items-center gap-3 rounded-xl border px-3 py-2 text-sm"
            >
              <input
                type="checkbox"
                checked={selection[slot]}
                onChange={() => toggle(slot)}
                className="size-5 accent-foreground"
              />
              <span>
                {label} · {highlight.headline}
              </span>
            </label>
          );
        })}
      </fieldset>

      <div
        role="region"
        aria-label="공유 카드 미리보기"
        className="mt-5 flex aspect-square w-full flex-col overflow-hidden rounded-2xl bg-[#f7f3ea] p-[7%] text-[#20211d] shadow-sm ring-1 ring-[#ded7cb]"
      >
        <p className="text-[clamp(1.2rem,6vw,1.75rem)] font-bold tracking-tight">
          이번 주의 나
        </p>
        <p className="mt-0.5 text-[10px] text-[#6c6b65]">
          기록에서 찾은 세 가지 모습
        </p>
        {items.length === 0 ? (
          <p className="mt-16 text-center text-sm text-[#6c6b65]">
            남길 항목을 골라 주세요
          </p>
        ) : (
          <div className="mt-[7%] flex-1 space-y-2">
            {items.map((item) => (
              <div
                key={item.slot}
                className="grid grid-cols-[4.25rem_minmax(0,1fr)] gap-2 border-b border-[#ded7cb] pb-2"
              >
                <p className="text-[10px] font-semibold text-[#9a6239]">
                  {item.label}
                </p>
                <div className="min-w-0">
                  <p className="truncate text-xs font-bold">{item.headline}</p>
                  <p className="mt-0.5 line-clamp-1 text-[9px] leading-3 text-[#6c6b65]">
                    {item.detail}
                  </p>
                </div>
              </div>
            ))}
          </div>
        )}
        <p className="mt-auto pt-2 text-xs font-bold">실은</p>
      </div>

      <button
        type="button"
        disabled={busy || items.length === 0}
        onClick={() => void savePng()}
        className="mt-4 inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-xl bg-foreground px-4 text-sm font-medium text-background disabled:opacity-40"
      >
        <Download aria-hidden="true" className="size-4" />
        {busy ? "저장하는 중" : "PNG로 저장"}
      </button>
    </section>
  );
}
