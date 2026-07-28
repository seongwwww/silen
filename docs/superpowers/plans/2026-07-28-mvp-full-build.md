# 실은 MVP 제품 표면 구현 — 마스터 계획 v2

설계 근거: `docs/superpowers/specs/2026-07-28-mvp-full-design.md`
화면 원본: `docs/design/wireframes.html` (7화면)

> **상태:** 설계 승인 전. 승인 뒤 Phase -1→6 순서로 진행한다.

이 계획은 와이어프레임 7화면과 핵심 탐지 루프를 완성한다. 야간 스케줄러·잡 상태·
알림·PWA·계정 연결은 설계 문서 §10의 **베타 운영 게이트**이며, 이 계획이 끝나도
자동 운영까지 완료됐다고 보고하지 않는다.

Phase는 의존 순서이지만 **하나의 장기 브랜치에 전부 넣지 않는다.** 각 Phase를
짧은 브랜치로 구현·검증·리뷰·병합한 뒤 다음 Phase를 시작한다.

---

## 시작 전 필독

1. `AGENTS.md` — **Next.js 16이다.** 앱 코드 작성 전 `node_modules/next/dist/docs/`의
   해당 문서를 먼저 읽어라. 학습 데이터와 API가 다르다.
2. `CLAUDE.md` + `.claude/rules/*.md` 전부
3. 위 설계 문서

## 검토로 확정한 경계

이미 확정된 사항이다. 다르게 보이더라도 **이 목록이 이긴다.**

- 감정 차이의 멱등성을 위한 **부분 유니크 인덱스**(Phase 2)와 안전한 삭제 요청을
  위한 **security definer RPC**(Phase 6)를 각각 up/down 마이그레이션으로 만든다.
  그 밖의 스키마 변경은 새 설계 승인을 받는다.
- **연속(streak)은 매일 카드에서 뺀다.** 주간 리포트로 간다.
- **일기는 `status != 'dismissed'`를 쓴다.** `confirmed`만 쓰던 조건을 바꾼다.
- **사진·음성·위치 입력 버튼, 걸음·방문장소 동의 토글을 만들지 마라.**
  동작하는 전체 경로가 없어 거짓 약속이 된다.
- **회고는 키워드 검색이다.** 임베딩·pgvector를 도입하지 마라.
- 진행률 바·카운트다운·"N일 남았어요"·스트릭 **금지**(죄책감 유도).
- "부재"는 생활 부재가 아니라 **기록 부재**다. 빈 날에는 만들지 않고,
  UI·LLM은 언제나 "기록에서/언급이"라는 범위를 드러낸다.
- `first_occurrence`는 저장하되 매일 카드 랭킹과 서술 호출에서만 제외한다.
- 계획의 예시 코드와 `.claude/rules/`가 어긋나면 **규칙이 이긴다.**

## 매 태스크 공통 절차

```
실패 테스트 → 최소 구현 → 리팩터 → 검사 → 커밋
```

**검사 (앱 변경 시):**
```powershell
npm run check      # lint + typecheck + unit
npm run build      # ★ 반드시. Supabase select 타입 추론 오류는 이것만 잡는다
```

**검사 (워커 변경 시):**
```powershell
worker\.venv\Scripts\python.exe -m ruff check worker
worker\.venv\Scripts\python.exe -m pytest worker -m "not integration"
```

**통합 테스트를 생략한 Phase는 완료가 아니다.** 먼저 기존
`docs/superpowers/plans/2026-07-28-test-isolation.md`를 완료해 전역 사용자 삭제와
큐 purge를 제거한다. 그 뒤 각 Phase의 대상 통합 테스트와 마지막 전체 통합 테스트를
실행한다. 삭제 API의 파괴 테스트만 사람이 명시적으로 실행한다.

**커밋:** `<type>(<scope>): <한국어 요약>` · 본문은 무엇을·왜 · 마침표 없음.
`Co-Authored-By`는 네 것으로. **사용자 기록 본문을 커밋 메시지에 넣지 마라.**

## 브랜치와 게이트

| 순서 | 브랜치 | 범위 |
|---|---|---|
| -1 | `fix/test-isolation` | 안전한 통합 테스트 선행 |
| 0~1 | `feat/mvp-shell` | 언어·토큰·탭바·기록·홈 |
| 2 | `feat/detector-v2` | 놀라움·기록 부재·감정·멱등 인덱스 |
| 3 | `feat/diary-optout` | opt-out·일회성 톤 주문 |
| 4 | `feat/weekly-report` | rolling 7일 집계·화면 |
| 5 | `feat/recall-search` | 키워드 회고 |
| 6 | `feat/data-controls` | 내보내기·삭제·stats |

