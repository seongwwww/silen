# ADR-0002 설계 스펙 — 스키마 설계 리뷰 게이트 4항목

- 날짜: 2026-07-22
- 관련: `.claude/rules/database.md`(설계 리뷰 게이트), `.claude/rules/privacy.md`, `docs/decisions/ADR-0001-stack-and-workflow.md`, `docs/design/ERD.mermaid`
- 상태: 설계 확정 (구현 계획 대기)

## 1. 배경

ADR-0001의 후속 항목으로 `database.md`가 "첫 스키마 마이그레이션 전에 확정"하라고 지정한 4가지를 결정한다.

1. 차이 근거 연결 — `difference_evidence` 조인 테이블
2. 일기 출처 — `diary_sources` 조인 테이블
3. polymorphic `EMBEDDINGS` 무결성
4. 완전 삭제 추적 — deletion ledger

현재 `ERD.mermaid`는 `DIARIES.source_memory_ids` 배열과 `(target_type, target_id)` 폴리모픽 `EMBEDDINGS`를 그대로 두고 있어 위 게이트를 통과하지 못한 상태다.

## 2. 결정 요약

| # | 항목 | 결정 |
|---|------|------|
| 1 | 차이 근거 | `difference_evidence` 조인 테이블 |
| 2 | 일기 출처 | `diary_sources` 조인 테이블, `source_memory_ids` 배열 제거 |
| 3 | 임베딩 | 타입별 3테이블 + 원본 계열 UNION 뷰 |
| 4 | 삭제 | 유예기간 없는 즉시 완전 삭제, ledger로 단계 추적 |
| 5 | 파생물 처리 | baseline은 무효화 후 재구축, difference는 무효화만(재생성 없음), diary는 불변, 주간 리포트는 스냅샷 대신 참조 |
| 6 | 동의 철회 | 인용된 일기를 함께 지울지 사용자에게 질문 |

---

## 3. 근거 조인 테이블

```sql
CREATE TABLE difference_evidence (
  difference_id uuid NOT NULL REFERENCES differences(id) ON DELETE CASCADE,
  memory_id     uuid NOT NULL REFERENCES memories(id)    ON DELETE CASCADE,
  PRIMARY KEY (difference_id, memory_id)
);

CREATE TABLE diary_sources (
  diary_id  uuid NOT NULL REFERENCES diaries(id)   ON DELETE CASCADE,
  memory_id uuid NOT NULL REFERENCES memories(id)  ON DELETE CASCADE,
  PRIMARY KEY (diary_id, memory_id)
);

CREATE INDEX ON difference_evidence (memory_id);   -- 메모 → 파생물 역방향 조회
CREATE INDEX ON diary_sources (memory_id);
```

`DIARIES.source_memory_ids` 배열 컬럼은 제거한다.

역방향 인덱스가 필요한 이유: 삭제 파이프라인이 "이 메모가 근거로 쓰인 difference/diary"를 찾아야 한다. 이게 삭제 완전성의 핵심 질의다.

---

## 4. 임베딩 — 타입별 분리

### 스키마

```sql
CREATE TABLE memory_embeddings (
  id uuid PRIMARY KEY,
  user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  memory_id uuid NOT NULL UNIQUE REFERENCES memories(id) ON DELETE CASCADE,
  embedding vector(N) NOT NULL,
  model text NOT NULL,
  is_searchable boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now()
);
-- asset_embeddings (asset_id), diary_embeddings (diary_id) 동일 구조
```

### 검색 뷰

```sql
CREATE VIEW source_embeddings AS
  SELECT 'memory'::text AS src_type, memory_id AS src_id, user_id, embedding, is_searchable
    FROM memory_embeddings
  UNION ALL
  SELECT 'asset', asset_id, user_id, embedding, is_searchable
    FROM asset_embeddings;
```

`diary_embeddings`는 뷰에 넣지 않는다. 회고 검색은 "실제 기록만 인용"이 원칙이고, 일기는 AI 생성물이라 근거 카드에 올라갈 대상이 아니다. 일기 검색이 필요해지면 별도 경로로 조회한다.

### 설계 근거

