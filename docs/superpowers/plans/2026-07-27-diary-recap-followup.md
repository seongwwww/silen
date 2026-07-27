# 일기 정화 · 오늘의 처음(recap) · 꼬리 질문 Implementation Plan

> **실행 주체:** 이 계획은 **Codex가 구현**한다. Superpowers 스킬 없이 수동으로 수행한다 — 태스크마다 ① 실패 테스트 → ② 실패 확인 → ③ 계획의 코드 그대로 구현 → ④ 통과 확인 → ⑤ lint/ruff + build → ⑥ 그 태스크 단위로 1커밋.

**Goal:** 실데이터에서 드러난 일기 품질 문제(“처음” 도배·메타 서술·본문과 목록 중복)를 고치고, 처음 등장한 것에 대해 꼬리 질문 하나를 던져 기록이 이어지게 한다.

**Architecture:** 차이의 성격에 따라 표시 경로를 나눈다 — `first_occurrence`는 목록(recap), `freq_shift`만 본문에 녹인다. detector 판정은 건드리지 않고 문구만 고친다. 꼬리 질문은 일기 생성 안에서 함께 만들고, 답변은 전용 저장 없이 새 기록이 된다.

**Tech Stack:** Python 3.12(워커) · Next.js 16 · TypeScript · Tailwind · pytest · Vitest

## Global Constraints

- 산출물은 **코드**다. `main` 직접 커밋 금지 — **`feat/diary-recap-followup` 브랜치를 `main`에서 새로 만들어** 작업한다.
- 커밋 메시지 `<type>(<scope>): <한국어 요약>`. scope는 `detector`·`worker`·`db`·`ui`·`eval`·`docs`. **`Co-Authored-By` 트레일러는 네 것으로.**
- **태스크마다 커밋만. push·merge 금지**(사람이 한다).
- ⚠️ **detector 변경과 프롬프트 변경을 같은 커밋에 섞지 마라**(git.md — eval 회귀를 이분 탐색해야 한다). Task 1과 Task 3·4는 반드시 별도 커밋.
- **마이그레이션은 up/down을 같은 커밋에.** down은 `supabase/migrations/down/<타임스탬프>_<이름>.down.sql`.
- ⚠️ **`supabase.select()` 인자는 리터럴 타입 유지**(상수면 `as const`). 이 오류는 lint·단위로 안 잡히고 **`npm run build`(tsc)에서만** 드러난다 → **프론트 태스크마다 build를 돌려라.**
- ⚠️ **터치 타깃 44px**(`min-h-11`). `min-h-9` 금지.
- ⚠️ **URL에 사용자 콘텐츠·엔티티명을 넣지 마라.** 질문 링크는 **id만** 넘긴다(`?section=<uuid>`). 질문 텍스트를 쿼리스트링에 넣지 마라(privacy.md).
- **로그에 기록 본문·일기·질문 텍스트를 남기지 마라.** id·카운트만.
- 파이썬은 `worker\.venv\Scripts\python.exe` 직접 호출. 통합 테스트는 로컬 Supabase 필요.
- 🚫 **`run-diary`·`run-daily`를 임의로 실행하지 마라(실 LLM 비용).** 검증은 스텁으로 한다.
- 🚫 **통합 테스트가 개발 DB의 사용자·큐를 지운다는 걸 알고 있어라.** 그건 알려진 문제이며 이번 범위 밖이다. 테스트는 정상적으로 돌려도 된다(실데이터 검증은 이미 끝났다).
- 완료(DoD) = ruff + pytest + lint + build + vitest(단위·통합). eval은 Task 7에서 다룬다.
- 못 고치는 실패나 모호한 점이 있으면 **멈추고 보고**하라. 추측하거나 테스트를 약화시키지 마라.

## 결정 고정 (Locked Decisions — 무-추측 규약)

1. **`first_occurrence`는 일기 본문에 넣지 않는다.** 일기 LLM 입력의 `differences`에서 제외한다. `freq_shift`만 넣는다.
2. **`다른점` 섹션에는 그날 확정된 차이 **전부**를 쓴다**(본문에 녹은 것만이 아니라). 이게 recap 재료다. 새 `section_type`을 만들지 마라.
3. **detector의 판정 로직·임계값·confidence를 바꾸지 마라.** Task 1은 `description` 문구만 바꾼다.
4. **description 새 문구는 `"처음 등장"`** (영문 enum 제거). `freq_shift` 문구는 그대로 둔다.
5. **꼬리 질문 대상 우선순위: `person` → `place` → `activity`.** 그날 `first_occurrence` 확정 차이 중 이 순서로 첫 번째 하나만. `thing`은 대상이 아니다(사람·장소·활동이 이야기가 된다). 대상이 없으면 **질문을 만들지 않는다.**
6. **질문은 하루에 최대 1개.** 여러 개 만들지 마라(prompts-draft §6 "기본은 묻지 않음").
7. **질문 저장:** `diary_sections(section_type='질문', difference_id=<근거 차이>, content=<질문>)`.
8. **답변 저장 스키마를 만들지 마라.** 질문 카드를 탭하면 기록 화면으로 이동하고, 사용자가 남긴 메모가 곧 답이다.
9. **일기 가드레일에 추가할 두 가지:** ① 메타 표현 블록리스트 ② **본문에 쓰인 차이(`used_difference_ids`)의 엔티티명이 본문에 그대로 등장해야 한다**(`여친`→`여자친구` 차단). 입력에 없는 차이는 이미 기존 검사가 막는다.
10. **메타 표현 블록리스트(diary 전용):** `"기록된"`, `"기록한"`, `"기록되"`, `"라는 단어"`, `"라는 표현"`, `"일기에"`. 기존 `FORBIDDEN_PHRASES`(조언·인과)는 그대로 함께 쓴다.
11. **`fetch_confirmed_differences` 반환 타입을 바꾼다.** `list[tuple[str,str]]` → `list[ConfirmedDifference]` dataclass(`difference_id`·`headline`·`detection_method`·`entity_type`·`entity_name`). 호출자(`write_diary`)를 함께 고친다.
12. **질문 생성 LLM은 `DiaryWriter`와 별도 포트**(`QuestionWriter`)로 둔다. 스텁 주입으로 테스트한다. 프로덕션 구현은 Vertex Gemini 재사용.