각 브랜치는 `main`에서 만들고, 리뷰 후 `merge --no-ff`가 끝나야 다음 브랜치를
시작한다. 커밋·push·병합은 사람이 요청할 때만 한다.

## 막히면

**추측해서 진행하지 말고 멈추고 보고해라.** 특히:
- 스키마 변경이 필요해 보일 때
- 계획과 실제 코드가 다를 때
- 테스트가 예상과 다르게 실패할 때

---

# Phase -1 — 통합 테스트 격리

**먼저 실행할 계획:** `docs/superpowers/plans/2026-07-28-test-isolation.md`.

완료 기준:
- 전역 `listUsers → deleteUser`와 `pgmq.purge_queue`가 테스트에서 사라진다
- 테스트는 자기가 만든 사용자·메시지만 정리하고 단언한다
- 프론트·워커 전체 통합 테스트가 기존 개발 데이터를 건드리지 않고 통과한다

이 단계 전에는 Phase 0 코드를 시작하지 않는다. 전체 기능을 만들고도 DoD를
증명하지 못하는 상태를 피하기 위한 선행 조건이다.

---

# Phase 0 — 바닥

## T0.1 언어·타이포·색 토큰

**목적:** 한국어 제품인데 `lang="en"`이다. 그리고 와이어프레임의 따뜻한 베이지가
구현에 하나도 반영돼 있지 않다(기본 회색 shadcn).

- `app/layout.tsx:28` — `lang="en"` → **`lang="ko"`**
- `app/globals.css` — 토큰 추가. 다크 모드도 대응한다.
  - 배경 `#faf7f2` · 강조 카드 `#f5ede0` · 테두리 `#e8dcc8`
  - 기존 shadcn CSS 변수(`--background`·`--card`·`--border`·`--accent`)에 얹는다.
    **새 변수 체계를 만들지 마라.**
- 한국어 줄바꿈 — `body`에 `word-break: keep-all; overflow-wrap: break-word`

**검증:** `npm run build` 통과. 홈이 베이지 배경으로 보인다.
**커밋:** `fix(ui): 문서 언어를 한국어로 바로잡고 베이지 토큰 도입`

## T0.2 하단 탭바

**목적:** 지금 화면 간 이동 수단이 없다. 와이어프레임 4탭.

- `components/common/TabBar.tsx` — 클라이언트 컴포넌트(`usePathname`으로 활성 표시)
- 이 Phase의 탭: **오늘 `/`** · **일기 `/diary`** · **설정 `/settings`**
- `/recall`이 실제로 구현되는 T5.2에서 네 번째 **회고 탭**을 추가한다.
- 아이콘은 와이어프레임 기호(`◉ ✎ ⌕ ☰`)를 그대로 쓰거나 lucide 동등물
- `position: fixed; bottom: 0`, 높이 56px, **각 탭 터치 타깃 44px 이상**
- 활성 탭은 **색 + 굵기 둘 다**로 구분(색만으로 의미 전달 금지)
- `aria-current="page"` 부여
- `app/layout.tsx`에 배치. `<body>`에 `padding-bottom`으로 콘텐츠 가림 방지

존재하지 않는 라우트를 탭에 미리 노출하지 않는다. "동작하지 않는 것은 그리지
않는다"는 설계 원칙과 404 없는 내비게이션을 함께 지킨다.

**테스트:** `TabBar.test.tsx` — 3개 렌더, 현재 경로에 `aria-current`.
**커밋:** `feat(ui): 하단 탭바 추가`

---

# Phase 1 — 홈을 발견 화면으로

와이어프레임 #1. **지금 홈은 기록 폼이다.** 기획서의 "홈 = 발견 우선"과 정반대다.

## T1.1 기록 화면 분리

- `app/record/page.tsx` 신설 — 지금 `app/page.tsx`의 `RecordForm`을 옮긴다
- `app/_components/RecordForm.tsx` → `app/record/_components/`로 이동
  (기존 테스트도 함께 이동. **테스트 내용은 바꾸지 마라.**)
- 홈의 `?section=` 꼬리질문 처리도 `/record`로 옮긴다.
  **`FollowUpCard`가 링크하는 경로를 함께 고쳐라** — 안 고치면 꼬리질문이 끊긴다.
- 제목 "뭐든 남겨요" / 부제 "분류도 태그도 필요 없어요"
- 저장 성공 시 **`/`로 돌아간다**
- 현재 폼의 텍스트·감정만 옮긴다. **사진·음성·위치 버튼은 만들지 마라.**

