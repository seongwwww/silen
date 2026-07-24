# 엔티티 통계 차이 검출(detector) 설계 스펙

> 상태: 확정(브레인스토밍 승인). 다음 단계: 구현 계획(writing-plans).
> 핵심 원칙: **탐지=통계, 서술=LLM.** 이 기능은 통계·규칙만 다룬다. LLM 없음.

## 1. 목적·경계

쌓인 `memory_entities`(person·place·activity·thing 언급)에서 **결정적 통계 규칙**으로
"평소와 다른 점"을 찾아 `differences`(status=`candidate`)를 채운다. 이 신호가 이후
의미필터·서술 LLM에 넘어가 일기·차이 카드가 된다.

**경계:** detector는 "이 엔티티가 평소와 다르게 나타났나"만 판정한다. **왜 그랬는지,
어떤 의미인지는 만들지 않는다**(그건 서술 LLM, 그것도 검증된 차이만 담백하게). 탐지에
LLM을 절대 쓰지 않는다.

## 2. 입력 재료의 현재 상태

- ✅ `entities` / `memory_entities` — 존재. 엔티티 언급이 쌓임.
- ⚠️ `signals`(steps/sleep/screen/checkin) — 테이블만 있고 **비어 있음**(센서 opt-in 미구현).
  → **z-score는 이번 범위 밖**(돌릴 데이터 없음).
- ✅ `differences` / `difference_evidence` — 존재. 단 `differences`에 멱등용 자연키 없음 → 추가.
- `detection_method` enum: `zscore | first_occurrence | freq_shift | pattern`.
- `category` enum: `오늘의다른점 | 성취 | 감정전환 | 패턴`.
- `differences.date`는 하루 단위 → 탐지는 **사용자 로컬 자정 경계**로 메모를 버킷팅.

## 3. 탐지 규칙 (2종, 엔티티당 하루 단위)

`detect_day(user_id, date)`는 그날(사용자 로컬) 언급된 각 엔티티를 다음 중 **정확히 하나**로
분류한다(상호 배타 — 첫 등장이면 반복일 수 없다):

### 3.1 first_occurrence
- 조건: 그 엔티티가 **오늘 이전 전체 이력에서 등장 기록이 전무**하고 오늘 등장.
- 의미: "처음 간 카페", "새 노래", "처음 만난 사람".
- `description`(사람용 아님): `이 <entity_type> 첫 등장`.

### 3.2 freq_shift
- 전제: 이전 등장 이력이 있다(= first_occurrence 아님). 최근 **28일 창**에서 반복 신호가 있을 때만.
- **연속(streak):** 오늘 포함 **2일 이상 연속**(사용자 로컬 날짜) 등장 → "이틀째/3일째".
  - `description`: `최근 <n>일 연속 등장`.
- **재등장(re-emergence):** 28일 창 안에 등장 이력이 있으나 직전 **7일 이상 공백** 후 오늘 다시 → "그 노래 또".
  - `description`: `<gap>일 만에 재등장(최근 28일 내)`.
- 위 둘 다 아니면(산발적 등장) **차이 없음** — 오탐 억제.

### 3.3 튜닝 상수
- 연속 임계 = 2일, 재등장 공백 = 7일, 창 = 28일.
- 이 상수들은 **골든 픽스처(단위 테스트)로 검증·튜닝**한다. 하드코딩하되 한곳(상수 모듈)에 모은다.

### 3.4 빈 날·평범한 날
- 오늘 엔티티가 없거나 모두 산발적이면 **differences 0건**. 억지 생성 금지(testing.md 필수 시나리오).

## 4. 데이터·스키마 변경

### 4.1 differences.entity_id 추가 (마이그레이션)
- `differences`에 **nullable `entity_id`** 컬럼 추가:
  `entity_id uuid references public.entities(id) on delete set null`.
- **`ON DELETE SET NULL`** (CASCADE 아님): 엔티티가 삭제돼도 difference를 하드 삭제하지 않는다.
  사용자의 `status`(confirmed/dismissed) 판단을 보존하고, 근거 소실 시 무효화는 stale 메커니즘의
  몫이다(ADR-0002: "근거 훼손 시 삭제가 아니라 stale"). **근거 소실 staling 자체는 삭제 원장
  기능의 범위이며 이 기능에서 구현하지 않는다.**
- entity 기반 method(first_occurrence·freq_shift)만 값을 채운다. 미래 zscore/pattern은 NULL.

### 4.2 멱등 자연키 (마이그레이션)
- **부분 unique 인덱스**:
  `unique (user_id, date, entity_id, detection_method) where entity_id is not null`.
- 재실행이 같은 (사용자, 날짜, 엔티티, 방법) 차이를 중복 생성하지 않는다(upsert).

