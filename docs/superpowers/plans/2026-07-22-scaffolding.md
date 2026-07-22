# 스캐폴딩 (2자산 + 테스트 하네스 + 로컬 DB) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Next.js 앱과 Python 워커가 각각 부팅되고, lint·typecheck·unit·integration이 실제로 실행되며, 로컬 Supabase에 마이그레이션이 재현 가능하게 적용되는 상태를 만든다.

**Architecture:** `backend.md`의 2자산 구조를 그대로 디렉터리로 옮긴다. Next.js는 저장소 루트, Python 워커는 `worker/`. 두 자산이 공유해야 하는 "하루 경계" 정의는 코드를 공유할 수 없으므로 **골든 픽스처 하나를 양쪽 테스트가 함께 읽는 방식**으로 일치를 강제한다. 3계층 의존 규칙은 문서가 아니라 ESLint로 기계 검사한다.

**Tech Stack:** Next.js(App Router) · TypeScript · Tailwind · Vitest · Python 3.11+ · pytest · ruff · Supabase CLI(로컬 Postgres + pgvector + PostGIS)

## Global Constraints

- 이 계획의 산출물은 **코드**다. `.claude/rules/git.md`에 따라 `main` 직접 커밋 금지 — `feat/scaffolding` 브랜치(worktree)에서 작업한다.
- 커밋 메시지는 `<type>(<scope>): <한국어 요약>`. Claude 작성 시 `Co-Authored-By` 트레일러를 남긴다.
- 커밋 메시지·브랜치명·fixture 파일명에 사용자 기록 본문을 넣지 않는다.
- Next.js는 **저장소 루트**에 둔다(README 기준). Python 워커는 `worker/`.
- Python 버전 `>=3.11` (`datetime.fromisoformat`의 `Z` 지원과 `zoneinfo`가 필요).
- **Windows에서는 `tzdata` 패키지가 필수다.** Windows에는 시스템 tz 데이터베이스가 없어 `zoneinfo`가 실패한다.
- Supabase 로컬 스택은 **Docker Desktop이 실행 중**이어야 한다.
- 기존 `README.md` · `.gitignore` · `CLAUDE.md` · `docs/` · `.claude/`를 덮어쓰지 않는다.
- 이 계획은 **큐 배선·실제 스키마를 포함하지 않는다.** 그것은 후속 계획(C)의 몫이다.

---

## File Structure

| 경로 | 책임 |
|------|------|
| `package.json` `next.config.ts` `tsconfig.json` | Next.js 앱 자산 |
| `app/` | 경계 계층 — Route Handler·페이지 |
| `lib/time/day.ts` | "하루" 경계 단일 유틸 (backend.md 요구) |
| `lib/services/` | 서비스 계층 (프레임워크 타입 모름) |
| `lib/repositories/` | 저장소 계층 (쿼리·user 스코프 강제) |
| `components/ui/` `components/common/` | frontend.md 공통 컴포넌트 배치 |
| `fixtures/day-boundary.json` | 두 자산이 공유하는 날짜 경계 골든 케이스 |
| `eslint.config.mjs` | 3계층 의존 규칙 기계 검사 |
| `vitest.config.ts` `vitest.integration.config.ts` | 단위 / 통합 테스트 분리 |
| `worker/pyproject.toml` | 워커 자산 정의·도구 설정 |
| `worker/src/silen_worker/time.py` | 워커 쪽 하루 경계 (픽스처로 TS와 일치 검증) |
| `worker/tests/` | pytest |
| `supabase/migrations/` | 마이그레이션 (up) |
| `supabase/migrations/down/` | 대응 down 스크립트 (database.md 요구) |

---

## Task 1: Next.js 앱 스캐폴딩

기존 `README.md`·`.gitignore`와 충돌하지 않게 임시 디렉터리에 생성 후 병합한다. `create-next-app`은 대상 디렉터리에 자신이 만들 파일과 같은 이름이 있으면 거부하므로 `.`에 직접 실행할 수 없다.