**검증:** `npm run check` + `npm run build`. 기존 RecordForm 테스트 전부 통과.
**커밋:** `refactor(ui): 기록 폼을 /record로 분리`

## T1.2 오늘 화면

`app/page.tsx`를 새로 쓴다. 위에서부터:

1. **제목** "오늘" + 부제 `7월 22일 화요일` (사용자 타임존 기준 — `lib/time` 사용)
2. **오늘의 다른 점** — 차이 카드(강조 배경). 없으면 이 카드 자체를 숨긴다
   - 카드마다 서술 문장 + **[맞아요] [아니에요]**(`ConfirmActions` 재사용)
   - 관측 3일 미만이면 대신 **"아직 평소를 익히는 중이에요"** 한 줄
   - **진행률·남은 일수를 표시하지 마라**
3. **오늘의 메모 · N개** — 개수와 **첫 20자 미리보기**. 0건이면 "오늘은 아직 조용하네요"
4. **일기 상태 카드** — 설계 §6 표 그대로
5. **`+ 지금 남기기`** — `/record`로 가는 큰 버튼

**서비스:** `lib/services/today.ts` — `buildTodayView()`.
프레임워크 타입을 몰라야 한다(`no-restricted-imports`가 막는다).
필요한 조회는 저장소 인터페이스로 주입받는다.

**저장소:** 기존 `memoryRepository`·`differenceRepository`·`diaryRepository`를 쓴다.
새 메서드가 필요하면 거기 추가해라. **새 파일을 만들지 마라** —
`eslint.config.mjs`의 `except` 목록이 또 늘어난다.

`components/common/StateView.tsx`에 빠진 `ProcessingState`·`OfflineState`를 먼저
추가해 상태 5종을 공통으로 만든다: empty / loading / processing / error / offline.
단, 저장된 잡 상태가 없으므로 processing은 "메모는 있으나 일기는 아직 없음"만
뜻한다. 실패했다고 추측하는 문구는 쓰지 않는다.

**테스트:** `lib/services/today.test.ts` — 메모 0건 / 차이 0건 / 관측 3일 미만 /
일기 상태별. **저장소는 스텁으로.**

**검증:** `npm run check` + `npm run build`
**커밋:** `feat(ui): 홈을 발견 우선 오늘 화면으로 재구성`

---

# Phase 2 — 탐지 재설계 (워커)

**여기가 이 작업의 핵심이다.** 순수 파이썬이라 TDD가 가장 쉽다. 테스트를 두껍게 써라.

현재 `worker/src/silen_worker/detection/service.py`는:
- 오늘 등장한 엔티티만 본다 → **부재를 영원히 못 찾는다**
- `FIRST_OCCURRENCE_CONFIDENCE = 1.0` 고정 → **전부 동점이라 순위가 없다**

## T2.1 놀라움 계산 (순수 함수)

`worker/src/silen_worker/detection/surprisal.py` 신설.

```
active_history    = target 이전 28일 중 활성 메모가 있는 날짜 집합
n                 = len(active_history)
k                 = 그중 해당 엔티티가 언급된 날짜 수
p                 = (k + 0.5) / (n + 1)
bits_present(p)   = -log2(p)
bits_absent(p)    = -log2(1 - p)
```

오늘 날짜는 확률 추정에서 제외한다. 달력 경과일이 아니라 **활성 기록일**을
분모로 써서 기록하지 않은 날을 생활 부재로 오인하지 않는다.

**테스트(필수):**
- 과거 활성일마다 등장한 것이 오늘도 등장 → 낮은 bits
- 과거 활성일마다 등장한 것이 오늘 활성 기록에 없음 → 높은 bits
- 한 번도 없던 것이 오늘 등장 → 높음
- `seen_days == n` 이어도 **무한대·0으로 나누기가 없다**(평활 확인)
- `n == 0` 방어

**커밋:** `feat(detector): 놀라움(bits) 계산 도입`

## T2.2 탐지 규칙 교체 — 부재 포함

`detection/service.py`의 `detect_differences`를 다시 쓴다.

- **창 안 모든 엔티티를 순회한다.** `if target_date not in w.dates: continue`를 **제거**
- 분류:

| 조건 | method | description(통계 근거) |
|---|---|---|
| 이력 없음 + 오늘 등장 | `first_occurrence` | `처음 등장` |
| 이력 있음 + 오늘 활성 기록에 **언급 없음** + 과거 활성일 2회 이상 | `freq_shift` | `과거 활성일 {n}일 중 {k}일 기록됨, 오늘 기록에는 언급 없음, 마지막 {g}일 전` |
| 이력 있음 + 오늘 등장 + 공백 ≥ `REEMERGENCE_GAP_MIN` | `freq_shift` | `{gap}일 만에 재등장(최근 {n}일 중 {k}일)` |

