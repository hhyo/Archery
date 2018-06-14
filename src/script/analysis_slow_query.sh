#!/bin/bash
DIR="$( cd "$( dirname "$0"  )" && pwd  )"
cd $DIR

#config monitor database server 收集日志  配置archer数据库的连接地址
monitor_db_host="127.0.0.1"
monitor_db_port=3306
monitor_db_user="root"
monitor_db_password="123456"
monitor_db_database="archer"

#config mysql server 被监控机
mysql_host=$mysql_host # 和archer主库配置保持一致
mysql_port=$mysql_port # 和archer主库配置保持一致

#config slowqury 被监控机慢日志位置
slowquery_file="/home/mysql/log_slow.log"
pt_query_digest="/usr/bin/pt-query-digest"

#config server_id
hostname="${mysql_host}:${mysql_port}" # 用于archer做筛选

#获取上次分析时间，初始化时请删除last_analysis_time_$hostname文件，可分析全部日志数据
if [ -s last_analysis_time_$hostname ]; then
    last_analysis_time=`cat last_analysis_time_$hostname`
else
    last_analysis_time='0000-00-00-00 00:00:00'
fi

#collect mysql slowquery log into monitor database
#RDS需要增加--no-version-check选项
$pt_query_digest \
--user=$monitor_db_user --password=$monitor_db_password --port=$monitor_db_port \
--review h=$monitor_db_host,D=$monitor_db_database,t=mysql_slow_query_review  \
--history h=$monitor_db_host,D=$monitor_db_database,t=mysql_slow_query_review_history  \
--no-report --limit=100% --charset=utf8 \
--since "$last_analysis_time" \
--filter="\$event->{Bytes} = length(\$event->{arg}) and \$event->{hostname}=\"$hostname\"  and \$event->{client}=\$event->{ip} " \
$slowquery_file > /tmp/analysis_slow_query.log

echo `date +"%Y-%m-%d %H:%M:%S"`>last_analysis_time_$hostname