**Files:**
- Create: `package.json`, `tsconfig.json`, `next.config.ts`, `postcss.config.mjs`, `eslint.config.mjs`, `app/layout.tsx`, `app/page.tsx`, `app/globals.css`
- Modify: 없음

**Interfaces:**
- Consumes: 없음 (최초 태스크)
- Produces: npm 스크립트 `dev` `build` `start` `lint`, 경로 별칭 `@/*` → 저장소 루트

- [ ] **Step 1: 브랜치 생성**

```powershell
git checkout -b feat/scaffolding
```

- [ ] **Step 2: 임시 디렉터리에 Next.js 생성**

```powershell
npx create-next-app@latest scaffold-tmp --typescript --tailwind --app --eslint --no-src-dir --import-alias "@/*" --use-npm --yes
```

Expected: `Success! Created scaffold-tmp` 로 끝남. 중간에 질문이 뜨면 `--yes`가 먹지 않은 것이므로 기본값으로 답한다.

- [ ] **Step 3: 저장소 파일을 보존하며 병합**

`scaffold-tmp`의 `README.md`·`.gitignore`는 버린다. 우리 것이 이미 더 구체적이다(`.gitignore`에 `node_modules/`·`.next/`가 이미 있음).

```powershell
Remove-Item scaffold-tmp\README.md, scaffold-tmp\.gitignore -Force -ErrorAction SilentlyContinue
Get-ChildItem -Path scaffold-tmp -Force | Move-Item -Destination . -Force
Remove-Item scaffold-tmp -Recurse -Force
```

- [ ] **Step 4: 빌드가 통과하는지 확인**

```powershell
npm run build
```

Expected: `✓ Compiled successfully` 후 라우트 표가 출력되고 종료 코드 0.

- [ ] **Step 5: lint가 통과하는지 확인**

```powershell
npx eslint .
```

Expected: 출력 없음, 종료 코드 0.

- [ ] **Step 6: 커밋**

```powershell
git add -A
git commit -m "chore(app): Next.js 앱 스캐폴딩

create-next-app을 임시 디렉터리에 생성 후 병합.
기존 README.md·.gitignore는 보존."
```

---

## Task 2: 하루 경계 유틸 + Vitest 하네스

`backend.md`는 "하루의 정의는 단일 유틸(`lib/time`)에서만"을 요구한다. 테스트 하네스의 첫 대상으로 이걸 쓴다 — 더미 테스트 대신 실제로 필요한 규칙을 구현하면서 러너를 세운다.

픽스처를 **별도 JSON 파일**로 두는 이유: Task 4의 Python 워커가 같은 파일을 읽어 동일한 결과를 내는지 검증한다. 두 런타임이 코드를 공유할 수 없으므로 픽스처가 계약서 역할을 한다.

**Files:**
- Create: `fixtures/day-boundary.json`, `lib/time/day.ts`, `lib/time/day.test.ts`, `vitest.config.ts`
- Modify: `package.json` (scripts)

**Interfaces:**
- Consumes: Task 1의 `@/*` 별칭, TypeScript 설정
- Produces: `localDateFor(instant: Date, timeZone: string): string` — UTC 시각과 IANA 타임존을 받아 `YYYY-MM-DD` 로컬 날짜 문자열 반환. Task 4의 Python `local_date_for`가 동일 계약을 따른다.

- [ ] **Step 1: 골든 픽스처 작성**

`fixtures/day-boundary.json`:

