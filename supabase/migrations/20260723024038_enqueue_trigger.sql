-- 메모가 생기면 처리 잡을 큐에 넣는다. 앱은 탐지를 모르고 트리거가
-- 결합을 대신한다(2자산이 큐+DB로만 통신). insert와 같은 트랜잭션이라
-- 메모가 커밋되면 메시지도 반드시 들어간다(유령·유실 잡 없음).
-- 본문(raw_text)은 싣지 않는다 — memory_id만. 워커가 DB에서 읽는다.
create function public.enqueue_memory_job() returns trigger
  language plpgsql
  security definer
  set search_path = ''
as $$
begin
  perform pgmq.send('memory_jobs', jsonb_build_object(
    'memory_id', new.id,
    'user_id', new.user_id
  ));
  return new;
end;
$$;

create trigger on_memory_created
  after insert on public.memories
  for each row execute function public.enqueue_memory_job();