- **연속(streak) 분기를 매일 탐지에서 제거한다.** 주간(T4.1)으로 옮긴다.
  기존 streak 테스트는 **삭제하지 말고** 주간 쪽으로 옮겨라.
- `confidence`에 **bits를 그대로** 넣는다
- `description`은 사람에게 직접 노출되지 않지만 **LLM 입력이다.**
  영문 enum·변수명을 넣지 마라. 한국어 통계 문장으로.
- 오늘 메모가 0건이면 즉시 빈 결과를 반환한다.
- 기록 부재의 evidence는 과거 해당 엔티티 메모와 오늘의 전체 활성 메모를 연결한다.
  현재의 `today_entities[entity_id]["today"]`만 연결하는 방식으로는 부재 근거가
  0개가 되므로 DB 조회 결과에 과거·오늘 memory ID를 함께 보존한다.

**테스트(필수):**
- 매일 기록되던 엔티티가 오늘 활성 기록에 없음 → **`freq_shift` 1건**
- 창 안 1회만 등장한 것이 오늘 없음 → **0건**(추정 불가)
- 산발적 등장 → 0건
- 오늘 메모가 없는 빈 날 → 0건 (**억지 생성 금지 — 반드시 유지**)
- 매일 나오는 것이 오늘도 나옴 → 낮은 bits

**커밋:** `feat(detector): 부재를 탐지하고 놀라움으로 순위를 매긴다`

## T2.3 감정축

`worker/src/silen_worker/detection/emotion.py` 신설 — **순수 함수.**

- 입력: `[(local_date, valence)]` 목록 + target_date
- 일자별 평균 valence → baseline 평균·표준편차
- `sd_eff = max(sd, 0.25)`, `z = (v_today - mu) / sd_eff`
- `p = 2 * (1 - Φ(|z|))`,
  `bits = -log2(max(p, 2 ** -8))` (Φ는 `statistics.NormalDist().cdf`)
- 과거 **감정 활성일이 5일 미만이면 결과 없음**
- bits는 최대 8.0으로 제한한다
- 같은 방향 연속은 매일 신호로 만들지 않고 T4.1 주간 집계로 넘긴다
- 출력 `method='zscore'`, `category='감정전환'`
- description 예:
  - `최근 {n}일 평균 {mu:.2f}, 오늘 {v:.2f} (z={z:.1f})`

**DB:** `worker/src/silen_worker/db.py`에 `fetch_window_emotions()` 추가.
`emotions` ⋈ `memories` 조인, **`user_id` 필터 필수**, `deleted_at is null`,
`is_locked = false`. 워커는 RLS를 우회하므로 **이 필터가 유일한 격리 방어선이다.**

**테스트(필수):**
- 평탄한 감정 → 0건
- 오늘만 뚝 떨어짐 → 1건, bits 높음
- 과거 감정 기록일 4일 → 0건
- `sd == 0`이어도 0으로 나누지 않고 실제 변화는 탐지
- 평탄한 감정 + 같은 오늘 값 → 0건

**멱등 마이그레이션:** 감정 차이는 `entity_id is null`이라 현재
`differences_entity_natural_key`의 보호를 받지 않는다. 아래 인덱스를 새
up/down 마이그레이션으로 추가한다.

```sql
create unique index differences_dimension_natural_key
  on public.differences (user_id, date, dimension, detection_method)
  where entity_id is null;
```

감정 upsert는 `(user_id, date, dimension='emotion', detection_method='zscore')`
자연키를 사용한다. `upsert_dimension_difference()`를 별도로 두어
`entity_id=null`, `category='감정전환'`을 명시하고, 오늘과 baseline에 쓴 감정
메모 ID를 evidence로 연결한다. 엔티티 전용 `upsert_difference()`의 타입과
하드코딩 category를 억지로 재사용하지 않는다.

**커밋:** `feat(detector): 감정축 탐지 추가`

## T2.4 랭킹 · 상한 · 기각 학습 · 콜드스타트

`detection/service.py`에 `rank_differences()` 추가 — **순수 함수.**

순서대로:
1. `first_occurrence`는 **저장하되 랭킹·서술 대상에서 제외**한다
   ("오늘 처음" 목록과 주간 리포트가 소비)
