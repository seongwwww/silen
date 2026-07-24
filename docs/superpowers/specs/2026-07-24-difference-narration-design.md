# 차이 서술(difference narration) 설계 스펙

> 상태: 확정(브레인스토밍 승인). 다음 단계: 구현 계획(writing-plans).
> 핵심 원칙: **탐지=통계, 서술=LLM.** LLM은 **번역자이지 발견자가 아니다** — 검증된 차이를
> 담백한 한국어로만 옮긴다. 없는 사실·감정·인과·조언 창작 금지(prompts-draft §1).

## 1. 목적·경계

detector가 만든 `differences`(status=`candidate`)를 **사람이 읽는 카드 텍스트**로 옮긴다.
홈/"오늘의 다른 점" 카드에 쓰일 headline·body·근거 한 줄을 생성한다.

**경계:** 서술은 이미 검증된 차이를 문장화만 한다. **차이를 찾지도, 의미를 지어내지도 않는다.**
차이 판정은 detector(통계), 이 기능은 그 결과의 번역만.

## 2. 서술 입력·출력

### 2.1 입력 — 구조화 사실만 (메모 본문 미전송)
- `entities.name` (예: "김밥", "그 카페")
- `entities.entity_type` (person·place·activity·thing)
- `differences.detection_method` (first_occurrence·freq_shift)
- `differences.description` (통계 근거, 예: "최근 3일 연속 등장")
- `differences.date`

메모 `raw_text`(본문)는 **전송하지 않는다.** 프라이버시 표면 최소화 + 서사·감정 환각 유혹 제거.
카드는 통계적 차이에 관한 것이라 구조화 사실만으로 충분하다.

### 2.2 출력 — Structured Output 스키마 강제
- `headline` — 12자 내외. 무엇이 달랐는지 담백하게.
- `body` — 1~2문장. 평소 대비 사실만. 이유를 지어내지 않는다.
- `evidence_text` — "왜 찾았는지" 사람 말 한 줄(통계 용어 순화).

스키마 밖 텍스트는 거부한다.

### 2.3 톤
- MVP는 **담백 고정.** 톤 3층(따뜻 등 프리셋·주문·수정)은 일기 기능 소관 → 범위 밖.

## 3. 가드레일 (핵심 방어선)

서술은 자유 산문이라 환각 검증이 추출보다 어렵다. 입력이 구조화 사실뿐이라 허용 사실
표면이 작다는 점을 활용한다. **결정적 검사**(단위 테스트로 고정):

1. **엔티티명 정합** — 출력(headline+body)에 입력 `entities.name`이 실재해야 한다(카드가 그 차이를 가리키는지).
2. **조언·응원·인과 블록리스트 미포함** — "때문에"·"덕분에"·"해보세요"·"어때요"·"화이팅"·"추천"
   등 금지 표현 목록(상수 한곳, 튜닝 가능). 통계에 없는 인과·자기계발·응원 0(ai-evals.md).
3. **길이 상한** — headline·body·evidence_text 각 상한 초과 시 폐기.
4. **스키마 밖 텍스트 거부** — Structured Output으로 강제.

**통과 못 하면 저장하지 않는다**(추출 guardrail 철학과 동일 — 결정적 방어선).
근거 없는 문장 0% 목표.

## 4. 저장 — `difference_narrations` 테이블 (마이그레이션)

탐지(통계)와 서술(프롬프트)을 **행으로 분리**한다. detector 변경과 프롬프트 변경을 섞지
않는다는 git.md 원칙을 저장에도 반영 — 재서술이 difference 행을 건드리지 않는다.

```
create table public.difference_narrations (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users(id) on delete cascade,
  difference_id uuid not null unique references public.differences(id) on delete cascade,
  headline text not null,
  body text not null,
  evidence_text text not null,
  model text not null,
  created_at timestamptz not null default now()
);
```

- `difference_id` **unique** → 하나의 difference당 서술 1건(멱등). 재서술은 명시적 "다시 만들기"만.
- `on delete cascade` → difference 삭제 시 서술도 삭제(생성물, 근거 사라지면 함께).
- `user_id` 비정규화 → user 스코프 질의·RLS 일관.
- RLS 정책 + `authenticated`/`service_role` GRANT를 같은 마이그레이션에(supabase/README 규약).
- up/down을 같은 커밋에.

