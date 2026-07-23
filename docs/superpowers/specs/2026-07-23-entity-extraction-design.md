# 엔티티 추출 설계 스펙 — Gemini Flash · 가드레일 · 보수적 병합

- 날짜: 2026-07-23
- 관련: `.claude/rules/ai-evals.md`, `.claude/rules/privacy.md`, `.claude/rules/backend.md`, `docs/superpowers/specs/2026-07-23-worker-pipeline-design.md`, `docs/planning/서비스_기획서.md` §6·9
- 상태: 설계 확정 (구현 계획 대기)
- 선행: 워커 파이프라인(pgmq·트리거·process_pending·스코핑)이 `main`에 병합됨.

## 1. 배경

제품 약속("놓친 차이 발견")을 지키려면 텍스트에서 **엔티티**(사람·장소·활동·사물)를 뽑아 `entities`를 채워야 한다. 그래야 first-occurrence("그 노래 또")·freq-shift("3일째 김밥") 같은 차이가 탐지 가능해진다.

엔티티 추출은 통계가 아니라 **LLM 작업**이다. 단, "탐지=통계, 서술=LLM" 경계를 지킨다 — 추출은 "차이를 찾아줘"가 아니라 "이 문장에 어떤 엔티티가 있나"를 묻는 **신호 보강**이다. 차이 판정(새로운가·반복인가)은 여전히 순수 통계(detector)의 몫이다. 이는 OCR/STT처럼 LLM으로 구조화 신호를 만드는 단계다.

이 스펙은 워커 파이프라인(A)의 "사소한 잡" 자리에 진짜 추출을 넣는다.

## 2. 결정 요약

| # | 항목 | 결정 |
|---|------|------|
| 1 | 프로바이더 | **Gemini Flash, 무학습 구성(유료 API/Vertex)**. 무료 티어 금지 |
| 2 | 추출 대상 | person·place·activity·thing 4종(사람 포함) |
| 3 | 출력 | 구조화 스키마 `[{type, name}]`. 스키마 밖 거부 |
| 4 | 가드레일 | 추출 name이 원문에 실재하는지 후검증. 없으면 폐기(환각 0%) |
| 5 | 병합 | `normalized_name` 보수적 키로 upsert. 애매하면 안 합침 |
| 6 | 삭제 완전성 | 고아 entity는 트리거로 **즉시** 삭제 |
| 7 | 멱등성 | 자연키 upsert. 재처리해도 중복 없음 |
| 8 | eval | 골든셋 1일차. CI 게이트 |
| 9 | 백필 | **미룸**. 새 메모만. 실데이터 시점에 일회성 스크립트 |

---

## 3. 흐름

```
메모 insert ──[트리거]──▶ pgmq ──▶ 워커 process_pending
                                        │
                     메모 텍스트 조회(user 스코프) → Gemini Flash 추출
                                        │
                 구조화 출력 → 가드레일(원문 대조) → 보수적 병합
                                        │
                     entities · memory_entities upsert (멱등)
```

A에서 세운 배관을 그대로 쓴다. `process_pending`이 소비하는 잡의 내용이 "조회 후 반환"에서 "조회 → 추출 → 저장"으로 바뀐다.

## 4. 프로바이더 — Gemini Flash (무학습 필수)

### 왜 이 조건이 협상 불가인가

privacy.md·기획서의 **"AI 학습에 유저 데이터 미사용"**은 Gemini에서 구성에 따라 갈린다:
- 무료 AI Studio 티어 — 입력을 모델 개선에 쓸 수 있음 → **사용 불가**
- 유료 Gemini API / Vertex AI — 학습에 쓰지 않음 → **이것만 사용**

개인 일기를, 이제 타인 이름까지 담아 외부로 보내므로 무학습 구성은 필수다.

### 구성
- 모델 **Gemini Flash**(저렴·빠름). 엔티티 추출은 짧은 텍스트에서 명사 뽑기라 소형 모델로 충분(ai-evals.md "필터·게이트는 소형 모델").
- API 키는 **워커 환경변수**(`GEMINI_API_KEY` 등). 코드·로그·커밋·큐 메시지에 싣지 않는다.
- 외부 호출이므로 타임아웃·재시도(지수 백오프)·비용 상한 인지(backend.md). 실패는 pgmq visibility timeout으로 재시도, 상한 초과 시 데드레터.
- **본문을 로그·에러 추적에 남기지 않는다.** Gemini에 보내는 것은 처리용이며, 우리 로그·APM에는 memory_id·엔티티 카운트만.