2. `bits < 2.0` 버린다
3. `표시점수 = bits / (1 + 최근 28일 같은 entity+method 기각횟수)`,
   **최근 28일 기각 3회 이상이면 제외**
4. 내림차순 정렬 → **상위 3개**
5. **과거 활성일 < 2이면 전부 버린다**(세 번째 활성일부터 가능)

- 임계값·상한은 전부 `detection/constants.py`에. **매직 넘버 금지.**
- 기각 횟수는 `db.py`에
  `fetch_dismiss_counts(user_id, entity_ids, methods, since_date)`를 추가한다
  (`status='dismissed'`, 최근 28일, **user_id 필터 필수**)

**테스트(필수):**
- 4건 들어오면 3건만 나온다
- 1.9 bits는 탈락, 2.1은 통과
- 기각 2회면 점수 1/3, 3회면 제외
- 과거 활성일 1일이면 0건, 2일이면 임계값에 따라 판정
- `first_occurrence`는 절대 랭킹에 안 들어간다

**연결:** `tasks/detect.py`는 먼저 `first_occurrence`를 저장해 일기·주간 근거를
보존한다. 나머지 엔티티·감정 후보를 합쳐 랭킹한 뒤 상위 3개만 카드/서술 대상으로
반환한다. 엔티티 차이는 기존 부분 유니크 인덱스, 감정 차이는 T2.3의 새 부분
유니크 인덱스로 멱등을 보장한다.

**커밋:** `feat(detector): 랭킹·상한·기각 학습·콜드스타트 게이트`

## T2.5 서술에 비교 수치

`worker/src/silen_worker/narration/` — 프롬프트가 통계 근거를 **문장에 녹이도록** 한다.

- 지금: *"김밥이 다시 나왔어요"*
- 바꾼 뒤: *"김밥이 사흘 만에 다시 나왔어요. 최근 4주엔 주 한 번꼴이었는데요."*

- 기록 부재 서술 톤: *"앞선 두 기록일에 있던 운동 얘기가 오늘 기록에는
  없었어요."* — **생활 부재로 승격·원인·평가·권유 금지.**
  *"괜찮으세요?"* · *"다시 시작해보는 건"* 은 절대 금지
- 감정 서술: *"최근 감정 기록 평균보다 오늘 값이 낮았어요."* —
  **입력 수치만.** 위로·해석 금지
- **기존 가드레일(엔티티명 정합·조언/인과 블록리스트·길이)은 그대로 통과해야 한다**
- 감정 차이는 `entity_id`가 없으므로
  `fetch_difference_for_narration()`의 엔티티 inner join을 left join으로 바꾸고,
  엔티티명 정합 가드레일은 엔티티 차이에만 적용한다. 대신 감정 차이는
  `dimension='emotion'`, 수치 description, evidence ID 정합을 검증한다.
- `fetch_confirmed_differences()`도 left join과 nullable 엔티티 타입을 지원해
  감정 차이가 일기 소비 경로에서 조용히 누락되지 않게 한다.
- `NarrationInput.entity_name/entity_type`과 `DiaryDifference.entity_name`을
  nullable로 바꾸고, 프롬프트·가드레일의 "엔티티 이름 필수"는 값이 있을 때만
  적용한다. 감정 프롬프트에는 엔티티 표현 대신 `차원: 감정 기록`을 넣는다.
- 일기 본문 소비 대상은 `freq_shift`와 `zscore`다. 질문 대상 선택은 기존처럼
  엔티티가 있는 `first_occurrence`만 허용해 감정 차이가 질문 생성기를 깨지 않게 한다.

**eval:** `evals/narration/`에 케이스 추가 — 부재 서술 1건, 감정 서술 1건.
기대 속성: 조언 0 · 인과 0 · 수치가 입력 통계와 일치.

**eval 실행은 실제 Vertex 호출이라 비용이 든다.** 케이스를 추가하고 사람의
실행 승인을 받아 1회 실행한다. eval 미실행 상태를 Phase 완료로 표시하지 않는다.

**커밋:** `feat(narration): 서술에 비교 수치를 넣는다`

---

# Phase 3 — 일기 opt-out · 톤 주문

## T3.1 확인을 관문에서 내린다

- 일기 생성이 쓰는 차이 조건을 **`status = 'confirmed'` → `status <> 'dismissed'`**
  (`worker/src/silen_worker/diary/` 및 대응 db 쿼리)
- `fetch_confirmed_differences`는 의미가 달라지므로
  `fetch_usable_differences`로 이름을 바꾸고 모든 호출·테스트를 함께 갱신한다.
