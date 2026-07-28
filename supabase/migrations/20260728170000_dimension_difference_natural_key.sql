-- 엔티티 없는 zscore 감정 차이만 재실행 시 한 행으로 수렴한다.
-- 다른 entity_id null 행은 엔티티 삭제(ON DELETE SET NULL) 뒤에도 충돌하지 않는다.
create unique index differences_dimension_natural_key
  on public.differences (user_id, date, dimension, detection_method)
  where entity_id is null
    and dimension = 'emotion'
    and detection_method = 'zscore';
