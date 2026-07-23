-- 큐를 지운다. 확장은 다른 큐가 있을 수 있어 남긴다(보수적).
select pgmq.drop_queue('memory_jobs');