```json
{
  "description": "사용자 로컬 자정 기준 '하루' 경계. Next.js(lib/time)와 Python 워커가 동일한 결과를 내야 한다.",
  "cases": [
    {
      "name": "seoul-one-second-before-local-midnight",
      "timezone": "Asia/Seoul",
      "instant": "2026-03-01T14:59:59Z",
      "expectedLocalDate": "2026-03-01"
    },
    {
      "name": "seoul-exactly-local-midnight",
      "timezone": "Asia/Seoul",
      "instant": "2026-03-01T15:00:00Z",
      "expectedLocalDate": "2026-03-02"
    },
    {
      "name": "utc-noon-stays-same-day",
      "timezone": "UTC",
      "instant": "2026-03-01T12:00:00Z",
      "expectedLocalDate": "2026-03-01"
    },
    {
      "name": "new-york-before-dst-start-boundary",
      "timezone": "America/New_York",
      "instant": "2026-03-08T04:59:59Z",
      "expectedLocalDate": "2026-03-07"
    },
    {
      "name": "new-york-at-dst-start-boundary",
      "timezone": "America/New_York",
      "instant": "2026-03-08T05:00:00Z",
      "expectedLocalDate": "2026-03-08"
    },
    {
      "name": "new-york-day-after-dst-shifts-utc-offset",
      "timezone": "America/New_York",
      "instant": "2026-03-09T03:59:59Z",
      "expectedLocalDate": "2026-03-08"
    },
    {
      "name": "new-york-day-after-dst-crosses-at-0400z",
      "timezone": "America/New_York",
      "instant": "2026-03-09T04:00:00Z",
      "expectedLocalDate": "2026-03-09"
    }
  ]
}
```

마지막 두 케이스가 핵심이다. DST 시작 후 뉴욕의 자정은 UTC 기준 `05:00Z`가 아니라 `04:00Z`로 옮겨간다. **고정 오프셋으로 구현하면 여기서 깨진다.**

- [ ] **Step 2: Vitest 설치 및 설정**

```powershell
npm install -D vitest vite-tsconfig-paths
```

`vitest.config.ts`:

```ts
import { defineConfig } from "vitest/config";
import tsconfigPaths from "vite-tsconfig-paths";

export default defineConfig({
  plugins: [tsconfigPaths()],
  test: {
    environment: "node",
    include: ["lib/**/*.test.ts", "app/**/*.test.ts"],
    // 통합 테스트는 별도 러너로 분리한다(Task 5). 이 제외가 없으면
    // lib/**/*.test.ts 패턴이 *.integration.test.ts 도 함께 잡는다.
    exclude: ["node_modules", ".next", "**/*.integration.test.ts"],
  },
});
```

`package.json`의 `scripts`에 추가:

```json
"test": "vitest run",
"typecheck": "tsc --noEmit"
```

- [ ] **Step 3: 실패하는 테스트 작성**

`lib/time/day.test.ts`:

```ts
import { describe, it, expect } from "vitest";
import fixture from "@/fixtures/day-boundary.json";
import { localDateFor } from "./day";

describe("localDateFor", () => {
  for (const testCase of fixture.cases) {
    it(testCase.name, () => {
      const result = localDateFor(new Date(testCase.instant), testCase.timezone);
      expect(result).toBe(testCase.expectedLocalDate);
    });
  }
});
```

- [ ] **Step 4: 테스트가 실패하는지 확인**

```powershell
npm test
```

Expected: FAIL. `Failed to resolve import "./day"` 또는 그에 준하는 모듈 해석 오류.

- [ ] **Step 5: 최소 구현 작성**

`lib/time/day.ts`:

```ts
/**
 * 사용자 로컬 자정을 기준으로 한 "하루"의 날짜를 반환한다.
 * "하루"의 정의는 이 모듈에서만 관리한다(backend.md).
 *
 * en-CA 로케일은 YYYY-MM-DD 형식을 보장하며, Intl이 IANA 타임존의
 * DST 전환을 처리하므로 고정 오프셋 계산을 하지 않는다.
 */
export function localDateFor(instant: Date, timeZone: string): string {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(instant);
}
```

- [ ] **Step 6: 테스트가 통과하는지 확인**

```powershell
npm test
```

Expected: PASS. `Test Files 1 passed`, `Tests 7 passed`.

- [ ] **Step 7: 타입 검사**

```powershell
npm run typecheck
```

Expected: 출력 없음, 종료 코드 0. `resolveJsonModule` 오류가 나면 `tsconfig.json`의 `compilerOptions`에 `"resolveJsonModule": true`를 추가한다.