---

## 5. 추출 대상·출력

### 엔티티 4종
`person`·`place`·`activity`·`thing`. 사람 포함(프라이버시 경계는 §7·8에서 다룸).

### 구조화 출력 스키마
Gemini의 구조화 출력으로 다음만 받는다:

```json
{ "entities": [ { "type": "person|place|activity|thing", "name": "string" } ] }
```

스키마 밖 텍스트·설명·해석은 거부한다. name은 **원문에 나타난 형태의 기본형**(조사 제거: "민수랑" → "민수").

### 프롬프트 원칙(ai-evals.md)
- "이 텍스트에 등장하는 사람·장소·활동·사물을 뽑아라. 텍스트에 없는 것을 지어내지 마라. 추론·해석·감정 판단 금지."
- 빈 텍스트·엔티티 없는 텍스트 → 빈 배열. 억지 생성 금지.

---

## 6. 가드레일 — 환각 0%

ai-evals.md는 "근거 없는 사실 비율 0%"를 요구한다. 추출은 타인 이름을 저장하므로 특히 중요하다.

- **원문 대조**: 추출된 각 `name`이 메모 원문에 실제로 등장하는지 후검증한다(부분 문자열 매칭 — "민수"는 "민수랑 점심"에 포함). 없으면 그 엔티티를 **폐기**한다.
- LLM이 확장·추론한 이름은 원문에 없으므로 자동 탈락한다(예: "스벅"만 있는데 "스타벅스"를 반환 → 폐기). 우리는 **추출자이지 해석자가 아니다.**
- 이 후검증은 순수 코드(문자열)라 비용이 없다. eval 골든셋이 회귀를 막는다.

---

## 7. 보수적 병합 (기획서 §6)

### normalized_name
같은 사용자 안에서 같은 엔티티를 재사용하기 위한 **보수적** 매칭 키. 공백 제거·소문자화(라틴) 등 안전한 정규화만. **과병합 금지** — 애매하면 별개로 둔다(예: "김민수"와 "민수"는 자동 병합하지 않는다).

### 절차
- `(user_id, entity_type, normalized_name)`로 조회. 있으면 그 entity 재사용, 없으면 생성.
- `memory_entities`에 `(memory_id, entity_id, relation_type)`로 링크. `confirmed_by_user = false`(자동 추출).
- 유저 확정 병합 UI는 후속(프론트). 지금은 자동 병합 결과를 미확정 상태로 저장만.

`relation_type`은 entity_type에 따라 기본 매핑(person→met, place→visited, activity→did). thing은 매핑이 애매하므로 이번 범위에서 thing은 `did`로 두거나 링크 relation_type을 nullable 허용 여부를 구현 시 확정(스키마 확인 필요).

---

## 8. 삭제 완전성 — 고아 entity 즉시 삭제

타인 이름을 저장하므로 삭제가 완전해야 한다(privacy.md). 우리는 삭제 완전성을 늘 **구조로** 강제해왔다.

- `memory_entities`는 memories에 FK CASCADE → 메모 삭제 시 링크가 사라진다.
- 그러나 entity(민수) 자체는 다른 메모에서도 쓰일 수 있어 CASCADE로 안 지워진다. **어디서도 안 쓰이면(고아) 남으면 안 된다.**
- **`memory_entities` AFTER DELETE 트리거**: 삭제된 링크의 entity가 남은 `memory_entities`·`relations`에서 더는 참조되지 않으면 그 entity를 즉시 삭제한다. 메모 삭제·계정 삭제·미래 경로 모두에 균일하게 걸린다.
- 계정 삭제는 `entities.user_id` FK CASCADE로도 지워지므로 이중 안전.

이 트리거가 "지웠는데 타인 이름이 남는" 창을 원천 차단한다. 삭제 파이프라인 워커가 없어도 작동한다.

---

## 9. 멱등성

