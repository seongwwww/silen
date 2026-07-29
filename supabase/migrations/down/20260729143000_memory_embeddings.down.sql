revoke execute on function public.poll_recall(uuid) from authenticated;
revoke execute on function public.request_recall(uuid, text) from authenticated;
drop function if exists public.poll_recall(uuid);
drop function if exists public.request_recall(uuid, text);

drop trigger if exists memories_sync_embedding_searchability on public.memories;
drop function if exists public.sync_memory_embedding_searchability();

drop table if exists public.memory_embeddings;

alter table public.memories
  drop constraint if exists memories_id_user_unique;
