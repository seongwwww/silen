# 기록 화면(record screen) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 홈(`/`)을 기록 화면으로 교체한다 — 한 줄 입력 + 전송, 선택형 감정 칩, 저장 후 초기화하고 머문다(연달아 쓰기).

**Architecture:** 순수 프론트 슬라이스. `app/page.tsx`(서버 컴포넌트)가 `RecordForm`(클라이언트)을 렌더하고, 폼이 기존 `POST /api/memories`를 호출한다. 백엔드·스키마 변경 없음. 감정 칩은 이 화면 전용 컴포넌트로 두고 두 번째 사용처가 생길 때 공통화한다.

**Tech Stack:** Next.js 16.2.11(App Router) · React 19 · TypeScript · Tailwind v4 · shadcn/ui · sonner · Vitest 4 + Testing Library(jsdom)

## Global Constraints

- 산출물은 **코드**다. `main` 직접 커밋 금지 — `feat/record-screen` 브랜치(생성됨).
- 커밋 `<type>(<scope>): <한국어 요약>` + `Co-Authored-By` 트레일러(작성자 본인 것). scope는 `ui`. **커밋만, push/merge는 사람.**
- **백엔드·스키마 변경 없음** — 기존 `POST /api/memories`(`{text, emotion?, assetPaths?, occurredAt?}`) 재사용. 새 라우트·마이그레이션 만들지 마라.
- **앱 코드 전 Next.js 16 문서 필독**(AGENTS.md): `node_modules/next/dist/docs/01-app/`. 학습데이터와 다르다.
- **세션 처리 금지** — API가 세션 없으면 익명 세션을 자동 생성한다. 폼에서 로그인·세션 로직을 넣지 마라.
- ⚠️ **`POST /api/memories`는 멱등이 아니다** — 이중 클릭이 중복 메모를 만든다. **in-flight 가드 필수**(아래 Locked Decision 4).
- **실패 시 입력 내용을 절대 비우지 않는다**(사용자가 쓴 글을 잃는 것이 최악).
- frontend.md: 죄책감·독려·축하 문구 금지 · 담담한 한국어 · 44px 터치 타깃 · **색만으로 의미 전달 금지**(감정 칩은 `aria-pressed` + 텍스트) · 포커스 표시.
- DoD = lint + typecheck(build) + unit. 통합 테스트는 기존 API 것으로 충분(추가하지 않는다).
- 테스트 인프라는 이미 있다(vitest react plugin·jsdom·`app/**/*.test.tsx` include). 컴포넌트 테스트 파일 상단에 `// @vitest-environment jsdom` + `import "@testing-library/jest-dom/vitest";`.

## 결정 고정 (Locked Decisions)

1. **감정 값 매핑** — 라벨 `좋았어요`→`good`, `그냥`→`neutral`, `별로`→`bad`. 타입은 기존 `EmotionChoice`(`@/lib/services/memory`)를 재사용한다.
2. **감정은 선택·토글** — 미선택 기본. 같은 칩을 다시 누르면 해제(`undefined`). 미선택이면 요청 바디에 `emotion` 키를 넣지 않는다(`JSON.stringify`가 `undefined`를 생략).
3. **요청 바디** — `{ text: <trim된 값>, emotion?: EmotionChoice }`만. `assetPaths`·`occurredAt`은 보내지 않는다(서버가 `captured_at` 기본값 사용).
4. **중복 전송 방지** — `useRef` 동기 가드 + 버튼 `disabled` **둘 다**. state는 비동기라 빠른 이중 클릭에 경쟁이 생긴다: 함수 진입 즉시 `if (inFlight.current) return; inFlight.current = true;`, `finally`에서 해제.
5. **빈 입력** — `text.trim() === ""`이면 전송 버튼 `disabled`. 서버 왕복 없이 차단.
6. **엔터 정책** — 엔터는 줄바꿈(기본 동작 유지). `Ctrl+Enter`/`Cmd+Enter`만 전송.
7. **자동 확장** — `useEffect`에서 `el.style.height="auto"` 후 `Math.min(scrollHeight, MAX_HEIGHT_PX)`로 설정. `MAX_HEIGHT_PX = 160`(약 6줄). **jsdom은 `scrollHeight`가 0이라 이 동작은 테스트하지 않는다**(브라우저 육안 확인).
8. **offline** — 전송 시작 시 `navigator.onLine === false`면 fetch하지 않고 `toast.error("지금은 오프라인이에요. 연결되면 다시 시도해 주세요.")` 후 **입력 보존**하고 종료. 큐잉 없음.
9. **성공 처리** — 입력·감정 초기화, `toast("기록했어요")`, textarea에 **포커스 유지**. 화면 이동·축하 문구 없음.
10. **실패 처리** — `res.ok`가 false거나 fetch가 throw하면 `toast.error("기록하지 못했어요. 다시 시도해 주세요.")`, **입력·감정 그대로 보존**. 자동 재시도 없음.
11. **컴포넌트 배치** — `EmotionChips`는 `app/_components/`(이 화면 전용). 두 번째 사용처가 생기면 `components/common/`으로 승격. 지금 성급히 공통화하지 않는다.
12. **홈 교체** — `app/page.tsx`의 Next 스캐폴딩을 전부 제거하고 기록 화면으로. `app/layout.tsx`의 `metadata`를 `{ title: "실은", description: "실은 아무것도 아니지 않았다" }`로 교체. `<Toaster/>`는 이미 마운트돼 있으니 건드리지 않는다.
13. **커밋 단위** — 태스크마다 1커밋. push/merge 안 함.

