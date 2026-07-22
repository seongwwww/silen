-- 보상 전략: 확장에 의존하는 객체가 남아 있으면 실패한다(의도된 동작).
-- 강제 제거는 데이터 손실을 유발하므로 cascade를 쓰지 않는다.
drop extension if exists postgis;
drop extension if exists vector;
