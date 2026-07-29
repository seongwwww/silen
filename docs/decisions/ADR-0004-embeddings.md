# ADR-0004 — 메모 임베딩 저장과 검색

- 상태: 채택
- 날짜: 2026-07-29
- 관련: `docs/superpowers/plans/2026-07-29-beta-gate.md` P3

## 맥락

회고 질문을 기존 키워드 검색만으로 처리하면 같은 뜻을 다른 표현으로 쓴 기록을
찾기 어렵다. 메모 본문을 벡터로 저장하고 키워드 결과와 합쳐야 하지만, 임베딩
테이블 구조와 모델·차원은 마이그레이션에 박힌 뒤 바꾸려면 전체 재생성이 필요하다.

다음 제약을 함께 만족해야 한다.

- MVP에서 임베딩할 대상은 `memories`뿐이다.
- 모든 사용자 데이터 테이블은 `user_id`를 직접 보유하고, 검색은 사용자 범위를
  먼저 제한해야 한다.
- 잠기거나 삭제 중인 메모는 생성·검색에서 제외한다.
- 메모를 완전히 삭제하면 임베딩도 같은 트랜잭션에서 사라져야 한다.
- 한국어 검색 품질을 지원하는 현재 Vertex AI 정식 모델을 사용한다.
- 로컬 pgvector 0.8.2의 `vector` HNSW 인덱스는 최대 2,000차원까지 지원한다.

## 검토한 선택지

1. **다형 대상 테이블 `(target_type, target_id)`** — 여러 산출물을 한 테이블에
   담기 쉽지만 데이터베이스 외부 검증 없이는 대상 FK 무결성을 보장할 수 없다.
2. **메모 전용 테이블 + 3072차원 `vector`** — 모델의 전체 출력을 보존하지만
   pgvector `vector` HNSW 차원 한도를 넘으므로 계획한 인덱스를 만들 수 없다.
3. **메모 전용 테이블 + 3072차원 `halfvec`** — HNSW는 가능하지만 반정밀도 저장을
   새로 도입하고 현재 스키마 관례와 달라진다.
4. **메모 전용 테이블 + 명시적 768차원 `vector`** — Vertex AI가 지원하는
   `output_dimensionality` 축소를 사용해 저장·연산 비용과 검색 인덱스를 함께
   유지한다.

## 결정

### 모델과 벡터

- 모델: `gemini-embedding-001`
- 출력 차원: **768**
- 메모 입력 task type: `RETRIEVAL_DOCUMENT`
- 사용자 질문 task type: `RETRIEVAL_QUERY`
- 거리: cosine
- 인덱스: HNSW, `vector_cosine_ops`

`gemini-embedding-001`은 Vertex AI의 영어·다국어·코드 통합 임베딩 모델이고 전체
출력은 3072차원이다. Vertex AI가 더 작은 `output_dimensionality`를 공식 지원하므로
모든 호출에서 768을 명시한다. 차원 값은 기본값에 맡기지 않는다.

### 저장 구조

`memory_embeddings` 단일 테이블을 둔다.

- `memory_id uuid primary key`
- `user_id uuid not null`
- `embedding vector(768) not null`
- `model text not null`
- `is_searchable boolean not null`
- `created_at timestamptz not null`

`(memory_id, user_id)`는 `memories(id, user_id)`를 복합 FK로 참조하고
`on delete cascade`를 사용한다. 이를 위해 `memories(id, user_id)`에 유니크 제약을
추가한다. 이 구조는 임베딩 행의 소유자를 부모와 다르게 기록할 수 없게 하면서도
모든 벡터 질의가 `user_id`로 먼저 좁혀지게 한다.