## File Structure

| 경로 | 책임 |
|------|------|
| `worker/src/silen_worker/detection/service.py`(수정) | description 문구만 |
| `worker/tests/test_detection.py`·`test_detection_repo_integration.py`·`test_detect_day_integration.py`(수정) | 문구 기대값 |
| `supabase/migrations/<ts>_diary_question.sql` + `down/` | section_type에 `'질문'` 추가 |
| `worker/src/silen_worker/db.py`(수정) | `fetch_confirmed_differences` 확장, `insert_diary_question` |
| `worker/src/silen_worker/diary/service.py`(수정) | 본문 입력 분리·가드레일 강화 |
| `worker/src/silen_worker/diary/constants.py`(수정) | 메타 블록리스트 |
| `worker/src/silen_worker/diary/question.py` | 질문 게이트·프롬프트·가드레일·포트 |
| `worker/src/silen_worker/diary/gemini.py`(수정) | `GeminiQuestionWriter` 추가 |
| `worker/src/silen_worker/tasks/write_diary.py`(수정) | 분리 배선 + 질문 생성 |
| `lib/repositories/diaryRepository.ts`(수정) | `recap`·`question` 조회 |
| `lib/services/diary.ts`(수정) | 타입 확장 |
| `app/diary/_components/DiaryView.tsx`(수정) | recap 제목·질문 카드 |
| `app/_components/RecordForm.tsx`(수정) | 질문 맥락 표시 |
| `app/page.tsx`(수정) | `?section=` 조회 |
| `evals/diary/`(수정) | 골든셋 보강 |

---

## Task 1: detector description 문구 정화

**⚠️ 이 태스크는 detector만 건드린다. 프롬프트·일기 코드를 같은 커밋에 넣지 마라(git.md).**

**Files:** Modify `worker/src/silen_worker/detection/service.py`, `worker/tests/test_detection.py`, `worker/tests/test_detection_repo_integration.py`, `worker/tests/test_detect_day_integration.py`

- [ ] **Step 1: 테스트 기대값 먼저 바꾼다(실패 확인용)**

세 파일에서 `"이 thing 첫 등장"`·`"이 place 첫 등장"` 문자열을 **`"처음 등장"`** 으로 바꾼다.
- `worker/tests/test_detection.py:21` → `assert out[0].description == "처음 등장"`
- `worker/tests/test_detection_repo_integration.py:87,90` → 인자를 `"처음 등장"` 으로
- `worker/tests/test_detect_day_integration.py:44` → `assert rows == [("first_occurrence", "처음 등장")]`

- [ ] **Step 2: 실패 확인**

```powershell
worker\.venv\Scripts\python.exe -m pytest worker/tests/test_detection.py -v
```
Expected: FAIL — 현재 값이 `"이 thing 첫 등장"`이라 불일치.

- [ ] **Step 3: 구현**

`worker/src/silen_worker/detection/service.py`에서 first_occurrence 생성부의 description을 바꾼다:

```python
                DetectedDifference(
                    w.entity_id, w.entity_type, "first_occurrence",
                    # 영문 enum이 LLM에 그대로 가면 "이 thing이 기록된 것도 처음"
                    # 같은 메타 서술을 낳는다. 사람 말로 둔다.
                    "처음 등장", FIRST_OCCURRENCE_CONFIDENCE,
                )
```

**판정 로직·임계값·confidence는 건드리지 마라.** `freq_shift` 문구도 그대로 둔다.

- [ ] **Step 4: 통과 확인**

```powershell
worker\.venv\Scripts\python.exe -m pytest worker -q
worker\.venv\Scripts\python.exe -m ruff check worker
```
Expected: 전체 PASS(113 기준), ruff 통과.

- [ ] **Step 5: 커밋**

```powershell
git add worker/src/silen_worker/detection/service.py worker/tests/test_detection.py worker/tests/test_detection_repo_integration.py worker/tests/test_detect_day_integration.py
git commit -m "fix(detector): first_occurrence 문구를 사람 말로

description에 영문 enum이 들어가 LLM이 '이 thing이 기록된 것도 처음'
같은 메타 서술을 만들었다. '처음 등장'으로 바꾼다. 판정 로직·임계값·
confidence는 그대로다."
```

---

## Task 2: 스키마 — `section_type`에 `'질문'` 추가

**Files:** Create `supabase/migrations/<ts>_diary_question.sql`, `supabase/migrations/down/<ts>_diary_question.down.sql`, `worker/tests/test_diary_question_schema_integration.py`

- [ ] **Step 1: 마이그레이션 생성**

```powershell
npx supabase migration new diary_question
```
생성된 14자리 타임스탬프를 up/down 파일명에 **동일하게** 쓴다.

- [ ] **Step 2: up 작성**

```sql
-- 꼬리 질문은 일기에 딸린 섹션이다. 새 테이블을 만들지 않고
-- diary_sections에 종류를 하나 추가한다. difference_id로 근거 차이와 연결된다.
alter table public.diary_sections
  drop constraint diary_sections_section_type_check;
alter table public.diary_sections
  add constraint diary_sections_section_type_check
  check (section_type in ('오늘의한문장','본문','다른점','성취','질문'));
```

제약 이름이 다르면 아래로 확인해 맞춘다:
```powershell
worker\.venv\Scripts\python.exe -c "import psycopg; c=psycopg.connect('postgresql://postgres:postgres@127.0.0.1:54322/postgres'); print(c.execute(\"select conname from pg_constraint where conrelid='public.diary_sections'::regclass and contype='c'\").fetchall())"
```

- [ ] **Step 3: down 작성**

```sql
-- 되돌리면 기존 '질문' 행이 제약 위반이라 실패할 수 있다(의도).
alter table public.diary_sections
  drop constraint diary_sections_section_type_check;
alter table public.diary_sections
  add constraint diary_sections_section_type_check
  check (section_type in ('오늘의한문장','본문','다른점','성취'));
```

