// @vitest-environment jsdom
import { describe, expect, it, vi } from "vitest";
import { paintShareCard } from "./shareCardClient";

describe("공유 카드 PNG 렌더", () => {
  it("1080 정사각형 캔버스에 선택한 요약과 브랜드명만 그린다", () => {
    const fillText = vi.fn();
    const context = {
      fillStyle: "",
      strokeStyle: "",
      lineWidth: 1,
      font: "",
      textBaseline: "alphabetic",
      fillRect: vi.fn(),
      fillText,
      measureText: (text: string) => ({ width: text.length * 20 }),
      beginPath: vi.fn(),
      moveTo: vi.fn(),
      lineTo: vi.fn(),
      stroke: vi.fn(),
    } as unknown as CanvasRenderingContext2D;
    const canvas = {
      width: 0,
      height: 0,
      getContext: vi.fn().mockReturnValue(context),
    } as unknown as HTMLCanvasElement;

    paintShareCard(canvas, [
      {
        slot: "가장많이한것",
        label: "가장 많이",
        headline: "김밥",
        detail: "7일 기록에서 4번 언급됐어요.",
      },
    ]);

    expect(canvas.width).toBe(1080);
    expect(canvas.height).toBe(1080);
    expect(fillText).toHaveBeenCalledWith("이번 주의 나", 96, 142);
    expect(fillText).toHaveBeenCalledWith("가장 많이", 96, 330);
    expect(fillText).toHaveBeenCalledWith("김밥", 310, 330);
    expect(fillText).toHaveBeenCalledWith("실은", 96, 986);
  });
});