- **FK NOT NULL + ON DELETE CASCADE** — 원본이 사라지면 벡터가 DB 차원에서 함께 사라진다. 고아 벡터가 구조적으로 불가능해지므로, 삭제 누락이 애플리케이션 버그로 발생할 여지가 없다. 폴리모픽을 버린 유일하고 결정적인 이유다.
- **`user_id` 비정규화** — `privacy.md`의 "모든 벡터 질의에 user_id 선필터"를 조인 없이 강제한다. 교차 사용자 노출은 심각 결함이므로 필터를 벡터와 같은 행에 둔다.
- **`is_searchable` 비정규화** — `is_locked` / `deleted_at` 확인을 위해 `memories`를 조인하면 벡터 인덱스를 못 탄다. 트리거로 동기화해 필터를 임베딩 행에 붙인다.

**동기화는 asset까지 연쇄해야 한다.** `assets`는 `memories`의 자식이므로 기억을 잠그면 그 사진의 OCR 임베딩도 검색에서 빠져야 한다. `memories.is_locked` 변경 시 `memory_embeddings`만 갱신하면 **잠근 기억의 사진 텍스트가 검색에 계속 잡힌다.**

```
memories.is_locked / deleted_at 변경
  ├─▶ memory_embeddings.is_searchable
  └─▶ assets (해당 memory_id) ─▶ asset_embeddings.is_searchable
```

`asset_embeddings`는 자기 부모 `assets`를 통해 조상 `memories`의 상태를 물려받는다. 트리거는 `memories` 한 곳에 걸고 두 방향을 모두 갱신한다.

### 제약

- `memory_embeddings`와 `asset_embeddings`는 **같은 모델·같은 차원**이어야 UNION 유사도 비교가 성립한다. 모델 교체 시 두 테이블을 함께 재생성한다. `diary_embeddings`는 뷰 밖이라 독립적이다.
- 인덱스: 각 테이블에 HNSW(`vector_cosine_ops`) + `(user_id)` btree. `ORDER BY embedding <=> $1 LIMIT k`는 각 브랜치의 인덱스가 정렬 출력을 주므로 Merge Append로 밀리는 것을 기대하나, **구현 시 `EXPLAIN`으로 실제 계획을 확인한다**(가정이지 보장이 아님).

---

## 5. 삭제 — deletion ledger

### 정책: 유예기간 없음

soft delete와 hard delete 사이에 휴지통을 두지 않는다. `deleted_at`은 "복구 대기"가 아니라 **삭제 파이프라인 진행 중 모든 읽기 경로에서 제외하는 tombstone**이며, ledger가 완료되면 행 자체가 사라진다.

근거: "지우면 정말 지워진다"가 제품 약속이고, 유예기간을 두면 그 기간 동안 검색·탐지·일기·회고 모든 경로에 제외 필터를 빠짐없이 걸어야 하는데 한 곳만 놓쳐도 삭제한 기억이 일기에 등장한다.

대가: 오조작 복구가 불가능하다. UI에서 "되돌릴 수 없음"을 명시하고 내보내기 경로를 안내해야 한다.

### 테이블

```sql
CREATE TABLE deletions (
  id uuid PRIMARY KEY,
  user_id uuid NOT NULL,          -- users FK 없음. 아래 "ledger는 대상보다 오래 산다" 참조
  trigger text NOT NULL,          -- memory | consent_revoke | account
  target_type text NOT NULL,
  target_id uuid,
  cascade_diaries boolean,        -- 사용자 응답. NULL = 미응답
  status text NOT NULL,           -- awaiting_user | running | completed | failed
  steps_done text[] NOT NULL DEFAULT '{}',
  attempts int NOT NULL DEFAULT 0,
  last_error text,
  created_at timestamptz NOT NULL DEFAULT now(),
  completed_at timestamptz
);

-- 진행 중인 삭제는 대상당 하나. 중복 요청이 ledger를 복제하지 않는다
CREATE UNIQUE INDEX deletions_active_target
  ON deletions (target_type, target_id)
  WHERE status <> 'completed';
```