- [ ] **Step 4: 통합 테스트**

`worker/tests/test_diary_question_schema_integration.py`:

```python
import pytest

from tests.conftest import seed_user, delete_user


@pytest.mark.integration
def test_질문_섹션을_저장할_수_있다(conn):
    user = seed_user(conn)
    try:
        diary = conn.execute(
            "insert into public.diaries (user_id, date, status, generated_text) "
            "values (%s, current_date, 'draft', '본문') returning id::text",
            (user,),
        ).fetchone()[0]
        conn.execute(
            "insert into public.diary_sections (diary_id, section_type, content) "
            "values (%s, '질문', '오늘 처음 만난 사람은 어떤 분이었나요?')",
            (diary,),
        )
        row = conn.execute(
            "select content from public.diary_sections "
            "where diary_id = %s and section_type = '질문'",
            (diary,),
        ).fetchone()
        assert row is not None
    finally:
        delete_user(conn, user)
```

- [ ] **Step 5: 적용·실행**

```powershell
npx supabase db reset
npx supabase stop; Start-Sleep -Seconds 3; npx supabase start
worker\.venv\Scripts\python.exe -m pytest worker/tests/test_diary_question_schema_integration.py -m integration -v
```
Expected: 1건 PASS.

- [ ] **Step 6: 커밋**

```powershell
git add supabase/migrations worker/tests/test_diary_question_schema_integration.py
git commit -m "feat(db): diary_sections에 질문 종류 추가

꼬리 질문은 일기에 딸린 섹션이다. 새 테이블 없이 종류를 하나 늘리고
difference_id로 근거 차이와 연결한다. up/down 동봉."
```

---

## Task 3: 일기 재료 분리 — 본문엔 freq_shift만, recap엔 전부

**Files:** Modify `worker/src/silen_worker/db.py`, `worker/src/silen_worker/tasks/write_diary.py`, `worker/tests/test_diary_repo_integration.py`, `worker/tests/test_diary_integration.py`

**Interfaces:**
- Produces:
  ```python
  @dataclass
  class ConfirmedDifference:
      difference_id: str; headline: str; detection_method: str
      entity_type: str; entity_name: str
  def fetch_confirmed_differences(conn, user_id, target_date) -> list[ConfirmedDifference]
  ```

- [ ] **Step 1: 저장소 확장**

`worker/src/silen_worker/db.py`의 `fetch_confirmed_differences`를 아래로 **교체**한다(`ConfirmedDifference`는 그 위에 둔다):

```python
@dataclass
class ConfirmedDifference:
    difference_id: str
    headline: str
    detection_method: str
    entity_type: str
    entity_name: str


def fetch_confirmed_differences(
    conn: psycopg.Connection, user_id: str, target_date: date
) -> list[ConfirmedDifference]:
    """그날 confirmed(intact) 차이. detection_method로 본문용(freq_shift)과
    recap용(first_occurrence)을 가르고, entity_name은 가드레일에 쓴다."""
    rows = conn.execute(
        """
        select d.id::text, coalesce(n.headline, d.description, ''),
               d.detection_method, e.entity_type, e.name
        from public.differences d
        join public.entities e on e.id = d.entity_id
        left join public.difference_narrations n on n.difference_id = d.id
        where d.user_id = %s
          and d.date = %s
          and d.status = 'confirmed'
          and d.evidence_state = 'intact'
        order by d.id
        """,
        (user_id, target_date),
    ).fetchall()
    return [ConfirmedDifference(r[0], r[1], r[2], r[3], r[4]) for r in rows]
```

> `entities`를 INNER JOIN으로 바꿨다. 엔티티 없는 차이(미래 zscore 등)는 아직 없고, 있어도 일기 재료가 아니다.

- [ ] **Step 2: 경계 배선 수정**

`worker/src/silen_worker/tasks/write_diary.py`에서 차이를 다루는 부분을 아래로 바꾼다:

```python
    confirmed = fetch_confirmed_differences(conn, user_id, target)
    # 본문엔 '이야기가 되는' 반복만 녹인다. '처음 등장'은 나열이 자연스러워
    # recap 목록이 담당한다(본문에 넣으면 "~한 것도 처음이다"가 반복된다).
    body_diffs = [c for c in confirmed if c.detection_method == "freq_shift"]

    facts = DiaryInput(
        date_iso=target_date_iso,
        user_id=user_id,
        memories=memories,
        differences=[
            DiaryDifference(c.difference_id, c.headline, c.entity_name) for c in body_diffs
        ],
    )
```

그리고 섹션 저장을 **확정 차이 전부**로 바꾼다(기존 `used_diff_pairs` 계산을 대체):

```python
    diary_id = upsert_diary(conn, user_id, target, diary.body)
    # recap 목록은 그날 확정된 차이 전부다(본문에 녹은 것만이 아니라).
    recap = [(c.difference_id, c.headline) for c in confirmed]
    replace_diary_sections(conn, diary_id, diary.one_line, diary.body, recap)
    replace_diary_sources(conn, diary_id, diary.used_memory_ids)
```

- [ ] **Step 3: `DiaryDifference`에 엔티티명 추가**

`worker/src/silen_worker/diary/service.py`:

```python
@dataclass(frozen=True)
class DiaryDifference:
    difference_id: str
    headline: str
    entity_name: str
```

`build_prompt`의 차이 줄도 바꾼다(엔티티명을 노출해 LLM이 그 표현을 쓰게 한다):

```python
    diff_lines = (
        "\n".join(f"- [{d.difference_id}] {d.headline} (표현: {d.entity_name})" for d in facts.differences)
        or "- (없음)"
    )
```

그리고 프롬프트 규칙에 두 줄을 추가한다(기존 규칙 줄 뒤):

```python
        "'일기에 기록됐다' 같은 메타 서술 금지 — 시스템의 기록 상태가 아니라 네 하루를 써라.\n"
        "다른 점에 적힌 표현을 그대로 써라. 다른 말로 바꾸지 마라(예: '여친'을 '여자친구'로 바꾸지 마라).\n"
```

