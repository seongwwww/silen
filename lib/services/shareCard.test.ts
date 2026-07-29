import { describe, expect, it } from "vitest";
import {
  buildShareCardItems,
  type ShareCardSelection,
} from "./shareCard";

const highlights = {
  가장많이한것: {
    headline: "김밥",
    detail: "7일 기록에서 4번 언급됐어요.",
  },
  처음한것: {
    headline: "그 카페",
    detail: "이번 7일 기록에 처음 등장했어요.",
  },
  감정순간: {
    headline: "목요일이 달랐어요",
    detail: "최근 기록보다 감정이 크게 달랐어요.",
  },
};

describe("공유 카드 항목", () => {
  it("기본 선택된 세 요약 슬롯만 정해진 순서로 만든다", () => {
    const selection: ShareCardSelection = {
      가장많이한것: true,
      처음한것: true,
      감정순간: true,
    };

    expect(buildShareCardItems(highlights, selection)).toEqual([
      { slot: "가장많이한것", label: "가장 많이", ...highlights.가장많이한것 },
      { slot: "처음한것", label: "처음", ...highlights.처음한것 },
      { slot: "감정순간", label: "감정", ...highlights.감정순간 },
    ]);
  });

  it("해제했거나 비어 있는 슬롯은 카드에 넣지 않는다", () => {
    expect(
      buildShareCardItems(
        { ...highlights, 감정순간: null },
        {
          가장많이한것: true,
          처음한것: false,
          감정순간: true,
        },
      ),
    ).toEqual([
      { slot: "가장많이한것", label: "가장 많이", ...highlights.가장많이한것 },
    ]);
  });
});