**`user_id`에 `users` FK를 걸지 않는다.** 계정 삭제 시 `db_hard_delete`가 `users` 행을 지우면 CASCADE로 ledger가 함께 사라져, **삭제가 끝나기도 전에 진행 상태를 잃는다.** 부분 실패 시 재개가 불가능해지므로 ledger는 삭제 대상보다 오래 살아야 한다. 완료된 ledger의 보존 기간은 운영 정책으로 따로 정한다.

**중복 방지 제약**은 `backend.md`의 "자연키로 upsert" 요구를 스키마로 강제한다. 이게 없으면 사용자가 삭제 버튼을 두 번 눌렀을 때 ledger 행이 두 개 생기고 같은 단계가 경쟁 실행된다.

### 실행

**동기 (요청 안에서)** — `deleted_at` tombstone 설정 + `is_searchable = false`. 이 시점부터 검색·탐지·일기·회고 모든 경로에서 즉시 제외된다.

**비동기 워커 (단계별, 각 단계 멱등, `steps_done`으로 재개)**

| 순서 | 단계 | 내용 |
|---|---|---|
| 1 | `search_index` | 외부 검색 색인에서 제거 |
| 2 | `derived` | 파생물 처리 (6절) |
| 3 | `storage` | Supabase Storage 파일 삭제 |
| 4 | `db_hard_delete` | 행 제거. FK CASCADE로 embeddings·조인 테이블 연쇄 |

**순서가 중요하다**: `storage`가 `db_hard_delete`보다 앞서야 한다. 행을 먼저 지우면 `assets.file_url`을 잃어 어떤 파일을 지워야 할지 알 수 없게 된다.

**멱등성** — 각 단계는 재실행해도 안전해야 한다(delete if exists). 재시도가 중복 작업이나 오류를 만들지 않는다.

**실패** — 재시도 상한 초과 시 `status = 'failed'` + 사용자에게 "삭제가 완료되지 않았습니다" 고지 + 재시도 경로 제공. 조용히 삼키지 않는다.

**트리거 3종** 모두 같은 ledger를 쓴다: 기억 1건 삭제 / 동의 철회 / 계정 전체 삭제.

---

## 6. 파생물 처리 — 캐시와 산출물의 구분

삭제가 파생물에 미치는 영향은 대상의 성격에 따라 다르게 처리한다.

### BASELINES = 캐시 → 무효화 후 재구축

남은 기록으로 언제든 다시 계산되는 롤링 통계(7d/28d/dow)이며 사용자에게 보이는 산출물이 아니다. 재계산하지 않으면 지운 데이터의 영향이 평균값에 계속 남아 "파생 신호까지 삭제"를 어긴다.

→ 해당 dimension의 baseline을 삭제하고, 다음 탐지 잡이 남은 데이터로 다시 세운다. 이것은 재생성이 아니라 캐시 재구축이다.

**baseline 부재 시 탐지 잡의 동작**: baseline이 없으면 탐지 잡은 **실패하지 않고 먼저 재계산한 뒤 진행한다**(cache miss 처리). baseline은 언제든 원본에서 유도 가능하므로 부재가 오류 상태가 아니다. 실패로 처리하면 삭제 직후의 탐지가 데드레터로 빠지고, 건너뛰면 그날의 차이를 영구히 잃는다.

### DIFFERENCES = 산출물 → 무효화만, 재생성 없음

근거 메모가 하나라도 삭제되면 해당 difference를 **stale로 표시**한다. 삭제하지 않고, 재탐지하지도 않는다.

```sql
ALTER TABLE differences
  ADD COLUMN evidence_state text NOT NULL DEFAULT 'intact',  -- intact | stale
  ADD COLUMN staled_at timestamptz;
```

`stale` 전환 시 `description`(= 탐지 상세)을 **비운다**. `prompts-draft.md`가 보여주듯 이 필드는 `"최근 2주 평균 19:20 → 오늘 18:40"` 같은 순수 통계값이라 사용자 기록 본문은 섞이지 않지만, `"오늘 18:40"`이라는 값 자체가 지운 메모에서 유래한 파생값이므로 남기면 `privacy.md`에 걸린다.