- [ ] **Step 4: 기존 테스트 수정**

`worker/tests/test_diary.py`의 `_facts()`에서 `DiaryDifference("d1", "평소보다 일찍 퇴근")` → `DiaryDifference("d1", "평소보다 일찍 퇴근", "퇴근")`으로 인자를 하나 늘린다(다른 곳도 동일).

`worker/tests/test_diary_repo_integration.py`에서 `fetch_confirmed_differences` 반환을 튜플로 비교하던 단언을 dataclass 필드 비교로 바꾼다.

- [ ] **Step 5: 통합 테스트 추가**

`worker/tests/test_diary_integration.py`의 describe 끝에 추가:

```python
@pytest.mark.integration
def test_처음등장은_본문재료가_아니고_recap에만_남는다(conn):
    user = seed_user(conn)
    try:
        seed_memory(conn, user, "점심 김밥")
        # first_occurrence 확정 차이 하나
        ent = conn.execute(
            "insert into public.entities (user_id, entity_type, name, normalized_name) "
            "values (%s, 'thing', '김밥', '김밥') returning id::text", (user,)
        ).fetchone()[0]
        conn.execute(
            "insert into public.differences (user_id, date, entity_id, dimension, description, "
            "detection_method, confidence, category, status, evidence_state) "
            "values (%s, %s, %s, 'thing', '처음 등장', 'first_occurrence', 1.0, "
            "'오늘의다른점', 'confirmed', 'intact')",
            (user, date.today(), ent),
        )

        seen = {}

        class RecordingWriter:
            model = "stub"

            def write(self, facts):
                seen["diffs"] = [d.difference_id for d in facts.differences]
                return {
                    "one_line": "비슷한 하루.",
                    "body": "특별할 것 없는 하루였다. 점심은 김밥.",
                    "used_memory_ids": [m.memory_id for m in facts.memories],
                    "used_difference_ids": [],
                }

        did = generate_diary(conn, user, _today_iso(), writer=RecordingWriter())
        assert did is not None
        assert seen["diffs"] == []  # 본문 재료에서 제외됐다

        recap = conn.execute(
            "select count(*)::int from public.diary_sections "
            "where diary_id = %s and section_type = '다른점'", (did,),
        ).fetchone()[0]
        assert recap == 1  # recap 목록엔 남는다
    finally:
        delete_user(conn, user)
```

- [ ] **Step 6: 실행**

```powershell
worker\.venv\Scripts\python.exe -m pytest worker -q
worker\.venv\Scripts\python.exe -m ruff check worker
```
Expected: 전체 PASS.

- [ ] **Step 7: 커밋**

```powershell
git add worker/src/silen_worker/db.py worker/src/silen_worker/tasks/write_diary.py worker/src/silen_worker/diary/service.py worker/tests
git commit -m "feat(worker): 일기 본문엔 반복만, 처음 등장은 recap으로

first_occurrence를 본문 재료에서 빼고 freq_shift만 녹인다. '처음'은
나열이 자연스러워 recap 목록이 담당한다 — 본문에 넣으니 '~한 것도
처음이다'가 반복됐다. 다른점 섹션은 확정 차이 전부를 남겨 recap 재료가
된다. 프롬프트에 메타 서술 금지와 표현 보존 규칙을 넣는다."
```

---

## Task 4: 일기 가드레일 강화 — 메타 표현·엔티티명

**Files:** Modify `worker/src/silen_worker/diary/constants.py`, `worker/src/silen_worker/diary/service.py`, `worker/tests/test_diary.py`

- [ ] **Step 1: 실패 테스트 추가**

`worker/tests/test_diary.py` 끝에 추가:

```python
def test_메타_서술은_폐기한다():
    out = guardrail(_raw(body="일기에 출근이라는 행동이 기록된 것도 오늘이 처음이다."), _facts())
    assert out is None


def test_단어를_기록했다는_표현도_폐기한다():
    out = guardrail(_raw(body="시간이라는 단어를 남긴 것은 오늘이 처음이다."), _facts())
    assert out is None


def test_쓴_차이의_표현을_바꾸면_폐기한다():
    # 입력 엔티티명은 '퇴근'인데 본문이 다른 말로 바꿔 쓰면 안 된다.
    out = guardrail(
        _raw(body="오늘은 평소보다 일찍 회사를 나왔다.", used_difference_ids=["d1"]),
        _facts(),
    )
    assert out is None


def test_쓴_차이의_표현을_그대로_쓰면_통과한다():
    out = guardrail(
        _raw(body="오늘은 평소보다 일찍 퇴근을 했다.", used_difference_ids=["d1"]),
        _facts(),
    )
    assert out is not None
```

- [ ] **Step 2: 실패 확인**

```powershell
worker\.venv\Scripts\python.exe -m pytest worker/tests/test_diary.py -v
```
Expected: 새 4건 중 앞 3건 FAIL.

- [ ] **Step 3: 구현**

`worker/src/silen_worker/diary/constants.py`에 추가:

```python
# 시스템의 기록 상태를 말하는 메타 서술. 사용자의 하루를 써야 한다.
# 실데이터에서 "일기에 출근이라는 행동이 기록된 것도 오늘이 처음이다" 류가 나왔다.
META_PHRASES = ("기록된", "기록한", "기록되", "라는 단어", "라는 표현", "일기에")
```

`worker/src/silen_worker/diary/service.py`의 `guardrail`에서 블록리스트 검사 부분을 아래로 바꾼다:

```python
    blob = f"{one_line} {body}"
    if any(p in blob for p in FORBIDDEN_PHRASES):
        return None
    if any(p in blob for p in META_PHRASES):
        return None

    # 본문에 쓴 차이는 그 엔티티 표현을 그대로 써야 한다.
    # ('여친'을 '여자친구'로 바꾸는 확장을 막는다 — 원문에 없는 표현이다.)
    name_by_id = {d.difference_id: d.entity_name for d in facts.differences}
    for difference_id in used_diff:
        name = name_by_id.get(difference_id, "")
        if name and name not in body:
            return None
```

import에 `META_PHRASES`를 추가한다.