## File Structure

| 경로 | 책임 |
|------|------|
| `components/ui/textarea.tsx` | shadcn textarea(추가) |
| `app/_components/EmotionChips.tsx` | 감정 칩 3종(선택·토글·a11y) |
| `app/_components/EmotionChips.test.tsx` | 토글·aria-pressed·콜백 단위 |
| `app/_components/RecordForm.tsx` | 입력·전송·상태·중복방지(클라이언트) |
| `app/_components/RecordForm.test.tsx` | 빈입력·바디·중복방지·실패보존·성공초기화 |
| `app/page.tsx`(교체) | 홈 = 기록 화면(서버 컴포넌트) |
| `app/layout.tsx`(수정) | metadata를 "실은"으로 |
| `README.md`(수정) | 구조 한 줄 |

---

## Task 1: 감정 칩 (선택·토글·접근성)

**Files:** Create `app/_components/EmotionChips.tsx`, `app/_components/EmotionChips.test.tsx`; Add `components/ui/textarea.tsx`(shadcn)

**Interfaces — Produces:**
```tsx
// value가 undefined면 미선택. 같은 값을 다시 고르면 onChange(undefined).
export function EmotionChips(props: {
  value: EmotionChoice | undefined;
  onChange: (next: EmotionChoice | undefined) => void;
  disabled?: boolean;
}): JSX.Element
```

- [ ] **Step 1: shadcn textarea 추가**(Task 2에서 쓴다)
```powershell
npx shadcn@latest add textarea
```
Expected: `components/ui/textarea.tsx` 생성. 대화형으로 멈추면 기본값으로 답한다.

- [ ] **Step 2: 실패 테스트** — `app/_components/EmotionChips.test.tsx`:
```tsx
// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { EmotionChips } from "./EmotionChips";

describe("EmotionChips", () => {
  it("세 가지 감정을 라벨로 보여준다", () => {
    render(<EmotionChips value={undefined} onChange={() => {}} />);
    expect(screen.getByRole("button", { name: "좋았어요" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "그냥" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "별로" })).toBeInTheDocument();
  });

  it("선택 상태를 aria-pressed로 알린다(색만으로 전달하지 않음)", () => {
    render(<EmotionChips value="good" onChange={() => {}} />);
    expect(screen.getByRole("button", { name: "좋았어요" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "그냥" })).toHaveAttribute("aria-pressed", "false");
  });

  it("고르면 해당 값을 알린다", async () => {
    const onChange = vi.fn();
    render(<EmotionChips value={undefined} onChange={onChange} />);
    await userEvent.click(screen.getByRole("button", { name: "별로" }));
    expect(onChange).toHaveBeenCalledWith("bad");
  });

  it("같은 걸 다시 누르면 해제한다", async () => {
    const onChange = vi.fn();
    render(<EmotionChips value="neutral" onChange={onChange} />);
    await userEvent.click(screen.getByRole("button", { name: "그냥" }));
    expect(onChange).toHaveBeenCalledWith(undefined);
  });
});
```