남는 것: `date`, `dimension`, `category`, 그리고 **사용자가 눌러둔 `status`([맞아요]/[아니에요])**. 사용자의 판단 이력은 보존되고, 지운 기억의 내용은 남지 않는다.

**자동 재생성을 하지 않는 이유**:
- `backend.md`가 이미 "늦은 메모 → 명시적 다시 만들기만, 자동 재생성 금지"를 정했다. 늦게 온 메모로도 자동 재생성을 안 하는데 지워진 메모 때문에 하는 것은 일관되지 않는다.
- 사용자가 눌러둔 `status`가 리셋된다. 판단을 임의로 지우는 셈이다.
- "지웠는데 비슷한 게 또 떴다"는 삭제 의도를 배신한다.
- 과거 날짜를 건드리면 그 날 일기·주간 리포트까지 도미노로 흔들린다.

감수하는 비용: 남은 근거만으로도 성립했을 차이를 잃을 수 있다. "의무가 아니라 선물" 제품이므로 놓쳐도 괜찮은 범위로 판단한다. 사용자가 원하면 해당 날짜를 수동으로 "다시 찾기" 할 수 있다.

### DIARIES = 확정된 과거 → 불변

이미 생성된 일기 본문은 건드리지 않는다. `diary_sources`의 끊어진 링크만 정리된다. 일기는 사용자가 읽고 수정까지 한 결과물이며, 임의로 지우면 사용자의 기억을 훼손한다.

### WEEKLY_REPORTS = 스냅샷 금지 → 참조로 전환

`WEEKLY_REPORTS.highlights`가 difference 내용을 `jsonb`로 **복사해 보관하면 삭제 방어선 밖에 사본이 생긴다.** difference를 stale 처리하고 `description`을 파기해도 지운 기억의 파생값이 리포트 안에 그대로 남는다.

→ highlights를 스냅샷이 아니라 **참조**로 바꾼다. 이 ADR이 `source_memory_ids` 배열에 적용한 것과 같은 처리다.

```sql
CREATE TABLE weekly_report_highlights (
  report_id     uuid NOT NULL REFERENCES weekly_reports(id) ON DELETE CASCADE,
  difference_id uuid NOT NULL REFERENCES differences(id)     ON DELETE CASCADE,
  slot text NOT NULL,        -- 가장많이한것 | 처음한것 | 감정순간
  rank int NOT NULL,
  PRIMARY KEY (report_id, difference_id)
);
```

리포트는 읽는 시점에 difference를 조회해 렌더링하며, **3중 방어의 2번(소비 시점 `evidence_state = 'intact'` 필터)이 그대로 적용된다.** 별도 삭제 단계가 필요 없어진다.

대가: stale된 항목이 과거 리포트에서 빠져 리포트가 처음 봤을 때와 달라진다. "과거는 그대로, 미래로는 안 흐른다"와 엄밀히는 어긋나지만, 지운 기억의 파생값을 남기는 것보다 낫다고 판단한다. 리포트가 비면 해당 슬롯을 조용히 생략한다.

`highlights` `jsonb` 컬럼은 제거한다. 통계 요약처럼 difference에서 유도되지 않는 값이 필요하면 그때 별도 컬럼으로 추가한다.

### stale 표시의 3중 방어

주기 잡만으로는 삭제 직후~다음 주기 사이에 일기 생성 잡이 아직 표시되지 않은 difference를 소비할 수 있다. 지운 기억이 그날 밤 일기에 등장하는 시나리오다. 따라서:

1. **ledger `derived` 단계** — 영향받은 difference를 찾아 `evidence_state = 'stale'` + `description` 파기. `difference_evidence` 행의 물리적 제거는 이후 `db_hard_delete`의 FK CASCADE가 처리하므로, 이 단계는 **CASCADE가 링크를 지우기 전에** 대상을 식별해야 한다(단계 순서가 2 → 4인 이유)
2. **소비 시점 검증** — 일기 생성·주간 리포트·회고는 `evidence_state = 'intact'`만 조회한다. 조건 한 줄이라 비용이 없고 지연 창이 원천적으로 사라진다
3. **주기 sweeper** — 1이 실패했거나 누락된 건을 보정하는 방어선