- [ ] **Step 4: 통과 확인**

```powershell
worker\.venv\Scripts\python.exe -m pytest worker -q
worker\.venv\Scripts\python.exe -m ruff check worker
```
Expected: 전체 PASS.

- [ ] **Step 5: 커밋**

```powershell
git add worker/src/silen_worker/diary/constants.py worker/src/silen_worker/diary/service.py worker/tests/test_diary.py
git commit -m "feat(worker): 일기 가드레일 — 메타 서술·표현 변경 차단

실데이터에서 '일기에 기록된 것도 처음이다' 류 메타 서술과 '여친'을
'여자친구'로 바꾸는 확장이 통과했다. 메타 표현 블록리스트를 두고,
본문에 쓴 차이의 엔티티 표현이 본문에 그대로 있는지 검사한다."
```

---

## Task 5: 꼬리 질문 생성

**Files:** Create `worker/src/silen_worker/diary/question.py`, `worker/tests/test_diary_question.py`; Modify `worker/src/silen_worker/diary/gemini.py`, `worker/src/silen_worker/db.py`, `worker/src/silen_worker/tasks/write_diary.py`, `worker/tests/test_diary_integration.py`

**Interfaces:**
- Produces:
  ```python
  QUESTION_TARGET_TYPES = ("person", "place", "activity")
  def pick_question_target(confirmed: list[ConfirmedDifference]) -> ConfirmedDifference | None
  def build_question_prompt(target: ConfirmedDifference) -> str
  def question_guardrail(raw: dict, target: ConfirmedDifference) -> str | None
  class QuestionWriter(Protocol):
      def ask(self, target) -> dict: ...
  # db.py
  def insert_diary_question(conn, diary_id, difference_id, content) -> None
  ```

- [ ] **Step 1: 실패 테스트 작성**

`worker/tests/test_diary_question.py`:

```python
from silen_worker.db import ConfirmedDifference
from silen_worker.diary.question import (
    build_question_prompt, pick_question_target, question_guardrail,
)


def _diff(method="first_occurrence", etype="person", name="지은", did="d1"):
    return ConfirmedDifference(did, f"{name} 처음", method, etype, name)


def test_사람이_있으면_사람을_고른다():
    target = pick_question_target([_diff(etype="activity", did="d2"), _diff(etype="person")])
    assert target.entity_type == "person"


def test_사람이_없으면_장소_다음_활동():
    assert pick_question_target([_diff(etype="activity", did="d2"), _diff(etype="place", did="d3")]).entity_type == "place"
    assert pick_question_target([_diff(etype="activity")]).entity_type == "activity"


def test_사물은_대상이_아니다():
    assert pick_question_target([_diff(etype="thing")]) is None


def test_반복차이는_대상이_아니다():
    assert pick_question_target([_diff(method="freq_shift")]) is None


def test_대상이_없으면_None():
    assert pick_question_target([]) is None


def test_프롬프트에_엔티티명이_들어간다():
    assert "지은" in build_question_prompt(_diff())


def test_정상_질문은_통과한다():
    assert question_guardrail({"question": "지은은 어떤 사람이었어요?"}, _diff()) is not None


def test_엔티티명_없는_질문은_폐기한다():
    assert question_guardrail({"question": "오늘 어땠어요?"}, _diff()) is None


def test_심문조_질문은_폐기한다():
    assert question_guardrail({"question": "지은과 무엇을 했는지 말해보세요."}, _diff()) is None


def test_빈_질문은_폐기한다():
    assert question_guardrail({"question": "   "}, _diff()) is None
```

- [ ] **Step 2: 실패 확인**

```powershell
worker\.venv\Scripts\python.exe -m pytest worker/tests/test_diary_question.py -v
```
Expected: FAIL — 모듈 없음.

- [ ] **Step 3: 구현**

`worker/src/silen_worker/diary/question.py`:

```python
"""꼬리 질문 — 처음 등장한 것에 대해 하루 한 번만 묻는다(prompts-draft §6).

기본은 묻지 않는다. 물어도 부담이 없어야 하고, 심문하지 않는다.
답변은 별도로 저장하지 않는다 — 사용자가 남기는 새 기록이 곧 답이다.
"""

from typing import Protocol

from silen_worker.db import ConfirmedDifference

# 사람·장소·활동이 이야기가 된다. 사물은 묻지 않는다.
QUESTION_TARGET_TYPES = ("person", "place", "activity")

QUESTION_MAX = 60

# 심문조·강요. "답 안 해도 되게" 하려면 이런 말투를 막아야 한다.
FORBIDDEN_QUESTION_PHRASES = ("말해보세요", "말해 보세요", "설명하세요", "적어주세요", "해야", "반드시")


def pick_question_target(
    confirmed: list[ConfirmedDifference],
) -> ConfirmedDifference | None:
    """질문 대상 하나. 처음 등장한 사람 > 장소 > 활동 순. 없으면 None(묻지 않는다)."""
    firsts = [c for c in confirmed if c.detection_method == "first_occurrence"]
    for entity_type in QUESTION_TARGET_TYPES:
        for candidate in firsts:
            if candidate.entity_type == entity_type:
                return candidate
    return None


def build_question_prompt(target: ConfirmedDifference) -> str:
    return (
        "너는 일기 앱 '실은'의 질문 담당이다. 오늘 처음 등장한 것에 대해\n"
        "짧은 질문 하나를 만들어라.\n"
        "규칙: 부담 없는 말투로, 답하지 않아도 되게. 심문하지 마라.\n"
        "'무엇을 했냐'가 아니라 '어땠냐/어떤 사람이냐' 방향으로.\n"
        f"아래 표현을 그대로 써라: {target.entity_name}\n"
        f"{QUESTION_MAX}자 이내.\n\n"
        f"처음 등장: {target.entity_name} ({target.entity_type})\n\n"
        '출력(JSON): {"question": "..."}'
    )


def question_guardrail(raw: dict, target: ConfirmedDifference) -> str | None:
    """통과한 질문 문자열, 아니면 None(저장하지 않는다)."""
    if not isinstance(raw, dict):
        return None
    question = str(raw.get("question") or "").strip()
    if not question or len(question) > QUESTION_MAX:
        return None
    if target.entity_name not in question:
        return None
    if any(p in question for p in FORBIDDEN_QUESTION_PHRASES):
        return None
    return question


class QuestionWriter(Protocol):
    def ask(self, target: ConfirmedDifference) -> dict:
        """{"question": "..."} 원시 출력. 가드레일 전."""
        ...
```

