# 데이터베이스 규칙

PostgreSQL + pgvector + PostGIS. 스키마 출처: `docs/design/ERD.mermaid`.

## 원칙

- **원본(memories/assets) ↔ AI 생성물(differences/diaries) 분리.** 근거 추적 가능해야 한다.
- 모든 사용자 데이터 테이블은 `user_id` 보유 + 인덱스. 쿼리는 항상 user 스코프.
- 소프트 삭제(deleted_at)와 하드 삭제 정책을 명시. 잠금(is_locked)은 검색/일기/탐지 제외에 반영.

## 설계 리뷰 게이트 (구현 전 반드시 확정)

첫 스키마 마이그레이션 전에 아래 4가지를 명시 구조로 확정한다:

1. **차이 근거 연결** — DIFFERENCES ↔ 근거 메모를 배열이 아니라 조인 테이블 `difference_evidence(difference_id, memory_id)` 로. 다대다·추적성 확보.
2. **일기 출처** — DIARIES.source_memory_ids 배열 대신 `diary_sources(diary_id, memory_id)` 조인 테이블. 삭제 연쇄·근거 질의 용이.
3. **polymorphic EMBEDDINGS** — (target_type, target_id) 폴리모픽은 FK 무결성이 약함. target별 부분 유니크 인덱스 + 앱 레벨 검증, 또는 target별 분리 테이블 검토. 결정은 ADR로.
4. **완전 삭제 추적** — 삭제 시 DB·Storage·embedding·검색 인덱스가 모두 처리됐는지 보장하는 **deletion ledger**(deletions 테이블: target, steps_done[], completed_at). 실패 시 재개 가능.

## 마이그레이션

- 전방/후방 호환 우선. 파괴적 변경은 확장→백필→수축(expand/backfill/contract) 단계로.
- **모든 마이그레이션에 down/보상 전략** 작성. **staging에서 dry-run** 후 적용.
- 마이그레이션 적용·production 접근은 Claude 자동 실행 금지(사람이 실행).

## 인덱스·성능

- pgvector: 적절한 인덱스(HNSW/IVF)와 차원·거리 지표 명시. 검색은 user_id 선필터 후 벡터.
- 자주 조회하는 (user_id, date) 복합 인덱스. N+1 방지(조인/배치 로드).
