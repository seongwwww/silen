-- 비동기 큐. Next(적재)·Python 워커(소비)가 DB로만 통신한다(backend.md).
-- pgmq는 같은 Postgres 안에 있어 적재가 메모 insert와 같은 트랜잭션에 묶인다.
create extension if not exists pgmq;

-- 메모 처리 잡 큐. 메시지는 {memory_id, user_id}.
select pgmq.create('memory_jobs');
