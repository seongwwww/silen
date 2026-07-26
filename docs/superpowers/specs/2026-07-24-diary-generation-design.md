# 일기 생성(diary generation) 설계 스펙

> 상태: 확정(브레인스토밍 승인). 다음 단계: 구현 계획(writing-plans).
> 핵심 원칙: **탐지=통계, 서술=LLM.** LLM은 **메모에 있는 사실만** 하루 이야기로 엮는다.
> 없는 장면·대사·감정·인과 창작 금지. 평범한 날은 평범하게(prompts-draft §4).

## 1. 목적·경계

그날의 메모와 사용자가 확인한(confirmed) 차이를 **하나의 담백한 하루 일기**로 엮어
`diaries`에 저장한다. 홈/밤 일기 화면에 쓰인다.

**경계:** 일기는 검증된 재료(메모 원문 + 확정 차이)를 문장화만 한다. 차이를 찾지도(detector),
없는 사실을 만들지도 않는다. 죄책감·과잉해석·자기계발 금지.

## 2. 입력

- **메모**: 그날(사용자 로컬 자정 경계, `time.local_date_for`) 비잠금·비삭제 메모의
  `raw_text`·`captured_at`. 시간순.
- **confirmed 차이**: 그날 `status='confirmed'` 차이 + `difference_narrations.headline`
  (LEFT JOIN — headline 없으면 `differences.description`로 폴백).
- **감정 입력 없음(MVP)**: EMOTIONS 테이블은 아직 미적재(감정 분석은 과잉해석 위험으로 유예된
  결정). 일기는 raw_text + 확정 차이만으로 쓴다. 감정 승격 방지는 eval이 검증.

**프라이버시:** 일기는 메모 `raw_text`(본문)를 Vertex로 전송한다 — 하루를 서술하므로 불가피.
**이는 신규 위험이 아니다**: 엔티티 추출이 이미 동일하게 `raw_text`를 Vertex로 보낸다(수용된
무학습 흐름). 다만 본문·일기 텍스트를 **로그·APM·예외에는 남기지 않는다**(backend.md).

## 3. 출력·저장 (Structured Output)

LLM 출력: `{ one_line, body, used_memory_ids, used_difference_ids }`.

- **`diaries`**: `generated_text = body`, `status='draft'`, `date`, `user_id`.
  **unique(user_id, date)로 하루 1건 보장.** `style_profile`은 담백 프리셋 기록.
- **`diary_sections`**: `[오늘의한문장 = one_line, 본문 = body]` + used 차이마다
  `다른점(difference_id, content = 그 차이의 headline)`.
- **`diary_sources`**: `used_memory_ids` → 메모 근거 조인(출처 추적).
- **스키마 변경 없음** — 기존 diaries/diary_sections/diary_sources 재사용(RLS·grant 이미 있음).

## 4. 멱등·재생성 (backend.md firm rule)

- `generate_diary(conn, user_id, date, force=False) -> str | None`.
- **하루 1건 보장**: `diaries` unique(user_id, date).
- **자동 재생성 금지**: 이미 일기가 있으면 `force=False`는 **no-op**(기존 diary_id 반환).
  늦은 메모가 와도 자동으로 다시 만들지 않는다.
- **명시적 "다시 만들기"만**: `force=True`는 재생성해 덮어쓴다 — **단 `status='draft'`일 때만.**
  `status`가 `edited`/`confirmed`(유저가 손댄 것)면 force여도 보존하고 no-op(유저 말이 이긴다).
- **빈 날**: 그날 메모가 **0개면 일기를 만들지 않는다**(`None` 반환). 메모가 있으면 확정
  차이가 없어도 평범한 일기를 만든다("억지 생성 안 함" — 빈 생성 vs 평범한 생성 구분).

## 5. 가드레일 (근거 정합 중심)

자유 산문이라 결정적 검사는 **근거 추적**에 집중하고, 검증 어려운 부분은 eval에 위임한다:

1. **근거 정합**: `used_memory_ids ⊆ 입력 메모 ids`, `used_difference_ids ⊆ 입력 confirmed ids`.
   입력 밖 id를 참조하면 폐기(환각 참조).
2. **비어있지 않음**: 메모가 입력됐고 body가 비어있지 않으면 `used_memory_ids`도 비어있지 않아야 한다.
3. **조언·응원·인과 블록리스트**: narration의 `FORBIDDEN_PHRASES` 재사용. 통계·사실에 없는
   인과·자기계발·응원 0.
