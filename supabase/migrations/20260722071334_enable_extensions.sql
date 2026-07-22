-- 실은: 벡터 검색(pgvector)과 공간 데이터(PostGIS) 확장
-- ADR-0002가 요구하는 임베딩 테이블의 전제 조건이다.
create extension if not exists vector;
create extension if not exists postgis;