- 후보 차이 문장은 생활 사실이 아니라 **기록 범위의 사실**로만 들어간다.
  기록 범위 가드레일을 통과하지 못하면 status와 무관하게 제외한다.
- `README.md`·`supabase/README.md`의 "사람이 확정한 차이만 녹인다" 서술을 고쳐라
- **run-daily → 확인 → run-diary 순서 강제가 사라진다.** README §4 설명 갱신

**테스트:** candidate 차이가 일기에 반영된다 / dismissed는 안 된다.
**커밋:** `feat(diary): 확인을 관문에서 내리고 기각만 반영한다`

## T3.2 기본 프리셋 + 1회 빠른/자유 주문

와이어프레임 #3. 지금은 설정의 기본 톤만 있다.

- **담백 · 따뜻**은 사용자 기본 프리셋으로 유지한다.
- **짧게 · 유머**는 프리셋을 늘리는 것이 아니라 이번 일기에만 적용되는
  `tone_instruction` 빠른 주문이다.
- 그 아래 **자유 주문 입력**(기존 재생성 요청 경로 재사용)
- `POST /api/diaries/[id]/regenerate`가 선택적
  `{ toneInstruction: string | null }` body를 검증해 저장하도록 확장한다.
- 빠른 주문이나 자유 주문은 **즉시 생성하지 않는다.** 재생성 요청과 함께
  1회 주문을 남기고 *"다음 생성 때 반영돼요"*를 표시한다.
- 터치 타깃 44px 이상, 선택 상태를 **색 + 라벨** 둘 다로

**주의:** 톤은 **문체만** 바꾼다. 사실 집합은 불변이다(`ai-evals.md`).
프롬프트에 톤을 넣되 **사실 가드레일은 그대로 적용**돼야 한다.
`유머` 요청은 특히 사실 추가 위험이 있으므로 담백/유머 사실 불변성 eval을
추가하고 통과하지 못하면 유머 칩만 범위에서 뺀다.

**커밋:** `feat(diary): 톤 칩과 자유 주문 추가`

---

# Phase 4 — 주간 리포트

와이어프레임 #5. 테이블 `weekly_reports`·`weekly_report_highlights`가 **이미 있다.**

## T4.1 주간 집계 (순수 함수)

`worker/src/silen_worker/weekly/service.py` 신설.

사용자의 첫 메모 로컬 날짜를 anchor로 삼아 7일 블록을 만든다. 첫 보상은
달력의 일요일이 아니라 **첫 기록 후 7일이 지난 시점**에 열린다. 이후에도 같은
anchor의 7일 블록 단위로 생성한다.

7일 창에서 슬롯 3개를 채운다 — `slot` 값은 스키마 check 제약 그대로:

| slot | 무엇 |
|---|---|
| `가장많이한것` | 창 안 최다 등장 엔티티 + 횟수. **연속(streak)이 여기로 온다** |
| `처음한것` | 그 주의 `first_occurrence` |
| `감정순간` | 감정 z가 가장 큰 날 |

- 첫 메모 이후 7일이 아직 지나지 않았으면 리포트를 만들지 않는다
- 빈 주(메모 0)는 만들지 않는다
- 슬롯이 하나도 안 차면 만들지 않는다
- `weekly_report_highlights`는 `difference_id`가 필수다. 최다 빈도는
  `detection_method='pattern'` 엔티티 difference를 만들고, 감정 순간은 기존
  또는 새 `zscore` difference를 만든다. `처음한것`은 저장돼 있던
  `first_occurrence`를 참조한다.
- 주간 pattern difference는 `category='패턴'`으로 저장한다. 기존
  `upsert_difference()`가 `category='오늘의다른점'`을 하드코딩하므로 category를
  인자로 받도록 확장하고 기존 호출의 기본 동작을 회귀 테스트로 보존한다.
- 새 pattern/zscore difference에는 해당 7일 메모 evidence를 연결한다.
- 동률은 횟수 → normalized name → entity id 순으로 고정해 재실행 결과를 같게 한다.

**테스트:** 빈 주 0건 / anchor 후 6일차 0건 / 7일 블록 완료 뒤 생성 /
활성일이 7일보다 적어도 있는 기록만으로 생성 / 슬롯별 / 동률 결정성.
**커밋:** `feat(weekly): 주간 집계 로직`

## T4.2 저장 · CLI

- `worker/src/silen_worker/tasks/write_weekly.py`
- `weekly_reports` **`unique (user_id, week)` upsert로 멱등**
- `week`는 사용자 anchor 기준 7일 블록의 시작 로컬 날짜(`2026-07-21`)다.
- Python에서는 `silen_worker.time`과 공용 day-boundary fixture를 쓴다.
  TypeScript의 `lib/time`을 직접 참조할 수 없다.