**근거 추적:** narration → difference_id → difference_evidence → memory. 출력에 difference_id 내포(추적성).

## 5. 아키텍처 (워커 3계층, 추출 패턴 재사용)

### 5.1 경계(task) — `narrate_difference(conn, difference_id)`
- 조회 → 서술 → 가드레일 → 저장. 반환: narration id 또는 None(가드레일 탈락).
- **스케줄/lazy 트리거 배선은 범위 밖.** 호출 가능한 함수만(detector·추출과 동일 유예).

### 5.2 서비스(순수) — `worker/src/silen_worker/narration/service.py`
- 프롬프트 조립(구조화 사실 → 프롬프트) + 가드레일(§3).
- LLM은 `Narrator` 포트로 주입(테스트는 스텁). DB·프레임워크 모름. **테스트 집중.**
- 입력 dataclass `NarrationInput`, 출력 dataclass `Narration`(headline·body·evidence_text).

### 5.3 저장소 — `worker/src/silen_worker/db.py` 확장
- `fetch_difference_for_narration(conn, difference_id)` — difference + 엔티티 조인. 반환에
  `user_id`·`entity_id`·`entity_name`·`entity_type`·`method`·`description`·`date` 포함.
  `evidence_state='intact'` + `entity_id is not null`만(현재 엔티티 차이만 서술 대상).
  이후 저장은 이 행에서 읽은 `user_id`를 그대로 써서 서술이 반드시 차이 소유자에 귀속되게 한다.
- `upsert_narration(conn, ...)` — difference_id 자연키로 멱등 upsert.

### 5.4 LLM — `worker/src/silen_worker/narration/gemini.py`
- Vertex AI Gemini + ADC 재사용(추출과 동일 인증·리전 `global`).
- 구조화 출력 스키마(headline·body·evidence_text) + "번역자" 전역 프롬프트(prompts-draft §1).
- 본문은 로그·예외에 남기지 않는다(입력에 본문도 없음).

## 6. 테스트 (DoD = lint + typecheck + unit + integration + eval)

### 6.1 단위 (DB·LLM 없음, 스텁)
- 가드레일: 엔티티명 없는 출력 폐기 / 조언·인과 표현 폐기 / 길이 초과 폐기 / 정상 통과.
- 프롬프트 조립: 구조화 사실이 프롬프트에 포함, 본문 미포함.

### 6.2 통합 (실 DB)
- 스텁 Narrator로 `narrate_difference` → difference_narrations 저장.
- **멱등**: 재실행이 중복 안 만듦(unique difference_id).
- **user 스코프 귀속**: 저장된 narration.user_id가 difference 소유자와 일치(교차 오염 없음).
- **삭제 연쇄**: difference 삭제 시 narration cascade 삭제.
- 가드레일 탈락 후보는 저장 안 됨.

### 6.3 eval (ai-evals 골든셋, 실 Vertex, CI 게이트)
- 환각 유혹(구조화 사실 밖 사실 창작 0)
- 감정 승격 없음(원본에 감정 없음 → 감정 언어 미추가)
- 조언·응원·인과 혼입 0
- 근거 정합(엔티티명·통계 사실만)
- 단정 금지(관찰체)
- **평범한 차이를 억지로 특별하게 만들지 않음**(필수)
- 모델 측정: 가드레일 전 raw 출력 기준(추출 eval과 동일 철학 — 가드레일이 아니라 모델을 잰다).

## 7. 범위 밖
- 의미 필터(수치 노이즈용 — z-score/signals 생길 때).
- 일기 생성(#8b, diaries·diary_sections·톤 3층).
- 톤 프리셋·수정(따뜻 등).
- 서술 스케줄/lazy 트리거 배선.
- 프론트 카드 UI(#9).

## 8. 주요 결정 요약
- **서술만.** 의미 필터·일기 생성 분리.
- **구조화 사실만 입력**(본문 미전송) — 프라이버시·환각 최소.
- **별도 difference_narrations 테이블**(1:1 unique) — 탐지↔서술 분리, 멱등.
- **가드레일 = 결정적 블록리스트 + 엔티티명 정합**, 통과분만 저장.
- Vertex ADC·구조화 출력·eval 게이트는 추출 기능 패턴 재사용.
- 톤은 담백 고정, 트리거 배선은 유예.
