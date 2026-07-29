import type { ShareCardItem } from "./shareCard";

export const SHARE_CARD_SIZE = 1080;
const FONT_STACK =
  '"Pretendard", "Noto Sans KR", "Apple SD Gothic Neo", "Malgun Gothic", sans-serif';

function fitLine(
  context: CanvasRenderingContext2D,
  text: string,
  maxWidth: number,
): string {
  if (context.measureText(text).width <= maxWidth) return text;
  let fitted = "";
  for (const character of text) {
    if (context.measureText(`${fitted}${character}…`).width > maxWidth) break;
    fitted += character;
  }
  return `${fitted}…`;
}

function wrapLines(
  context: CanvasRenderingContext2D,
  text: string,
  maxWidth: number,
  maxLines: number,
): string[] {
  const words = text.split(/\s+/).filter(Boolean);
  const lines: string[] = [];
  let current = "";
  for (const word of words) {
    const candidate = current ? `${current} ${word}` : word;
    if (context.measureText(candidate).width <= maxWidth) {
      current = candidate;
      continue;
    }
    if (current) lines.push(current);
    current = word;
    if (lines.length === maxLines - 1) break;
  }
  if (current && lines.length < maxLines) lines.push(current);
  const consumed = lines.join(" ").length;
  if (consumed < text.length && lines.length > 0) {
    lines[lines.length - 1] = fitLine(
      context,
      `${lines[lines.length - 1]}…`,
      maxWidth,
    );
  }
  return lines;
}

/** 외부 이미지·폰트·네트워크 없이 1080px 정사각형을 그린다. */
export function paintShareCard(
  canvas: HTMLCanvasElement,
  items: ShareCardItem[],
): void {
  canvas.width = SHARE_CARD_SIZE;
  canvas.height = SHARE_CARD_SIZE;
  const context = canvas.getContext("2d");
  if (!context) throw new Error("canvas_context_unavailable");

  context.fillStyle = "#f7f3ea";
  context.fillRect(0, 0, SHARE_CARD_SIZE, SHARE_CARD_SIZE);
  context.textBaseline = "alphabetic";

  context.fillStyle = "#20211d";
  context.font = `700 64px ${FONT_STACK}`;
  context.fillText("이번 주의 나", 96, 142);
  context.fillStyle = "#6c6b65";
  context.font = `400 28px ${FONT_STACK}`;
  context.fillText("기록에서 찾은 세 가지 모습", 96, 196);

  items.forEach((item, index) => {
    const y = 330 + index * 206;
    context.fillStyle = "#9a6239";
    context.font = `600 30px ${FONT_STACK}`;
    context.fillText(item.label, 96, y);
    context.fillStyle = "#20211d";
    context.font = `700 48px ${FONT_STACK}`;
    context.fillText(fitLine(context, item.headline, 670), 310, y);
    context.fillStyle = "#6c6b65";
    context.font = `400 28px ${FONT_STACK}`;
    for (const [lineIndex, line] of wrapLines(
      context,
      item.detail,
      670,
      2,
    ).entries()) {
      context.fillText(line, 310, y + 52 + lineIndex * 38);
    }
    context.strokeStyle = "#ded7cb";
    context.lineWidth = 2;
    context.beginPath();
    context.moveTo(96, y + 142);
    context.lineTo(984, y + 142);
    context.stroke();
  });

  context.fillStyle = "#20211d";
  context.font = `700 36px ${FONT_STACK}`;
  context.fillText("실은", 96, 986);
}

export type DownloadShareCard = (
  items: ShareCardItem[],
  weekStart: string,
) => Promise<void>;

/** PNG를 브라우저 메모리에서 만들고 즉시 다운로드한다. 서버 전송은 없다. */
export const downloadShareCard: DownloadShareCard = async (
  items,
  weekStart,
) => {
  if (document.fonts?.ready) await document.fonts.ready;
  const canvas = document.createElement("canvas");
  paintShareCard(canvas, items);
  const blob = await new Promise<Blob>((resolve, reject) => {
    canvas.toBlob((value) => {
      if (value) resolve(value);
      else reject(new Error("png_creation_failed"));
    }, "image/png");
  });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `silen-week-${weekStart}.png`;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
};