- [ ] **Step 3: 실패 확인** — `npx vitest run app/_components/EmotionChips.test.tsx`. Expected: FAIL(모듈 없음).

- [ ] **Step 4: 구현** — `app/_components/EmotionChips.tsx`:
```tsx
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
      {CHOICES.map((c) => {
        const selected = value === c.value;
        return (
          <Button
            key={c.value}
            type="button"
            variant="outline"
            size="sm"
            aria-pressed={selected}
            disabled={disabled}
            onClick={() => onChange(selected ? undefined : c.value)}
            className={`min-h-9 rounded-full px-3 text-[13px] ${
              selected ? "border-foreground font-medium" : "text-muted-foreground"
            }`}
          >
            {c.label}
          </Button>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 5: 통과 확인** — `npx vitest run app/_components/EmotionChips.test.tsx` → 4 PASS. `npm run lint`.

- [ ] **Step 6: 커밋**
```powershell
git add components/ui/textarea.tsx app/_components/EmotionChips.tsx app/_components/EmotionChips.test.tsx
git commit -m "feat(ui): 감정 칩 — 선택·토글·aria-pressed

미선택이 기본이고 같은 칩을 다시 누르면 해제된다(감정 입력은 의무가 아니다).
선택 상태를 색이 아니라 aria-pressed와 텍스트로 전달한다. shadcn textarea 추가."
```

---

## Task 2: 기록 폼 (입력·전송·중복방지·상태)

**Files:** Create `app/_components/RecordForm.tsx`, `app/_components/RecordForm.test.tsx`

**Interfaces — Consumes:** Task 1 `EmotionChips`, shadcn `Textarea`·`Button`, `sonner`. **Produces:** `export function RecordForm(): JSX.Element`

- [ ] **Step 1: 실패 테스트** — `app/_components/RecordForm.test.tsx`:
```tsx
// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { RecordForm } from "./RecordForm";

const input = () => screen.getByLabelText("오늘의 기록");
const sendButton = () => screen.getByRole("button", { name: "기록하기" });

// navigator 객체 전체를 stub하면 userEvent가 쓰는 clipboard가 사라져 깨진다.
// onLine 속성만 갈아끼운다.
function setOnLine(value: boolean) {
  Object.defineProperty(navigator, "onLine", { value, configurable: true });
}

beforeEach(() => {
  vi.restoreAllMocks();
  setOnLine(true);
});

describe("RecordForm", () => {
  it("빈 입력이면 전송할 수 없다", () => {
    render(<RecordForm />);
    expect(sendButton()).toBeDisabled();
  });

  it("공백만 있어도 전송할 수 없다", async () => {
    render(<RecordForm />);
    await userEvent.type(input(), "   ");
    expect(sendButton()).toBeDisabled();
  });

  it("텍스트와 감정을 바디에 담아 보낸다", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true });
    vi.stubGlobal("fetch", fetchMock);
    render(<RecordForm />);
    await userEvent.type(input(), "점심에 김밥");
    await userEvent.click(screen.getByRole("button", { name: "좋았어요" }));
    await userEvent.click(sendButton());
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/memories");
    expect(JSON.parse(init.body)).toEqual({ text: "점심에 김밥", emotion: "good" });
  });

  it("감정을 안 고르면 emotion을 보내지 않는다", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true });
    vi.stubGlobal("fetch", fetchMock);
    render(<RecordForm />);
    await userEvent.type(input(), "그냥 하루");
    await userEvent.click(sendButton());
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ text: "그냥 하루" });
  });

  it("성공하면 입력을 비우고 머문다", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true }));
    render(<RecordForm />);
    await userEvent.type(input(), "김밥");
    await userEvent.click(sendButton());
    await waitFor(() => expect(input()).toHaveValue(""));
  });

  it("실패하면 입력을 보존한다", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false }));
    render(<RecordForm />);
    await userEvent.type(input(), "잃으면 안 되는 글");
    await userEvent.click(sendButton());
    await waitFor(() => expect(input()).toHaveValue("잃으면 안 되는 글"));
  });

  it("이중 클릭에도 한 번만 보낸다(POST는 멱등이 아니다)", async () => {
    let resolve!: (v: unknown) => void;
    const pending = new Promise((r) => { resolve = r; });
    const fetchMock = vi.fn().mockReturnValue(pending);
    vi.stubGlobal("fetch", fetchMock);
    render(<RecordForm />);
    await userEvent.type(input(), "중복 금지");
    const btn = sendButton();
    await userEvent.click(btn);
    await userEvent.click(btn); // 응답 전 두 번째 클릭
    expect(fetchMock).toHaveBeenCalledTimes(1);
    resolve({ ok: true });
  });

  it("오프라인이면 보내지 않고 입력을 보존한다", async () => {
    setOnLine(false);
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    render(<RecordForm />);
    await userEvent.type(input(), "오프라인 글");
    await userEvent.click(sendButton());
    expect(fetchMock).not.toHaveBeenCalled();
    expect(input()).toHaveValue("오프라인 글");
  });
});
```

- [ ] **Step 2: 실패 확인** — `npx vitest run app/_components/RecordForm.test.tsx`. Expected: FAIL(모듈 없음).

- [ ] **Step 3: 구현** — `app/_components/RecordForm.tsx`:
```tsx
"use client";
import { useEffect, useRef, useState } from "react";
import { ArrowUp } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { EmotionChips } from "./EmotionChips";
import type { EmotionChoice } from "@/lib/services/memory";

