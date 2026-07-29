export type ShareCardSlot = "가장많이한것" | "처음한것" | "감정순간";

export type ShareCardHighlight = {
  headline: string;
  detail: string;
};

export type ShareCardHighlights = Record<
  ShareCardSlot,
  ShareCardHighlight | null
>;

export type ShareCardSelection = Record<ShareCardSlot, boolean>;

export type ShareCardItem = ShareCardHighlight & {
  slot: ShareCardSlot;
  label: string;
};

export const SHARE_CARD_SLOTS: ReadonlyArray<{
  slot: ShareCardSlot;
  label: string;
}> = [
  { slot: "가장많이한것", label: "가장 많이" },
  { slot: "처음한것", label: "처음" },
  { slot: "감정순간", label: "감정" },
];

/** 주간 리포트의 요약 슬롯만 공유 카드 입력으로 좁힌다. */
export function buildShareCardItems(
  highlights: ShareCardHighlights,
  selection: ShareCardSelection,
): ShareCardItem[] {
  return SHARE_CARD_SLOTS.flatMap(({ slot, label }) => {
    const highlight = highlights[slot];
    return selection[slot] && highlight
      ? [{ slot, label, ...highlight }]
      : [];
  });
}