- CLI `run-weekly` 추가. 기본 대상: 전체 사용자 중 각자 로컬 기준으로
  방금 완료된 7일 블록이 있는 사용자
- **재실행이 중복 행을 만들지 않아야 한다**
- `README.md` §4에 명령·스케줄 예시 추가

**커밋:** `feat(weekly): 리포트 저장과 run-weekly 명령`

## T4.3 리포트 화면

`app/report/page.tsx`.

- 제목 "당신이 몰랐던 이번 주"
- **7일 막대** — 날짜별 메모 수. 놀라움이 큰 날을 강조색으로
- 슬롯 카드 3개
- 하단 **"이번 주 기록에서 찾은 모습이에요"**
- 리포트 없으면: **"아직 묶을 7일 기록이 없어요"** — 남은 일수·압박 문구 금지
- **공유 카드 버튼은 만들지 마라**

**진입:** 일기 화면 상단 링크. 탭을 늘리지 마라(4개 유지).

**저장소:** `lib/repositories/weeklyRepository.ts` 신설.
**`eslint.config.mjs`의 `except` 목록에 추가해야 할 수 있다.**
추가하게 되면 주석의 경고대로 **"목록을 늘릴지 기준을 다시 세울지" 판단해서 보고해라.**
목록이 6개가 되면 기준을 다시 세울 때다.

**커밋:** `feat(ui): 주간 리포트 화면`

---

# Phase 5 — 회고 (키워드 검색)

와이어프레임 #6. **벡터가 아니라 키워드다.**

## T5.1 검색

- `lib/services/recall.ts` + `memoryRepository`에 `search()` 추가
- PostgreSQL `ILIKE` 또는 `to_tsvector`. **인덱스 추가는 마이그레이션이므로 하지 마라.**
  메모 수백 건에서 순차 스캔으로 충분하다
- 질의는 trim 후 1~100자. `ILIKE`를 쓰면 `%`·`_`를 리터럴로 escape해
  사용자가 빈 패턴으로 전체 기록을 우연히 조회하지 않게 한다
- **`user_id` 필터 필수** · `deleted_at is null` · **`is_locked = false`**
  (잠근 기억은 검색에서 빠진다 — `privacy.md`)
- 결과: 날짜 + 본문 발췌. **최신순, 상한 20건**

**테스트:** 빈 질의 / 결과 없음 / 잠근 메모 제외 / 삭제 메모 제외.
**커밋:** `feat(recall): 기록 키워드 검색`

## T5.2 회고 화면

`app/recall/page.tsx`.

- 제목 "그거 뭐였지" / 부제 "기록에게 물어보세요"
- 검색창
- 결과 = **근거 카드 목록** — `7.14` 같은 날짜 태그 + 발췌
- **LLM 요약 문장을 만들지 마라.** 이번 범위는 검색이다.
  *"작년 7월엔 이직을 두고 고민했었어요"* 같은 요약은 RAG가 생긴 뒤
- 결과 없음: "그런 기록은 아직 없어요"
- 상태 5종 구현
- `TabBar`에 네 번째 **회고 `/recall`** 탭을 이 시점에 추가하고 4탭 테스트로 갱신
- 본인 데이터 검색이므로 교차 사용자 결과가 0건임을 통합 테스트하고 보안 리뷰

**커밋:** `feat(ui): 회고 검색 화면`

---

# Phase 6 — 설정 · 데이터

와이어프레임 #7. **동작하는 것만 그린다.**

## T6.1 내보내기

- `app/api/export/route.ts` — 본인 **기록 JSON** 다운로드
- 포함: memories · emotions · asset metadata · entities · differences+narrations ·
  diaries+sections · weekly reports
- **`user_id` 스코프 강제**
- 응답 `Content-Disposition: attachment` · `Cache-Control: no-store`
- **본문을 로그에 남기지 마라**(`backend.md`)
- 사진 바이너리는 이 JSON에 들어가지 않으므로 UI도 "전체 백업"이 아니라
  **"기록 JSON 내보내기"**라고 정확히 쓴다

**커밋:** `feat(settings): 내 데이터 내보내기`

## T6.2 전체 삭제

- `app/api/account/data/route.ts` DELETE는 직접 테이블을 지우지 않고
  **삭제 원장 요청만 생성**한다.