4. **스키마 밖 텍스트·빈 필드 거부.**
5. 통과 못 하면 **저장 안 함**.
6. **환각(입력 밖 사실)·감정 승격**은 결정적으로 완벽 검증 불가 → **eval 골든셋이 측정**
   (추출·서술 eval과 동일 철학: 모델 raw 출력 기준).

## 6. 아키텍처 (워커 3계층, narration 패턴 재사용)

### 6.1 경계 — `generate_diary(conn, user_id, date, force=False)`
- 조회 → 생성 → 가드레일 → 저장. 반환: diary id, 또는 None(빈 날/보호된 기존 diary/가드레일 탈락).
- **diary_time 스케줄 트리거 배선은 범위 밖**(호출 가능 함수, detector·narration과 동일 유예).

### 6.2 서비스(순수) — `worker/src/silen_worker/diary/service.py`
- 프롬프트 조립(메모+확정차이 → 프롬프트) + 가드레일(§5). `DiaryWriter` 포트 주입.
- 입력 dataclass `DiaryInput`(date, memories[], differences[]), 출력 dataclass
  `Diary`(one_line, body, used_memory_ids, used_difference_ids). DB·프레임워크 모름. **테스트 집중.**

### 6.3 저장소 — `worker/src/silen_worker/db.py` 확장
- `fetch_diary_inputs(conn, user_id, date, tz)` — 그날 메모 + confirmed 차이(+narration headline).
  **user_id 강제**, 잠금·삭제 제외. 하루 경계는 `time.local_date_for`.
- `fetch_existing_diary(conn, user_id, date)` — 멱등/보호 판정용(status 포함).
- `upsert_diary` + `replace_diary_sections` + `replace_diary_sources` — 멱등 저장(force 시
  기존 sections/sources를 지우고 다시 씀). 하루 1건.

### 6.4 LLM — `worker/src/silen_worker/diary/gemini.py`
- Vertex ADC 재사용, 구조화 출력 스키마(one_line·body·used_memory_ids·used_difference_ids),
  "번역자" 프롬프트(§4 규칙: 사실만·평범하면 평범하게·감정 승격 금지·담백 톤).

## 7. 테스트 (DoD = lint + typecheck + unit + integration + eval)

### 7.1 단위 (DB·LLM 없음, 스텁)
- 가드레일: used_ids ⊆ 입력 통과 / 입력 밖 id 폐기 / body 있는데 used_memory 빈 것 폐기 /
  조언·인과 폐기 / 빈 출력 폐기.
- 프롬프트 조립: 메모·확정차이가 프롬프트에 포함.

### 7.2 통합 (실 DB)
- 스텁 DiaryWriter로 generate_diary → diaries+sections+sources 저장, used 차이의 다른점 섹션.
- **하루 1건 멱등**: 재호출(force=False)이 no-op(중복 없음, 같은 diary_id).
- **force 재생성**: draft를 덮어씀(sections/sources 교체).
- **유저 편집 보호**: status='edited'/'confirmed'면 force여도 보존.
- **빈 날**: 메모 0 → None, diary 미생성. 메모 있고 차이 0 → 평범한 일기 생성.
- **user 스코프 격리**: 타 사용자 메모·차이 안 섞임.
- **삭제 연쇄**: diary 삭제 시 sections/sources cascade.

### 7.3 eval (ai-evals 골든셋, 실 Vertex, CI 게이트)
- 환각(입력 메모 밖 사실 0) · 감정 승격 없음 · 조언·인과 0 · 근거 정합(used ⊆ 입력) ·
  **평범한 날 억지 특별화 안 함**(필수) · 톤 담백 · 단정 금지. 모델 raw 측정.

## 8. 범위 밖
- 톤 프리셋·pre_instruction·대화형 톤 수정(§5) · 후속 질문(§6) · 회고 RAG(§7) · 주간 리포트(§8).
- diary_time 스케줄 트리거 배선 · 감정(EMOTIONS) 입력 · 프론트 일기 UI(#9).

## 9. 주요 결정 요약
- **생성만, 담백 톤 고정.** 톤 프리셋·대화형 수정 유예.
- **입력 = 그날 메모(raw_text) + confirmed 차이(+narration headline).** 감정 미적재라 제외.
- **저장 = generated_text + diary_sections(오늘의한문장·본문·다른점) + diary_sources.** 스키마 변경 없음.
- **하루 1건 멱등·자동 재생성 금지.** force는 draft만 덮어씀, 유저 편집 보존. 빈 날(메모 0)은 미생성.
- **가드레일 = 근거 정합(used ⊆ 입력) + 블록리스트**, 나머지는 eval. 본문 전송은 추출과 동일 수용 흐름.