- [ ] **Step 4: 저장소·Gemini·배선**

`worker/src/silen_worker/db.py` 끝에 추가:

```python
def insert_diary_question(
    conn: psycopg.Connection, diary_id: str, difference_id: str, content: str
) -> None:
    """일기의 꼬리 질문 하나. replace_diary_sections가 섹션을 지운 뒤에 부른다."""
    conn.execute(
        "insert into public.diary_sections (diary_id, difference_id, section_type, content) "
        "values (%s, %s, '질문', %s)",
        (diary_id, difference_id, content),
    )
```

`worker/src/silen_worker/diary/gemini.py` 끝에 추가:

```python
_QUESTION_SCHEMA = types.Schema(
    type="OBJECT",
    properties={"question": types.Schema(type="STRING")},
    required=["question"],
)


class GeminiQuestionWriter:
    """QuestionWriter 포트 구현. 가드레일은 호출자 책임."""

    model = _MODEL

    def __init__(self) -> None:
        if not os.environ.get("GOOGLE_CLOUD_PROJECT"):
            raise RuntimeError("GOOGLE_CLOUD_PROJECT 미설정 — Vertex ADC 구성 필요")
        self._client = genai.Client()

    def ask(self, target) -> dict:
        from silen_worker.diary.question import build_question_prompt

        resp = self._client.models.generate_content(
            model=_MODEL,
            contents=build_question_prompt(target),
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=_QUESTION_SCHEMA,
            ),
        )
        return json.loads(resp.text)
```

`worker/src/silen_worker/tasks/write_diary.py`의 `generate_diary` 시그니처에 `asker` 파라미터를 더하고, 섹션 저장 뒤에 질문 생성을 붙인다:

```python
def generate_diary(
    conn: psycopg.Connection,
    user_id: str,
    target_date_iso: str,
    force: bool = False,
    writer: DiaryWriter | None = None,
    asker=None,
) -> str | None:
```

```python
    replace_diary_sources(conn, diary_id, diary.used_memory_ids)

    # 꼬리 질문은 하루 한 번, 대상이 있을 때만(prompts-draft §6 "기본은 묻지 않음").
    target = pick_question_target(confirmed)
    if target is not None:
        if asker is None:
            from silen_worker.diary.gemini import GeminiQuestionWriter

            asker = GeminiQuestionWriter()
        question = question_guardrail(asker.ask(target), target)
        if question is not None:
            insert_diary_question(conn, diary_id, target.difference_id, question)

    return diary_id
```

- [ ] **Step 5: 통합 테스트 추가**

`worker/tests/test_diary_integration.py` 끝에 추가:

```python
class StubAsker:
    def __init__(self, question):
        self._question = question

    def ask(self, target):
        return {"question": self._question}


@pytest.mark.integration
def test_처음_등장한_사람이_있으면_질문이_생긴다(conn):
    user = seed_user(conn)
    try:
        seed_memory(conn, user, "지은이 만남")
        ent = conn.execute(
            "insert into public.entities (user_id, entity_type, name, normalized_name) "
            "values (%s, 'person', '지은', '지은') returning id::text", (user,)
        ).fetchone()[0]
        conn.execute(
            "insert into public.differences (user_id, date, entity_id, dimension, description, "
            "detection_method, confidence, category, status, evidence_state) "
            "values (%s, %s, %s, 'person', '처음 등장', 'first_occurrence', 1.0, "
            "'오늘의다른점', 'confirmed', 'intact')",
            (user, date.today(), ent),
        )
        did = generate_diary(
            conn, user, _today_iso(), writer=StubWriter(),
            asker=StubAsker("지은은 어떤 사람이었어요?"),
        )
        row = conn.execute(
            "select content from public.diary_sections "
            "where diary_id = %s and section_type = '질문'", (did,),
        ).fetchone()
        assert row is not None
    finally:
        delete_user(conn, user)


@pytest.mark.integration
def test_대상이_없으면_질문이_생기지_않는다(conn):
    user = seed_user(conn)
    try:
        seed_memory(conn, user, "점심 김밥")
        did = generate_diary(
            conn, user, _today_iso(), writer=StubWriter(),
            asker=StubAsker("아무 질문"),
        )
        count = conn.execute(
            "select count(*)::int from public.diary_sections "
            "where diary_id = %s and section_type = '질문'", (did,),
        ).fetchone()[0]
        assert count == 0
    finally:
        delete_user(conn, user)
```

- [ ] **Step 6: 실행·커밋**

```powershell
worker\.venv\Scripts\python.exe -m pytest worker -q
worker\.venv\Scripts\python.exe -m ruff check worker
git add worker/src/silen_worker/diary worker/src/silen_worker/db.py worker/src/silen_worker/tasks/write_diary.py worker/tests
git commit -m "feat(worker): 꼬리 질문 하루 하나

처음 등장한 사람>장소>활동 중 하나에만 짧은 질문을 만든다. 대상이 없으면
묻지 않는다. 심문조·엔티티명 누락은 가드레일로 폐기한다. 답변은 따로
저장하지 않는다 — 사용자가 남기는 새 기록이 곧 답이다."
```

---

## Task 6: 프론트 — recap 제목 · 질문 카드 · 기록 화면 맥락

**Files:** Modify `lib/services/diary.ts`, `lib/repositories/diaryRepository.ts`, `app/diary/_components/DiaryView.tsx`, `app/_components/RecordForm.tsx`, `app/page.tsx`; Create `app/diary/_components/FollowUpCard.tsx` + 테스트

- [ ] **Step 1: 타입·조회 확장**

`lib/services/diary.ts`의 `DiaryView`에 추가:

