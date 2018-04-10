#!/bin/bash

#config monitor database server 收集日志  配置archer数据库的连接地址
monitor_db_host="127.0.0.1"
monitor_db_port=3306
monitor_db_user="root"
monitor_db_password="123456"
monitor_db_database="archer"

#config mysql server 被监控机
mysql_client="/usr/local/mysql/bin/mysql"
mysql_host="127.0.0.1" # 和archer主库配置保持一致
mysql_port=3306 # 和archer主库配置保持一致
mysql_user="root"
mysql_password="123456"

#config slowqury 被监控机慢日志位置
slowquery_dir="/home/mysql/slow_log/"
slowquery_long_time=1
slowquery_file=`$mysql_client -h$mysql_host -P$mysql_port -u$mysql_user -p$mysql_password  -e "show variables like 'slow_query_log_file'"|grep log|awk '{print $2}'`
pt_query_digest="/usr/local/bin/pt-query-digest"

#config server_id
hostname="${mysql_host}:${mysql_port}" # 用于archer做筛选


#collect mysql slowquery log into monitor database
#RDS需要增加--no-version-check选项
$pt_query_digest \
--no-version-check \
--user=$monitor_db_user --password=$monitor_db_password --port=$monitor_db_port \
--review h=$monitor_db_host,D=$monitor_db_database,t=mysql_slow_query_review  \
--history h=$monitor_db_host,D=$monitor_db_database,t=mysql_slow_query_review_history  \
--no-report --limit=100% --charset=utf8 \
--filter="\$event->{Byes} = length(\$event->{arg}) and \$event->{hostname}=\"$hostname\"  and \$event->{client}=\$event->{ip} " \
$slowquery_file > /tmp/analysis_slow_query.log

##### set a new slow query log ###########
tmp_log=`$mysql_client -h$mysql_host -P$mysql_port -u$mysql_user -p$mysql_password -e "select concat('$slowquery_dir','slowquery_',date_format(now(),'%Y_%m_%d_%H_%i'),'.log');"|grep log|sed -n -e '2p'`

#config mysql slowquery
$mysql_client -h$mysql_host -P$mysql_port -u$mysql_user -p$mysql_password -e "set global slow_query_log=1;set global long_query_time=$slowquery_long_time;"
$mysql_client -h$mysql_host -P$mysql_port -u$mysql_user -p$mysql_password -e "set global slow_query_log_file = '$tmp_log'; "

#delete log before 7 days
/usr/bin/find $slowquery_dir -name 'slowquery_*' -mtime +7|xargs rm -rf ;

####END####