- [ ] **Step 8: 커밋**

```powershell
git add fixtures/day-boundary.json lib/time vitest.config.ts package.json package-lock.json tsconfig.json
git commit -m "feat(api): 하루 경계 유틸과 Vitest 하네스

backend.md의 '하루 정의는 단일 유틸에서만' 요구를 구현.
DST 전환 케이스를 골든 픽스처로 고정 — 고정 오프셋 구현은 실패한다.
픽스처는 Python 워커도 함께 읽어 두 자산의 일치를 강제한다."
```

---

## Task 3: 3계층 의존 규칙을 ESLint로 강제

`backend.md`는 "계층 건너뛰기 금지"와 "서비스가 Request/Response를 알면 안 된다"를 요구한다. 문서로만 두면 지켜지지 않으므로 lint로 막는다.

**Files:**
- Create: `lib/services/.gitkeep`, `lib/repositories/.gitkeep`, `components/ui/.gitkeep`, `components/common/.gitkeep`
- Modify: `eslint.config.mjs`

**Interfaces:**
- Consumes: Task 1의 `eslint.config.mjs`
- Produces: `app/**`에서 `lib/repositories/**` import 시 lint 에러, `lib/services/**`에서 `next*` import 시 lint 에러

- [ ] **Step 1: 계층 디렉터리 생성**

```powershell
New-Item -ItemType Directory -Force lib\services, lib\repositories, components\ui, components\common | Out-Null
New-Item -ItemType File lib\services\.gitkeep, lib\repositories\.gitkeep, components\ui\.gitkeep, components\common\.gitkeep | Out-Null
```

- [ ] **Step 2: eslint-plugin-import 설치**

```powershell
npm install -D eslint-plugin-import
```

- [ ] **Step 3: 경계 규칙 추가**

`create-next-app`이 생성한 `eslint.config.mjs`는 버전에 따라 내용이 달라지므로 **전체를 교체하지 말고 두 곳에 삽입**한다.

1. 파일 최상단, 기존 `import` 구문들 아래에 다음 한 줄을 추가:

```js
import importPlugin from "eslint-plugin-import";
```

2. `export default [ ... ]` 배열의 **마지막 요소로** 다음 두 객체를 추가(기존 `next/core-web-vitals` 항목은 그대로 둔다):

```js
  {
    files: ["app/**/*.{ts,tsx}"],
    plugins: { import: importPlugin },
    rules: {
      "import/no-restricted-paths": [
        "error",
        {
          zones: [
            {
              target: "./app",
              from: "./lib/repositories",
              message:
                "계층 건너뛰기 금지(backend.md): 경계에서 저장소를 직접 호출하지 말고 서비스를 거친다.",
            },
          ],
        },
      ],
    },
  },
  {
    files: ["lib/services/**/*.ts"],
    rules: {
      "no-restricted-imports": [
        "error",
        {
          patterns: [
            {
              group: ["next", "next/*"],
              message:
                "역방향 의존 금지(backend.md): 서비스 계층은 Request/Response를 알면 안 된다.",
            },
          ],
        },
      ],
    },
  },
```

- [ ] **Step 4: 규칙이 실제로 막는지 확인 (위반 프로브)**

세 개의 임시 파일을 만든다. import 대상이 실제로 존재해야 모듈 해석 오류가 아니라 **경계 규칙 때문에** 실패하는지 확인할 수 있다.

`lib/repositories/probeThing.ts` (import 대상):

```ts
export const probeThing = "probe";
```

`app/__probe__.ts` (위반 1 — 경계가 저장소를 직접 호출):

```ts
import { probeThing } from "@/lib/repositories/probeThing";
export const probe = probeThing;
```

`lib/services/__probe__.ts` (위반 2 — 서비스가 프레임워크를 앎):

```ts
import { NextResponse } from "next/server";
export const probe = NextResponse;
```

```powershell
npx eslint app/__probe__.ts lib/services/__probe__.ts
```