const MAX_HEIGHT_PX = 160; // 약 6줄. 그 이상은 스크롤.

/** 기록 입력. 파이프라인의 입구다 — 열자마자 한 줄 쓰고 보내는 것이 전부여야 한다.
 * POST /api/memories는 멱등이 아니라 이중 전송이 중복 메모를 만든다(가드 필수).
 * 실패해도 사용자가 쓴 글은 절대 비우지 않는다. */
export function RecordForm() {
  const [text, setText] = useState("");
  const [emotion, setEmotion] = useState<EmotionChoice | undefined>(undefined);
  const [saving, setSaving] = useState(false);
  const inFlight = useRef(false);
  const areaRef = useRef<HTMLTextAreaElement>(null);

  // 내용에 맞춰 높이를 키운다(최대 MAX_HEIGHT_PX).
  useEffect(() => {
    const el = areaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, MAX_HEIGHT_PX)}px`;
  }, [text]);

  const canSend = text.trim().length > 0 && !saving;

  async function submit() {
    if (inFlight.current) return; // 동기 가드 — state는 비동기라 이중 클릭을 못 막는다
    const body = text.trim();
    if (!body) return;
    if (typeof navigator !== "undefined" && navigator.onLine === false) {
      toast.error("지금은 오프라인이에요. 연결되면 다시 시도해 주세요.");
      return;
    }
    inFlight.current = true;
    setSaving(true);
    try {
      const res = await fetch("/api/memories", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ text: body, emotion }),
      });
      if (!res.ok) throw new Error("save failed");
      setText("");
      setEmotion(undefined);
      toast("기록했어요");
      areaRef.current?.focus(); // 연달아 쓸 수 있게
    } catch {
      // 쓴 글은 그대로 둔다.
      toast.error("기록하지 못했어요. 다시 시도해 주세요.");
    } finally {
      inFlight.current = false;
      setSaving(false);
    }
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-start gap-2">
        <label htmlFor="record-text" className="sr-only">오늘의 기록</label>
        <Textarea
          id="record-text"
          ref={areaRef}
          rows={1}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
              e.preventDefault();
              void submit();
            }
          }}
          placeholder="오늘, 실은…"
          className="min-h-11 flex-1 resize-none"
        />
        <Button
          type="button"
          aria-label="기록하기"
          disabled={!canSend}
          onClick={() => void submit()}
          className="min-h-11 min-w-11"
        >
          <ArrowUp className="size-4" aria-hidden />
        </Button>
      </div>
      <EmotionChips value={emotion} onChange={setEmotion} disabled={saving} />
      <p className="text-[12px] text-muted-foreground">기분은 안 골라도 괜찮아요</p>
    </div>
  );
}
```

- [ ] **Step 4: 통과 확인** — `npx vitest run app/_components/RecordForm.test.tsx` → 8 PASS. `npm run lint`.
> 구현자 주의: shadcn `Textarea`가 `ref`를 전달하지 않으면(React 19에서는 보통 전달됨) `forwardRef` 여부를 확인하고, 필요하면 `components/ui/textarea.tsx`가 `ref`를 그대로 넘기도록 최소 수정한다. 테스트가 `getByLabelText("오늘의 기록")`로 접근하므로 `id`/`htmlFor` 연결은 유지한다.

- [ ] **Step 5: 커밋**
```powershell
git add app/_components/RecordForm.tsx app/_components/RecordForm.test.tsx
git commit -m "feat(ui): 기록 폼 — 입력·전송·중복방지·실패보존

한 줄 입력+전송, 자동 확장, Ctrl/Cmd+Enter 전송. POST가 멱등이 아니라
useRef 동기 가드로 이중 전송을 막고, 실패해도 쓴 글은 비우지 않는다.
성공하면 비우고 포커스를 남겨 연달아 쓸 수 있다."
```

---

## Task 3: 홈 교체

**Files:** Modify `app/page.tsx`, `app/layout.tsx`

- [ ] **Step 1: 홈을 기록 화면으로** — `app/page.tsx` 전체 교체(Next 스캐폴딩 제거):
```tsx
import { RecordForm } from "./_components/RecordForm";

export default function Home() {
  return (
    <main className="mx-auto flex min-h-svh max-w-md flex-col justify-center p-4">
      <h1 className="mb-3 text-lg font-medium">오늘, 실은</h1>
      <RecordForm />
    </main>
  );
}
```

- [ ] **Step 2: metadata** — `app/layout.tsx`의 `metadata`를 교체:
```tsx
export const metadata: Metadata = {
  title: "실은",
  description: "실은 아무것도 아니지 않았다",
};
```
`<Toaster/>`와 폰트 설정은 그대로 둔다.

- [ ] **Step 3: 검증**
```powershell
npm run lint
npx vitest run
npm run build
```
Expected: 전부 통과. 그다음 개발 서버에서 `/` 육안 확인 — 모바일 폭(390px)에서 입력→전송→"기록했어요" 토스트→입력창 비워짐·포커스 유지, 긴 글에서 textarea가 최대 높이까지 늘어난 뒤 스크롤되는지.
> 육안 확인이 안 되는 환경이면(서버 미가동 등) 그 사실을 보고하고 넘어간다 — 자동 검사는 위 3개로 충분하다.

- [ ] **Step 4: 커밋**
```powershell
git add app/page.tsx app/layout.tsx
git commit -m "feat(ui): 홈을 기록 화면으로 교체

Next 스캐폴딩을 걷어내고 첫 화면을 기록 입력으로. metadata를 '실은'으로.
파이프라인 입구가 사람 손에 닿는다."
```

---

## Task 4: 문서·마무리

**Files:** Modify `README.md`

- [ ] **Step 1: README** — 저장소 구조 절에 추가:
```
app/_components/         # 홈(기록) 전용 컴포넌트 — RecordForm·EmotionChips
```
그리고 홈이 기록 화면임을 한 줄로 적는다(`app/` 설명 근처).

- [ ] **Step 2: 전체 검사**
```powershell
npm run lint
npx vitest run
npx vitest run --config vitest.integration.config.mts
npm run build
```
Expected: 전부 통과(통합은 로컬 Supabase + 라이브 dev 서버 필요 — 안 떠 있으면 그 사실을 보고).

- [ ] **Step 3: 커밋**
```powershell
git add README.md
git commit -m "docs: 홈 기록 화면 구조 안내"
```

- [ ] **Step 4: 브랜치 마무리** — `/superpowers:finishing-a-development-branch`. rebase 후 `merge --no-ff`(squash 금지). **병합·push는 사람.**
> 보안 리뷰는 이번엔 불필요하다 — 인증·삭제·RAG 변경이 없고(세션은 기존 API가 처리), 새 엔드포인트도 없다.

---

## 완료 기준
- 홈(`/`)이 기록 화면이고, 텍스트(+선택 감정)로 메모가 저장된다.
- 빈 입력 차단 · 이중 클릭 1회 전송 · 실패 시 입력 보존 · 성공 시 초기화·포커스 유지 · 오프라인 안내.
- 감정 칩 토글과 `aria-pressed`, 44px 타깃, 담담한 문구.
- lint + unit + build 통과. 백엔드·스키마 변경 없음.

## 이번 범위 밖
- 사진 첨부 · 기록 열람/목록 · 오프라인 큐잉 · 음성 입력.
- 홈의 다른 위젯(일기·차이 요약) · 파이프라인 스케줄 트리거 · 로그인 UI.