### 4.3 채우는 값
- `category = '오늘의다른점'` (두 method 공통).
- `status = 'candidate'`, `evidence_state = 'intact'`.
- `confidence` = 신호 세기 기반 결정값(예: 연속 길이·공백 크기를 0~1로 정규화). 결정적, 난수 없음.
- `description` = 위 통계 근거 문자열(사람에게 직접 노출 안 함).
- `dimension` = 엔티티 식별 보조 텍스트(예: `<entity_type>`). 식별의 유일 출처는 entity_id.

### 4.4 근거 연결
- `difference_evidence`에 **그날 그 엔티티를 언급한 메모(들)**를 연결(다대다). 삭제 역추적·evidence 질의용.

### 4.5 up/down
- 마이그레이션은 up/down을 같은 커밋에. down은 컬럼·인덱스 제거.

## 5. 아키텍처 (워커 3계층)

두 자산 경계 유지: 앱은 관여 안 함. 워커가 큐/스케줄로 구동(트리거는 아래 유예).

### 5.1 경계(task) — `detect_day(user_id, date)`
- 진입점. 저장소로 재료를 읽고, 서비스로 규칙을 적용하고, 저장소로 결과를 쓴다.
- **실제 스케줄 트리거(사용자 로컬 자정 후 일 배치, 타임존별)는 이번 범위 밖.** 추출 기능이
  프로덕션 주기 실행을 유예했던 것과 동일. 호출 가능한 서비스로 만들고 배선은 다음 기능에서.

### 5.2 서비스(순수) — `worker/src/silen_worker/detection/service.py`
- 입력: 엔티티별 등장 날짜 집합(예: `dict[entity_id, set[date]]`)과 대상 날짜.
- 출력: `DetectedDifference` 목록(entity_id, method, description, confidence, evidence memory_ids).
- **DB·LLM·프레임워크를 모른다.** 규칙(3절)만. **테스트를 여기 집중.**

### 5.3 저장소 — `worker/src/silen_worker/db.py` 확장
- `fetch_entity_occurrences(conn, user_id, up_to_date, window_days)`:
  사용자의 엔티티 등장을 (entity_id, 로컬 날짜)로 반환. **user_id 강제**, `is_locked`·`deleted_at` 제외.
  first_occurrence 판정을 위해 "이전 등장 존재 여부"는 창 밖 전체 이력도 확인(존재성 질의).
- `upsert_difference(...)` + `link_difference_evidence(...)`: 4.2 자연키로 멱등 upsert.

### 5.4 하루 경계 유틸 (worker판 `lib/time`)
- `users.timezone` + Python `zoneinfo`로 `memories.captured_at`(항상 존재) → 사용자 로컬 날짜로 변환.
- 단일 유틸 모듈에 격리. 전날 메모가 오늘 차이에 새지 않도록 경계 테스트 필수.

## 6. 테스트 (DoD = lint + typecheck + unit + integration)

### 6.1 단위 (DB·LLM 없음, 결정적)
순수 규칙을 합성 시계열로:
- first_occurrence: 이력 없는 엔티티만 첫 등장으로.
- freq_shift 연속: 2일·3일 연속 검출, 1일(오늘만)은 미검출.
- freq_shift 재등장: 공백 7일 이상만 검출, 6일 이하는 미검출.
- 산발적 등장 → 미검출.
- **빈 날 → 0건**(억지 생성 안 함).
- 상호 배타: 첫 등장 엔티티가 freq_shift로도 뜨지 않음.

### 6.2 통합 (실 DB)
- memory_entities 시드 → `detect_day`가 differences + difference_evidence 기록.
- **멱등**: 재실행이 중복 레코드 안 만듦.
- **잠금·삭제 제외**: `is_locked`/`deleted_at` 메모는 탐지에서 빠짐.
- **타임존 경계**: 사용자 tz에서 전날 늦은 메모가 오늘 차이에 안 샘.
- **user 스코프 격리**: 타 사용자 엔티티가 절대 안 섞임.

### 6.3 eval
- **해당 없음.** 순수 통계라 LLM eval 게이트 없음(testing.md: detector 통계는 결정적 unit).
  golden은 6.1의 단위 픽스처가 대신한다.

## 7. 이번 범위 밖
- z-score(signals 비어 있음) · pattern-corr(상관) · 감정 전환(emotions).
- 의미필터/차이 서술/일기 생성(LLM).
- **스케줄 트리거**(일 배치 구동) · baselines 테이블 적재(온더플라이 계산으로 충분).
- 근거 소실 시 difference **staling**(삭제 원장 기능 소관).
- 유저 확정(맞아요/아니에요) UI.

## 8. 주요 결정 요약
- **엔티티 2종만**(first_occurrence·freq_shift). z-score는 데이터 부재로 유예.
- **하루 단위 배치** `detect_day(user_id, date)`. 순수·결정적·테스트 주도.
- **freq_shift = 28일 창**, first_occurrence = 전체 이력. baselines 테이블 미사용(온더플라이).
- **differences.entity_id FK 추가**(`ON DELETE SET NULL`) + 부분 unique로 멱등.
- 하루 경계는 사용자 로컬 자정(users.timezone), 워커에서 단일 유틸로 계산.
