#!/bin/bash
# 인사카드 수정(/hr/cards/<id>/edit)에 필요한 열 권한. 팀 저장소에서는 scripts/migrate_hr_card_edit.py 를 DB 마다 따로 실행해야 해서
# 새로 만든 DB 에서는 수정이 500(UPDATE denied)이 된다. 새 DB 를 만들 때 함께 적용한다. (팀 grants.sql 이 고쳐지면 중복이지만 무해)
set -euo pipefail
mysql -uroot -p"$MYSQL_ROOT_PASSWORD" <<SQL
GRANT UPDATE (name, dept, title, ext, emp_no, hire_date, annual_days) ON \`nexus\`.employees TO 'nexus_app'@'%';
GRANT UPDATE (display_name) ON \`nexus\`.users TO 'nexus_app'@'%';
GRANT UPDATE (name, dept, title, ext, emp_no, hire_date, annual_days) ON \`nexus_test\`.employees TO 'nexus_app'@'%';
GRANT UPDATE (display_name) ON \`nexus_test\`.users TO 'nexus_app'@'%';
FLUSH PRIVILEGES;
SQL
