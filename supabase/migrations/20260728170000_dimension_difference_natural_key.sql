-- entity_id가 없는 감정 차이도 재실행 시 한 행으로 수렴한다.
create unique index differences_dimension_natural_key
  on public.differences (user_id, date, dimension, detection_method)
  where entity_id is null;