```ts
  /** 꼬리 질문(없으면 null). id는 기록 화면 링크에 쓴다 — URL엔 id만 넣는다. */
  question: { sectionId: string; text: string } | null;
```

`lib/repositories/diaryRepository.ts`의 `DIARY_SELECT`에 `id`를 섹션에 추가하고(한 줄 리터럴 유지):

```ts
const DIARY_SELECT =
  "date, status, generated_text, edited_text, diary_sections(id, section_type, content), diary_sources(memories(raw_text, is_locked, deleted_at))" as const;
```

`SectionRow`에 `id: string`을 더하고, `toDiaryView`의 반환에 추가:

```ts
    question: (() => {
      const found = sections.find((section) => section.section_type === "질문");
      return found ? { sectionId: found.id, text: found.content } : null;
    })(),
```

`differences` 필터는 그대로 `'다른점'`을 쓴다(recap 목록).

- [ ] **Step 2: 질문 조회 함수 추가**

`lib/repositories/diaryRepository.ts`의 저장소 객체에 추가:

```ts
    /** 기록 화면이 질문을 맥락으로 보여줄 때 쓴다. RLS가 소유권을 강제한다. */
    async findQuestionById(sectionId: string): Promise<string | null> {
      const { data, error } = await client
        .from("diary_sections")
        .select("content")
        .eq("id", sectionId)
        .eq("section_type", "질문")
        .limit(1);
      if (error) throw error;
      return (data?.[0]?.content as string | undefined) ?? null;
    },
```

- [ ] **Step 3: 질문 카드 컴포넌트**

`app/diary/_components/FollowUpCard.tsx`:

```tsx
import Link from "next/link";

/** 처음 등장한 것에 대해 한 번 묻는다. 답은 강요하지 않는다 — 탭하면 기록
 * 화면으로 갈 뿐이고, 거기서 평소처럼 메모를 남기면 그게 답이다.
 * URL엔 id만 담는다(질문 텍스트에 사람 이름이 들어갈 수 있다). */
export function FollowUpCard({ sectionId, text }: { sectionId: string; text: string }) {
  return (
    <section className="mt-6">
      <p className="mb-2 text-xs text-muted-foreground">덧붙이고 싶다면</p>
      <Link
        href={`/?section=${sectionId}`}
        className="block min-h-11 rounded-lg border px-3 py-2 text-[15px]"
      >
        {text}
      </Link>
    </section>
  );
}
```

- [ ] **Step 4: `DiaryArticle`에 recap 제목·질문 카드**

`app/diary/_components/DiaryView.tsx`에서 차이 목록 블록을 아래로 바꾸고, 그 아래에 질문 카드를 둔다:

```tsx
      {diary.differences.length > 0 && (
        <section className="mt-4">
          <h3 className="mb-1 text-xs text-muted-foreground">오늘 처음</h3>
          <ul className="list-disc space-y-1 pl-5">
            {diary.differences.map((d, i) => (
              <li key={i} className="text-[15px] text-muted-foreground">
                {d}
              </li>
            ))}
          </ul>
        </section>
      )}

      {diary.question && (
        <FollowUpCard sectionId={diary.question.sectionId} text={diary.question.text} />
      )}
```

`import { FollowUpCard } from "./FollowUpCard";`를 추가한다.

- [ ] **Step 5: 기록 화면 질문 맥락**

`app/page.tsx`에서 `searchParams`로 `section`을 받아 질문을 조회해 `RecordForm`에 넘긴다. **Next.js 16에서 `searchParams`는 Promise다.**

```tsx
export default async function Home({
  searchParams,
}: {
  searchParams: Promise<{ section?: string }>;
}) {
  const { section } = await searchParams;
  let question: string | null = null;
  if (section) {
    const supabase = await createServerSupabase();
    const {
      data: { user },
    } = await supabase.auth.getUser();
    if (user) question = await createDiaryRepository(supabase).findQuestionById(section);
  }
  // ...기존 렌더에 <RecordForm question={question} />
}
```

기존 `app/page.tsx` 구조를 유지하되 위 조회를 더하고 `RecordForm`에 `question`을 넘긴다. import 두 줄(`createServerSupabase`·`createDiaryRepository`)을 추가한다.

`app/_components/RecordForm.tsx`는 prop을 받아 상단에 보여준다:

```tsx
export function RecordForm({ question }: { question?: string | null }) {
```

`return`의 최상단 `<div className="flex flex-col gap-3">` 바로 안에 추가:

```tsx
      {question && (
        <p className="rounded-lg bg-muted px-3 py-2 text-[15px] text-muted-foreground">
          {question}
        </p>
      )}
```

- [ ] **Step 6: 단위 테스트**

`app/diary/_components/FollowUpCard.test.tsx`:

```tsx
// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { FollowUpCard } from "./FollowUpCard";

describe("FollowUpCard", () => {
  it("질문을 보여주고 기록 화면으로 링크한다", () => {
    render(<FollowUpCard sectionId="sec-1" text="지은은 어떤 사람이었어요?" />);
    const link = screen.getByRole("link", { name: "지은은 어떤 사람이었어요?" });
    expect(link).toHaveAttribute("href", "/?section=sec-1");
  });

  it("URL에 질문 텍스트를 담지 않는다", () => {
    render(<FollowUpCard sectionId="sec-1" text="지은은 어떤 사람이었어요?" />);
    expect(screen.getByRole("link").getAttribute("href")).not.toContain("지은");
  });

  it("44px 터치 타깃", () => {
    render(<FollowUpCard sectionId="sec-1" text="질문" />);
    expect(screen.getByRole("link").className).toContain("min-h-11");
  });
});
```

`app/diary/_components/DiaryView.test.tsx`의 `base` 객체에 `question: null`을 추가하고(타입 충족), 아래 테스트를 더한다:

```tsx
  it("오늘 처음 제목을 보여준다", () => {
    render(<DiaryArticle diary={base} />);
    expect(screen.getByText("오늘 처음")).toBeInTheDocument();
  });

  it("질문이 있으면 카드를 보여준다", () => {
    render(
      <DiaryArticle
        diary={{ ...base, question: { sectionId: "s1", text: "지은은 어떤 사람이었어요?" } }}
      />,
    );
    expect(screen.getByRole("link", { name: "지은은 어떤 사람이었어요?" })).toBeInTheDocument();
  });
```