- `deletions`는 authenticated INSERT가 RLS로 차단돼 있다. 앱에 service role을
  넣지 말고 `auth.uid()`만 사용하는 `security definer`
  `request_account_data_deletion()` RPC를 up/down 마이그레이션으로 추가한다.
- 계정 삭제 요청의 `target_id`는 NULL이 아니라 **user_id**로 넣는다. 현재 부분
  유니크 인덱스는 NULL끼리 중복을 막지 못하므로, 그래야 이중 클릭이 멱등하다.
- `worker/src/silen_worker/tasks/delete_data.py`가 `running/failed` 원장을 읽어
  아래 단계를 재개 가능하게 처리한다.
  1. Storage `memories/{user_id}/` 객체 삭제
  2. weekly_reports → diaries → differences → entities/signals/baselines/consents →
     memories 순으로 본인 행 삭제
  3. DB·Storage 잔존 검증
  4. `completed` 기록
- Storage 삭제는 `storage.objects` SQL 삭제로 대체하지 않는다. Python 워커에
  `StorageDeletionPort`를 두고 프로덕션 어댑터가 Supabase Storage API를
  worker-only service-role 자격으로 호출한다. 단위 테스트는 스텁 포트를 쓰고,
  자격 증명·객체 경로를 로그에 남기지 않는다.
- `public.users`와 `auth.users`는 지우지 않는다. 이 기능은 **계정 탈퇴가 아니라
  모든 기록 데이터 삭제**이며, 사용자는 빈 계정으로 다시 기록할 수 있다.
- 단계별 완료를 `steps_done`에 기록하고 실패 시 `last_error`에는 본문·경로가
  아닌 오류 코드만 남긴다.
- UI: **두 단계 확인.** 무엇이 지워지는지 구체적으로 —
  *"원본 기록·사진·일기·차이·주간 리포트가 삭제됩니다. 계정은 유지되며,
  삭제한 기록은 되돌릴 수 없습니다."*

**⚠️ 이건 파괴적 동작이다.** 격리된 fixture를 쓰는 통합 테스트와 보안 리뷰를
작성하되 실행은 사람이 승인한다. 승인된 삭제 통합 테스트와 잔존 검증이 통과하기
전에는 Phase 6과 MVP를 완료로 표시하지 않는다.

**커밋:** `feat(settings): 전체 삭제`

## T6.3 stats 명령

CLI `stats` 추가 — 설계 §7의 4지표를 출력한다.

```
명시적 긍정 비율 82%  (confirmed 41 / dismissed 9)
하루 평균 차이   2.1건
일기 확정률      64%
관측일수 분포    3일+ 4명 · 7일+ 2명
```

**읽기 전용이어야 한다.** 아무것도 쓰지 마라. opt-out에서 이 값은 노출 대비
정확도가 아니라 명시적 피드백 중 긍정 비율임을 출력 설명에도 적는다.

**커밋:** `feat(worker): stats 명령`

---

# 마지막

## 문서 갱신

- `README.md` — 저장소 구조에 새 라우트(`/record`·`/report`·`/recall`),
  §4에 `run-weekly`·`stats`, 파이프라인 순서 변경(T3.1) 반영
- `supabase/README.md` — 탐지 절을 놀라움·부재·감정축으로, 일기 절의
  "확정한 차이만" 서술을 고침
- `PROJECT_STATE.md` — 완료 항목 갱신

## 최종 검사

```powershell
npm run check
npm run build
worker\.venv\Scripts\python.exe -m ruff check worker
worker\.venv\Scripts\python.exe -m pytest worker -m "not integration"
npm run test:integration
worker\.venv\Scripts\python.exe -m pytest worker -m integration
```

통합 테스트는 Phase -1 격리 완료 후 실행한다. 삭제 파이프라인 통합 테스트는
사람의 파괴 테스트 승인을 받고 fixture 사용자만 대상으로 실행한다. 실제 Vertex
eval도 사람의 비용 승인을 받아 detector·narration 변경분을 1회 실행한다.

아래가 하나라도 빠지면 "MVP 완료"가 아니라 **미검증**으로 보고한다.

- lint · typecheck · unit · integration · eval
- 마이그레이션 up/down 정적 검토
- 검색·삭제 보안 리뷰
- 7개 경로의 loading/processing/error/offline/empty 상태 검토
- 탭바와 모든 화면 링크의 404 부재

## 보고

Phase별로 무엇을 했는지, **어디서 계획과 실제가 달랐는지**, 멈춰서 물어야 할 것이
있는지 보고해라. 전부 다 됐다고만 쓰지 마라 — **안 된 것과 의심스러운 것을 먼저
써라.**
