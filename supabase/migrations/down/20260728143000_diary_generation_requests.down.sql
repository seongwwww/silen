revoke execute on function public.request_diary_generation(date) from authenticated;
drop function if exists public.request_diary_generation(date);
drop table if exists public.diary_generation_requests;