Expected: FAIL — 두 파일 각각에 위 메시지("계층 건너뛰기 금지…", "역방향 의존 금지…")가 출력되고 종료 코드 1.

**여기서 에러가 안 나면 규칙이 적용되지 않은 것이다.** 다음 단계로 넘어가지 말고 설정을 고친다.

- [ ] **Step 5: 프로브 제거 후 lint 통과 확인**

```powershell
Remove-Item app\__probe__.ts, lib\services\__probe__.ts, lib\repositories\probeThing.ts -Force
npx eslint .
```

Expected: 출력 없음, 종료 코드 0.

- [ ] **Step 6: 커밋**

```powershell
git add eslint.config.mjs lib components package.json package-lock.json
git commit -m "feat(api): 3계층 의존 규칙을 ESLint로 강제

backend.md의 계층 건너뛰기·역방향 의존 금지를 기계 검사로 전환.
- app/ → lib/repositories/ 직접 import 차단
- lib/services/ 에서 next* import 차단
문서로만 두면 지켜지지 않는다."
```

---

## Task 4: Python 워커 스캐폴딩 + 픽스처 일치 검증

워커가 부팅되고, TS와 **같은 픽스처**로 하루 경계 결과가 일치하는지 검증한다.

**Files:**
- Create: `worker/pyproject.toml`, `worker/src/silen_worker/__init__.py`, `worker/src/silen_worker/time.py`, `worker/tests/test_time.py`
- Modify: 없음

**Interfaces:**
- Consumes: Task 2의 `fixtures/day-boundary.json` (저장소 루트 기준 경로)
- Produces: `local_date_for(instant: datetime, time_zone: str) -> str` — Task 2의 `localDateFor`와 동일 계약

- [ ] **Step 1: 가상환경 생성**

```powershell
python -m venv worker\.venv
worker\.venv\Scripts\python.exe -m pip install --upgrade pip
```

`.gitignore`에 `.venv/`가 이미 있어 추적되지 않는다.

- [ ] **Step 2: `worker/pyproject.toml` 작성**

```toml
[project]
name = "silen-worker"
version = "0.0.0"
description = "실은 차이 탐지·서술 워커"
requires-python = ">=3.11"
dependencies = [
    "numpy",
    "scipy",
    "pandas",
    "tzdata",
]

[project.optional-dependencies]
dev = ["pytest", "ruff"]

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]

[tool.ruff]
line-length = 100
```

`tzdata`는 선택이 아니다. Windows에는 시스템 tz 데이터베이스가 없어 이게 없으면 `ZoneInfo("Asia/Seoul")`이 `ZoneInfoNotFoundError`로 죽는다.

- [ ] **Step 3: 의존성 설치**

```powershell
worker\.venv\Scripts\python.exe -m pip install -e "worker[dev]"
```

Expected: `Successfully installed ... silen-worker-0.0.0 ...`

- [ ] **Step 4: 패키지 초기화 파일 생성**

`worker/src/silen_worker/__init__.py`:

```python
"""실은 차이 탐지·서술 워커."""
```

- [ ] **Step 5: 실패하는 테스트 작성**

`worker/tests/test_time.py`:

```python
import json
from datetime import datetime
from pathlib import Path

import pytest

from silen_worker.time import local_date_for

FIXTURE_PATH = Path(__file__).resolve().parents[2] / "fixtures" / "day-boundary.json"
CASES = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))["cases"]


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["name"])
def test_local_date_matches_golden_fixture(case):
    instant = datetime.fromisoformat(case["instant"])
    assert local_date_for(instant, case["timezone"]) == case["expectedLocalDate"]
```

- [ ] **Step 6: 테스트가 실패하는지 확인**

```powershell
worker\.venv\Scripts\python.exe -m pytest worker -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'silen_worker.time'`

- [ ] **Step 7: 최소 구현 작성**

`worker/src/silen_worker/time.py`:

```python
"""사용자 로컬 자정 기준 '하루' 정의.

Next.js의 lib/time/day.ts와 동일한 계약을 따른다.
두 런타임이 코드를 공유할 수 없으므로 fixtures/day-boundary.json이
계약서 역할을 하며, 양쪽 테스트가 같은 파일을 읽는다.
"""

from datetime import datetime
from zoneinfo import ZoneInfo


def local_date_for(instant: datetime, time_zone: str) -> str:
    """UTC 시각과 IANA 타임존을 받아 YYYY-MM-DD 로컬 날짜를 반환한다."""
    return instant.astimezone(ZoneInfo(time_zone)).strftime("%Y-%m-%d")
```

- [ ] **Step 8: 테스트가 통과하는지 확인**

```powershell
worker\.venv\Scripts\python.exe -m pytest worker -v
```

Expected: PASS. `7 passed` — TS 쪽과 케이스 수가 같아야 한다.

- [ ] **Step 9: ruff 확인**

```powershell
worker\.venv\Scripts\python.exe -m ruff check worker
```

Expected: `All checks passed!`

- [ ] **Step 10: 커밋**

```powershell
git add worker
git commit -m "feat(worker): Python 워커 스캐폴딩과 하루 경계 구현

Next.js와 동일한 골든 픽스처를 읽어 두 자산의 날짜 경계가
어긋나지 않음을 테스트로 고정.
Windows에서 zoneinfo가 동작하도록 tzdata를 명시적 의존성으로 추가."
```

---

## Task 5: Supabase 로컬 스택 + 마이그레이션 재현성

**Files:**
- Create: `supabase/config.toml`(CLI 생성), `supabase/migrations/<timestamp>_enable_extensions.sql`, `supabase/migrations/down/<timestamp>_enable_extensions.down.sql`, `supabase/README.md`, `vitest.integration.config.ts`, `lib/repositories/db.integration.test.ts`
- Modify: `package.json` (scripts)

**Interfaces:**
- Consumes: 없음
- Produces: 로컬 DB 연결 문자열 `postgresql://postgres:postgres@127.0.0.1:54322/postgres`, npm 스크립트 `test:integration`

- [ ] **Step 1: Docker Desktop이 실행 중인지 확인**

```powershell
docker info
```

Expected: 서버 정보가 출력되고 종료 코드 0. 실패하면 Docker Desktop을 먼저 실행한다.

- [ ] **Step 2: Supabase 초기화 및 기동**

```powershell
npx supabase init
npx supabase start
```

Expected: 서비스 URL 목록 출력. `DB URL: postgresql://postgres:postgres@127.0.0.1:54322/postgres` 를 확인한다.

- [ ] **Step 3: 확장 마이그레이션 생성**

```powershell
npx supabase migration new enable_extensions
```

생성된 `supabase/migrations/<timestamp>_enable_extensions.sql`에 작성:

```sql
-- 실은: 벡터 검색(pgvector)과 공간 데이터(PostGIS) 확장
-- ADR-0002가 요구하는 임베딩 테이블의 전제 조건이다.
create extension if not exists vector;
create extension if not exists postgis;
```

- [ ] **Step 4: down 스크립트 작성**

`database.md`는 모든 마이그레이션에 down/보상 전략을 요구한다. Supabase CLI는 down 파일을 자동 실행하지 않으므로 **같은 타임스탬프 이름으로 짝을 맞춰** 보관한다.

`supabase/migrations/down/<timestamp>_enable_extensions.down.sql`:

```sql
-- 보상 전략: 확장에 의존하는 객체가 남아 있으면 실패한다(의도된 동작).
-- 강제 제거는 데이터 손실을 유발하므로 cascade를 쓰지 않는다.
drop extension if exists postgis;
drop extension if exists vector;
```

`supabase/README.md`:

```markdown
# Supabase 로컬

## 명령

- `npx supabase start` — 로컬 스택 기동 (Docker 필요)
- `npx supabase stop` — 중지
- `npx supabase migration new <name>` — 마이그레이션 생성
- `npx supabase db reset` — 초기화 후 마이그레이션 전체 재적용

## down 스크립트 규약

Supabase CLI에는 down 마이그레이션 개념이 없다. `database.md`가 요구하는
보상 전략은 `migrations/down/<같은-타임스탬프>_<같은-이름>.down.sql`로 보관한다.

- **자동 실행되지 않는다.** 롤백은 사람이 검토 후 실행한다.
- up 마이그레이션을 추가하면 down도 **같은 커밋에** 넣는다(git.md).
- 적용 전 staging에서 dry-run 한다. production 적용은 사람이 실행한다.
```

- [ ] **Step 5: 마이그레이션 재현성 확인**

```powershell
npx supabase db reset
```

Expected: `Applying migration <timestamp>_enable_extensions.sql...` 후 `Finished supabase db reset.` 종료 코드 0. **이 명령이 통과한다는 것은 마이그레이션이 빈 DB에서 처음부터 재생 가능하다는 뜻이다.**

- [ ] **Step 6: 통합 테스트 설정 추가**

```powershell
npm install -D pg @types/pg
```

`vitest.integration.config.ts`:

```ts
import { defineConfig } from "vitest/config";
import tsconfigPaths from "vite-tsconfig-paths";

export default defineConfig({
  plugins: [tsconfigPaths()],
  test: {
    environment: "node",
    include: ["**/*.integration.test.ts"],
    exclude: ["node_modules", ".next"],
    testTimeout: 30_000,
  },
});
```

`package.json`의 `scripts`에 추가:

```json
"test:integration": "vitest run --config vitest.integration.config.ts"
```

- [ ] **Step 7: 실패하는 통합 테스트 작성**

`lib/repositories/db.integration.test.ts`:

```ts
import { describe, it, expect, afterAll } from "vitest";
import { Client } from "pg";

const CONNECTION_STRING =
  process.env.SUPABASE_DB_URL ??
  "postgresql://postgres:postgres@127.0.0.1:54322/postgres";

const client = new Client({ connectionString: CONNECTION_STRING });
let connected = false;

async function getClient(): Promise<Client> {
  if (!connected) {
    await client.connect();
    connected = true;
  }
  return client;
}

afterAll(async () => {
  if (connected) await client.end();
});

describe("로컬 Supabase 스키마", () => {
  it("ADR-0002가 요구하는 확장이 설치되어 있다", async () => {
    const db = await getClient();
    const result = await db.query<{ extname: string }>(
      "select extname from pg_extension where extname in ('vector', 'postgis')",
    );
    const names = result.rows.map((row) => row.extname).sort();
    expect(names).toEqual(["postgis", "vector"]);
  });
});
```

- [ ] **Step 8: 통합 테스트 실행**

```powershell
npm run test:integration
```

Expected: PASS, `Tests 1 passed`.

스택이 안 떠 있으면 `ECONNREFUSED 127.0.0.1:54322`로 실패한다. 그때는 `npx supabase start`를 먼저 실행한다.

- [ ] **Step 9: 단위 테스트가 통합 테스트를 집어삼키지 않는지 확인**

```powershell
npm test
```

Expected: PASS, **`Tests 7 passed`** — 통합 테스트 1건은 포함되지 않아야 한다. Task 2에서 `vitest.config.ts`에 `**/*.integration.test.ts` 제외를 넣어둔 것이 여기서 효력을 발휘한다. 8건으로 나오면 그 제외가 빠진 것이므로 추가한다.

- [ ] **Step 10: 커밋**

```powershell
git add supabase vitest.integration.config.ts lib/repositories package.json package-lock.json
git commit -m "feat(db): Supabase 로컬 스택과 마이그레이션 재현성 확보

- pgvector·PostGIS 확장 마이그레이션 (ADR-0002의 전제)
- database.md의 down 요구를 migrations/down/ 규약으로 충족
- supabase db reset으로 빈 DB에서 재생 가능함을 확인
- 확장 설치를 검증하는 첫 통합 테스트. 단위와 러너를 분리"
```

---

