# 脱敏字段添加过于繁琐
# 可参考下面的脚本，定时运行即可

# 脱敏规则
# (1, '手机号'), (2, '证件号码'), (3, '银行卡'), (4, '邮箱'), (5, '金额'), (6, '其他')
masking_rule_phone='phone|mobile'
masking_rule_idno='id_number|idcard'
masking_rule_bankcardno='bank_no'
masking_rule_mail='mail|email'
masking_rule_amount='pay_money|amount'
masking_rule_others='pwd|password|user_pass'
masking_rules="$masking_rule_phone|$masking_rule_idno|$masking_rule_bankcardno|$masking_rule_mail|$masking_rule_amount|$masking_rule_others";

DIR="$( cd "$( dirname "$0"  )" && pwd  )"
cd $DIR
archery_host=127.0.0.1
archery_port=3306 
archery_user=
archery_db=archery
archery_pw=

# 获取archery所有slave实例信息
mysql -h$archery_host -P$archery_port -u$archery_user -p$archery_pw $archery_db -N -e "select 
id,instance_name,host,port 
from sql_instance  where type='slave';">instances.list

# 清空表
mysql -h$archery_host -P$archery_port -u$archery_user -p$archery_pw $archery_db -N -e "truncate table data_masking_columns;"

# 临时账号密码（因实例账号&密码为加密，写死使用）
# 此方式只适用单个实例或多个实例账号密码一致
user=
pw=

# 获取脱敏字段信息
cat instances.list|while read instance_name host port 
do 
mysql -h$host -P$port -u$user -p$pw -N -e "
SELECT CASE
         WHEN COLUMN_NAME REGEXP '$masking_rule_phone'
           THEN 1
         WHEN COLUMN_NAME REGEXP '$masking_rule_idno'
           THEN 2
         WHEN COLUMN_NAME REGEXP '$masking_rule_bankcardno'
           THEN 3
         WHEN COLUMN_NAME REGEXP '$masking_rule_mail'
           THEN 4
         WHEN COLUMN_NAME REGEXP '$masking_rule_amount'
           THEN 5
         WHEN COLUMN_NAME REGEXP '$masking_rule_others'
           THEN 6
         END AS       rule_type,
       1     AS       active,
       '$instance_id' instance_id,
       TABLE_SCHEMA   table_schema,
       TABLE_NAME     table_name,
       COLUMN_NAME    column_name,
       COLUMN_COMMENT column_comment
FROM information_schema.COLUMNS
WHERE COLUMN_NAME REGEXP '$masking_rules'
AND TABLE_SCHEMA != 'performance_schema'
AND TABLE_SCHEMA != 'information_schema';">$instance_name.txt

# 更新表数据
mysql -h$archery_host -P$archery_port -u$archery_user -p$archery_pw $archery_db -N -e "load data local infile '$instance_name.txt' replace into table data_masking_columns fields terminated by '\t' ( rule_type,active,instance_id,table_schema,table_name,column_name,column_comment);"
done