---

## 7. 일기 연쇄 삭제 질문

동의를 철회하거나 기억을 삭제할 때, 그것이 근거로 쓰인 일기가 있으면 사용자에게 묻는다.

- **묻는 조건** — `diary_sources`에 실제로 걸린 일기가 있을 때만. 대부분의 삭제는 프롬프트 없이 지나간다.
- **기본 선택** — "일기 남기기". 파괴적 기본값을 피한다.
- **ledger 상태** — 응답 전까지 `awaiting_user`. 응답이 오면 `cascade_diaries`를 기록하고 `running`으로 전환한다.
- **문구** — 무엇이 지워지고 무엇이 남는지 구체적으로 안내한다.

서비스가 임의로 일기를 지우지도, 임의로 남기지도 않는다.

---

## 8. ERD 변경 요약

| 대상 | 변경 |
|------|------|
| `DIARIES` | `source_memory_ids` 배열 제거 |
| `DIFFERENCES` | `evidence_state`, `staled_at` 추가 |
| `EMBEDDINGS` | 제거 → `MEMORY_EMBEDDINGS` / `ASSET_EMBEDDINGS` / `DIARY_EMBEDDINGS` 로 분리 |
| `WEEKLY_REPORTS` | `highlights` jsonb 제거 → 조인 테이블 참조로 전환 |
| 신규 | `DIFFERENCE_EVIDENCE`, `DIARY_SOURCES`, `WEEKLY_REPORT_HIGHLIGHTS`, `DELETIONS` |

관계선도 이에 맞춰 갱신한다(`MEMORIES ||--o{ DIARIES : "source_memory_ids"` → 조인 테이블 경유).

---

## 9. 테스트 요구사항

`testing.md`의 필수 회귀 시나리오에 대응한다.

**Unit**
- ledger 각 단계의 멱등성 — 같은 단계를 두 번 실행해도 결과가 같다
- `evidence_state` 전환 로직 — 근거 1건 삭제 시 stale, `description` 비워짐

**Integration**
- 삭제 후 DB·Storage·pgvector·검색 인덱스에 **잔존 없음**
- 중단된 ledger가 `steps_done`부터 **재개**되고 완료된다
- `storage` 단계 실패 시 `db_hard_delete`가 실행되지 않는다(파일 URL 유실 방지)
- `stale` difference가 일기 생성·주간 리포트·회고에 **유입되지 않음**
- 타 사용자 embedding이 `source_embeddings` 뷰 조회에 **절대 안 섞임**
- `is_locked` 전환 시 `is_searchable`이 동기화되고 검색에서 빠짐 — **memory뿐 아니라 그 memory에 딸린 asset의 OCR 임베딩까지** 함께 빠지는지 확인
- **계정 삭제 중 `users` 행이 사라져도 ledger가 살아남아** 남은 단계를 재개한다
- 삭제 요청을 두 번 보내도 ledger 행은 하나이며 단계가 중복 실행되지 않는다
- baseline이 없는 상태에서 탐지 잡이 돌면 실패·건너뛰기 없이 **재계산 후 진행**한다
- 동의 철회 시 `awaiting_user`에서 대기하고, 응답에 따라 일기가 남거나 지워진다
- 근거 메모 삭제 후에도 기존 일기 본문은 **변경되지 않음**

**마이그레이션**
- 모든 마이그레이션에 down/보상 전략을 함께 작성한다
- staging에서 dry-run 후 적용한다. 적용은 사람이 실행한다

---

## 10. 미결 사항

- **임베딩 차원 N과 모델 선택** — 이 스펙의 범위 밖. 임베딩 구현(W6) 시점에 결정하고 필요하면 별도 ADR로 남긴다. 그때까지 `vector(N)`은 플레이스홀더다.
- **외부 검색 인덱스의 실체** — `search_index` 단계가 Postgres FTS인지 별도 검색 엔진인지는 하이브리드 검색 설계 시 확정한다. ledger 단계 자체는 어느 쪽이든 동일하다.