`model`은 `gemini-embedding-001`만 허용한다. `is_searchable`은 ADR-0002에서
정한 비정규화 필드로, 부모 메모의 잠금·삭제 상태가 바뀔 때 트리거로 동기화한다.
성능용 플래그만 프라이버시 경계로 믿지 않고, RLS와 검색 쿼리에서 활성 부모 메모를
다시 확인한다. 잠금이 풀렸는데 임베딩이 없다면 같은 트리거가 기존
`memory_jobs` 큐에 메모 잡을 다시 넣는다.

RLS는 인증 사용자의 `select`만 허용하고 부모 메모 소유권을 함께 확인한다.
워커는 `service_role`만 생성·갱신·삭제할 수 있다. 메모별 행은 하나뿐이며 재처리는
upsert로 멱등하게 만든다.

### 비동기 회고 요청

저장소의 2자산 경계를 유지하려면 Next.js가 Vertex를 직접 호출해서는 안 되고,
Python 워커도 HTTP를 직접 받지 않는다. 별도 대화 테이블을 만들지 않고 기존
`memory_jobs`의 한 메시지를 짧게 사는 요청·응답 슬롯으로 재사용한다.

1. 인증된 RPC가 `auth.uid()`를 메시지의 `user_id`로 고정해 질문을 적재한다.
2. 워커가 질문 임베딩·검색·서술을 처리하고 같은 메시지를 완료 상태와 근거 ID로
   바꾸면서 원 질문을 제거한다.
3. 브라우저가 인증된 RPC로 결과를 가져가면 메시지를 즉시 삭제한다.
4. 가져가지 않은 완료·실패 메시지도 만료 뒤 워커가 삭제한다.

따라서 대화용 제품 스키마나 대화 이력은 남지 않고 새로고침하면 화면이 빈다.
큐에 머무는 동안에도 본문·질문·답변을 로그로 출력하지 않으며, 조회 RPC는 메시지의
`user_id = auth.uid()`를 확인한다.

### 생성·검색·삭제

- 엔티티 추출이 성공한 활성 메모만 임베딩한다.
- `is_locked = true` 또는 `deleted_at is not null`인 메모는 생성하지 않는다.
- 검색 SQL은 `user_id`와 활성 메모 조건을 벡터 거리 계산보다 먼저 적용한다.
- 사용자 질문은 벡터 결과와 기존 키워드 결과를 결정적으로 재정렬한다.
- 답변은 검색된 실제 메모만 근거로 삼고 근거 밖 문장이 생기면 폐기한다.
- 메모 하드 삭제 시 FK cascade가 임베딩을 함께 삭제한다. 계정 삭제도 기존 메모
  cascade를 통해 같은 경로를 따른다.
- 대화 내용은 저장하지 않는다.

## 결과

- 긍정적: FK 무결성과 사용자 선필터를 데이터 구조에 명시하고 HNSW cosine 검색을
  사용할 수 있다.
- 감수하는 비용: 3072차원 전체 출력보다 정보량이 줄 수 있다. 모델이나 차원을
  바꾸려면 별도 열/테이블로 확장하고 전체 재임베딩한 뒤 전환해야 한다.
- 운영 제약: 기존 메모 백필은 실제 Vertex 비용이 발생하므로 사람이 명시적으로
  실행한다. 서로 다른 모델·차원의 벡터를 한 인덱스에 섞지 않는다.
- 프라이버시 비용: 진행 중 회고 질문과 완료 결과가 결과 수신 또는 만료까지 기존
  큐에 잠시 존재한다. 이 메시지는 소유자 RPC 외에는 노출하지 않고 즉시 삭제한다.
- 후속 작업: 잠금 기능은 잠긴 메모를 검색·탐지·일기에서 모두 제외하는지 P5에서
  통합 검증한다.

## 근거 문서

- Vertex AI, Get text embeddings:
  https://cloud.google.com/vertex-ai/generative-ai/docs/embeddings/get-text-embeddings
- Vertex AI, Choose an embeddings task type:
  https://cloud.google.com/vertex-ai/generative-ai/docs/embeddings/task-types
- pgvector, Indexing:
  https://github.com/pgvector/pgvector#indexing