재처리(같은 메시지 두 번)해도 중복이 생기면 안 된다(backend.md).

- entity: `(user_id, entity_type, normalized_name)` 유니크 → upsert(on conflict do nothing/update).
- memory_entities: `(memory_id, entity_id, relation_type)` PK → upsert.
- 같은 메모를 다시 추출하면 같은 엔티티·링크로 수렴한다.

**주의**: 재추출 시 이전에 뽑혔다가 이번에 안 뽑힌 링크를 지울지(동기화) vs 추가만 할지. 이 스펙은 **추가만** 한다(프롬프트·모델은 안정적이라 결과가 크게 흔들리지 않음 가정). 명시적 재추출로 인한 링크 정리는 후속.

---

## 10. eval 골든셋 (1일차, ai-evals.md)

`evals/`에 입력 텍스트 → 기대 엔티티 픽스처를 둔다. CI 게이트. 프롬프트·모델 변경 시 자동 실행(Hook 권장).

필수 케이스:
- **환각 유혹** — 텍스트에 없는 이름을 안 뽑음(가드레일 검증)
- **빈 텍스트·엔티티 없음** — 빈 배열, 억지 생성 X
- **한국어 조사·띄어쓰기** — "민수랑"→"민수", "그 카페에서"→"카페"(또는 "그 카페")
- **보수적 병합** — 과병합 X("김민수"≠"민수")
- **4종 분류** — person/place/activity/thing 정확도
- **본인 데이터만** — 추출 결과가 메모 소유자에게만 귀속(워커 스코핑)

측정 지표: 환각율·근거정합율·false positive율(ai-evals.md). eval은 실제 Gemini 호출(계약 목이 아니라 실모델). 비용 인지.

---

## 11. 코드 배치 (backend.md 워커 3계층)

- **경계** `worker/src/silen_worker/tasks/process.py` — 잡 내용이 추출로 바뀜(조회 → 추출 → 저장).
- **서비스** `worker/src/silen_worker/extraction/` — 프롬프트·구조화 파싱·가드레일(원문 대조)·병합 규칙(normalized_name). LLM 클라이언트를 인터페이스로 주입받아 순수 로직을 테스트(가드레일·병합은 Gemini 없이 단위 테스트).
- **저장소** `worker/src/silen_worker/db.py` — entity·memory_entities upsert(user 스코프 강제). Gemini 클라이언트는 저장소 뒤 인터페이스로 숨겨 테스트에서 스텁 교체(testing.md).

## 12. 테스트

### 단위 (Gemini 없이)
- 가드레일: 원문에 없는 name 폐기, 있는 name 통과.
- 병합: normalized_name 보수적(과병합 X). 기존 entity 재사용.
- 스키마 파싱: 스키마 밖 출력 거부.

### 통합 (로컬 DB)
- 메모 → 추출(스텁 LLM) → entities·memory_entities 생성.
- 멱등성: 같은 메모 두 번 추출해도 entity·링크 1건씩.
- **고아 삭제**: entity를 여러 메모가 참조 → 한 메모 삭제 시 entity 유지, 마지막 메모 삭제 시 entity 삭제(트리거 검증).
- 교차 사용자: 워커가 A의 entity를 B에 안 섞음.

### eval (실 Gemini)
- §10 골든셋. 별도 게이트.

## 13. 이번 범위 밖
- 유저 확정 병합 UI (프론트)
- detector(first-occurrence·freq-shift) — 엔티티가 쌓인 뒤(통계)
- 백필(기존 메모) — 실데이터 시점 일회성
- relations(엔티티 그래프) — 이후
- 재추출 시 링크 동기화(지금은 추가만)

## 14. 검증이 필요한 가정
- **Gemini 구조화 출력이 한국어 4종 분류에 충분한지** — eval 골든셋으로 1일차 측정. 부족하면 프롬프트 보강 또는 Pro 승급.
- **memory_entities.relation_type이 thing에 어떤 값을 받는지** — 스키마 CHECK 제약 확인. 필요 시 nullable 또는 값 추가는 별도 마이그레이션.
- **무학습 구성의 정확한 설정 경로**(유료 API vs Vertex, 데이터 거버넌스 설정) — 구현 첫 단계에서 Google 문서로 확정.