## Task 6: Definition of Done 검사 묶기

`CLAUDE.md`의 완료 기준(lint + typecheck + unit + integration)을 한 번에 실행할 수 있게 만들고 README를 실제 상태로 갱신한다.

**Files:**
- Modify: `package.json` (scripts), `README.md`

**Interfaces:**
- Consumes: Task 1–5의 모든 스크립트
- Produces: `npm run check` — TS 자산의 lint·typecheck·unit을 순차 실행

- [ ] **Step 1: 통합 스크립트 추가**

`package.json`의 `scripts`:

```json
"lint": "eslint .",
"typecheck": "tsc --noEmit",
"test": "vitest run",
"test:integration": "vitest run --config vitest.integration.config.ts",
"check": "npm run lint && npm run typecheck && npm run test"
```

워커는 가상환경 경로가 OS마다 달라 npm 스크립트로 묶지 않는다. README에 명령을 따로 적는다.

- [ ] **Step 2: 전체 검사 실행**

```powershell
npm run check
worker\.venv\Scripts\python.exe -m ruff check worker
worker\.venv\Scripts\python.exe -m pytest worker
```

Expected: 세 명령 모두 종료 코드 0.

- [ ] **Step 3: README 갱신**

`README.md`의 `### 2. 앱 스캐폴딩 (아직 미생성)` 절 전체를 아래로 교체한다:

```markdown
### 2. 로컬 개발

전제: Node 20+, Python 3.11+, Docker Desktop.

```powershell
# 앱 (저장소 루트)
npm install

# Python 워커
python -m venv worker\.venv
worker\.venv\Scripts\python.exe -m pip install -e "worker[dev]"

# 로컬 DB (Supabase 스택 — Docker 필요)
npx supabase start
npx supabase db reset
```

### 3. 검사

```powershell
npm run check              # lint + typecheck + unit
npm run test:integration   # 통합 (Supabase 스택 기동 필요)
worker\.venv\Scripts\python.exe -m ruff check worker
worker\.venv\Scripts\python.exe -m pytest worker
```
```

`README.md`의 저장소 구조 블록에도 실제 디렉터리를 반영한다:

```
app/                    # 경계 계층 (Route Handler·페이지)
lib/time/               # "하루" 경계 단일 유틸
lib/services/           # 서비스 계층
lib/repositories/       # 저장소 계층
components/ui|common/   # 공통 컴포넌트 (frontend.md)
worker/                 # Python 워커 (차이 탐지·AI 잡)
fixtures/               # 두 자산이 공유하는 골든 케이스
supabase/migrations/    # 마이그레이션 (down/ 에 보상 스크립트)
docs/superpowers/       # 스펙·계획
```

- [ ] **Step 4: 커밋**

```powershell
git add package.json README.md
git commit -m "chore: Definition of Done 검사 묶기와 README 갱신

npm run check로 lint+typecheck+unit을 한 번에 실행.
워커는 가상환경 경로가 OS마다 달라 별도 명령으로 문서화.
README의 '앱 스캐폴딩 (아직 미생성)'을 실제 상태로 교체."
```

- [ ] **Step 5: 브랜치 마무리**

`/superpowers:finishing-a-development-branch`로 병합 방식을 결정한다. `git.md`에 따라 **rebase 후 `merge --no-ff`**, squash는 쓰지 않는다.

---

## 완료 기준

- `npm run check` 통과
- `npm run test:integration` 통과 (Supabase 스택 기동 상태)
- `ruff check worker` · `pytest worker` 통과
- `npx supabase db reset` 이 빈 DB에서 재생 성공
- 계층 위반 프로브가 lint 에러를 발생시킴 (Task 3 Step 4에서 확인)

## 후속 계획(C)로 넘기는 것

- ADR-0002 실제 스키마 마이그레이션(조인 테이블·임베딩 3종·`deletions`·트리거)
- 큐 배선과 잡 상태 관리
- Supabase Auth 연동과 RLS 정책
- 임베딩 차원 `N`·모델 확정