`app/_components/RecordForm.test.tsx`에 추가:

```tsx
  it("질문이 주어지면 맥락으로 보여준다", () => {
    render(<RecordForm question="지은은 어떤 사람이었어요?" />);
    expect(screen.getByText("지은은 어떤 사람이었어요?")).toBeInTheDocument();
  });
```

- [ ] **Step 7: 실행·커밋**

```powershell
npx vitest run
npm run lint
npm run build
npx vitest run --config vitest.integration.config.mts
```
Expected: 전부 통과. **build를 꼭 돌려라**(select 타입 추론).

```powershell
git add lib/services/diary.ts lib/repositories/diaryRepository.ts app/diary/_components app/_components/RecordForm.tsx app/_components/RecordForm.test.tsx app/page.tsx
git commit -m "feat(ui): 오늘 처음 recap과 꼬리 질문 카드

차이 목록에 '오늘 처음' 제목을 주고, 질문이 있으면 카드로 보여준다.
탭하면 기록 화면으로 가며 질문이 맥락으로 뜬다 — 답은 새 기록이 된다.
URL엔 섹션 id만 담는다(질문에 사람 이름이 들어갈 수 있다)."
```

---

## Task 7: eval 보강 · 문서

**Files:** Modify `evals/diary/fixtures.json`, `evals/diary/run.py`, `README.md`, `supabase/README.md`

- [ ] **Step 1: 골든셋 보강**

`evals/diary/fixtures.json`의 `cases`에 추가:

```json
    {"name": "many-firsts-no-repetition",
     "memories": [["m1", "빵빠래 먹었다"], ["m2", "출근해서 놀았다"], ["m3", "여친이랑 싸웠다"]],
     "differences": [],
     "reason": "처음 등장은 본문 재료가 아니다 — '처음'이 반복되면 안 된다"}
```

> `differences`가 빈 이유: 이제 `first_occurrence`는 본문 입력에서 제외되므로, 이 케이스의 일기 입력엔 차이가 없다.

- [ ] **Step 2: 러너에 검사 추가**

`evals/diary/run.py`의 `run_case`에서 blob 검사 뒤에 추가하고, import에 `META_PHRASES`를 더한다:

```python
    from silen_worker.diary.constants import META_PHRASES

    meta_hit = [p for p in META_PHRASES if p in blob]
    if meta_hit:
        failures.append(f"메타 서술 혼입: {meta_hit}")

    if blob.count("처음") > 1:
        failures.append(f"'처음' 반복 {blob.count('처음')}회 — 나열은 recap이 담당한다")
```

- [ ] **Step 3: 실행 (실 Vertex, 1회)**

```powershell
$env:GOOGLE_GENAI_USE_VERTEXAI = "true"
$env:GOOGLE_CLOUD_PROJECT = "project-58561b19-fb35-4c01-bb2"
$env:GOOGLE_CLOUD_LOCATION = "global"
worker\.venv\Scripts\python.exe evals/diary/run.py
```
Expected: 전 케이스 PASS. 실패하면 **프롬프트·상수를 임의로 고치지 말고 결과를 보고**하라.

- [ ] **Step 4: 문서**

`supabase/README.md`의 "일기 생성" 절 끝에 추가:

```markdown
- 본문엔 `freq_shift`(반복·재등장)만 녹인다. `first_occurrence`(처음 등장)는
  나열이 자연스러워 `다른점` 섹션(= 화면의 "오늘 처음")이 담당한다.
- 꼬리 질문은 하루 최대 1건(`section_type='질문'`). 처음 등장한 사람>장소>활동
  중 하나에만 묻고, 대상이 없으면 묻지 않는다. 답변은 따로 저장하지 않는다 —
  사용자가 남기는 새 기록이 곧 답이다.
```

`README.md`의 일기 화면 설명 문장 끝에 한 문장 추가:

```markdown
처음 등장한 것은 "오늘 처음" 목록으로 모아 보여주고, 그중 하나에 대해 부담 없는 질문을 한 번 건넨다(답하면 새 기록이 된다).
```

- [ ] **Step 5: 전체 검사·커밋**

```powershell
worker\.venv\Scripts\python.exe -m pytest worker -q
worker\.venv\Scripts\python.exe -m ruff check worker
npx vitest run
npm run lint
npm run build
npx vitest run --config vitest.integration.config.mts
```

```powershell
git add evals/diary README.md supabase/README.md
git commit -m "feat(eval): 일기 골든셋에 처음 반복·메타 서술 검사

기존 eval을 통과하고도 실데이터에서 '처음' 도배와 메타 서술이 나왔다.
그 두 가지를 게이트에 넣고 문서를 갱신한다."
```

- [ ] **Step 6: 최종 보고**

`HANDOFF.md`의 "상태" 절을 갱신하고 커밋한다. **push·merge는 하지 마라.**

---

## 완료 기준
- 일기 본문에 `first_occurrence`가 들어가지 않고 "처음"이 반복되지 않는다.
- 메타 서술("기록된", "라는 단어")과 엔티티 표현 변경(`여친`→`여자친구`)이 가드레일에 막힌다.
- `다른점` 섹션에 확정 차이 전부가 남고 화면에 **"오늘 처음"** 으로 보인다.
- 처음 등장한 사람이 있으면 질문 1건이 생기고, 없으면 생기지 않는다.
- 질문 카드 링크에 **id만** 있고 질문 텍스트가 없다.
- 기록 화면이 `?section=`으로 질문을 맥락으로 보여준다.
- ruff + pytest + lint + build + vitest(단위·통합) + eval 전부 통과.

## 이번 범위 밖
- 의미 필터(prompts-draft §2) · 추출 정제(`시간` 같은 일반명사) · confidence 차등화.
- 답변↔질문 연결 저장 · 질문 여러 개 · 대화형 후속.
- 통합 테스트 격리 · 워커 CLI UTF-8.
