## FAQ
### 错误日志地址
```
/downloads/log/archery.log
docker logs archery
```

### 页面样式显示异常
- 如果是runserver/debug.sh启动
    1. 因为settings里面关闭了debug，即DEBUG = False，需要在启动命令后面增加 --insecure
- 如果是nginx+gunicorn/startup.sh启动
    1. 是因为nginx的静态资源配置不正确，无法加载样式

        ```
        location /static {
                      alias /archery/static; #此处指向settings.py配置项STATIC_ROOT目录的绝对路径，用于nginx收集静态资源，一般默认为archery按照目录下的static目录
                    }
        ```
### 无法登录（确认用户名和密码正确）
- 检查用户is_active字段是否为1
### SQL上线相关
- 实例不显示数据库
    1. archery会默认过滤一些系统和测试数据库，过滤列表为`'information_schema', 'performance_schema', 'mysql', 'test', 'sys'`
### 检测SQL报错的几种情况
#### The backup dbname is too long
- 主库配置的连接信息过长，Inception生成备份时需要依靠连接信息创建备份数据库，可使用ip或者cname别名缩短连接名信息
#### invalid source infomation
- inception用来审核的账号，密码不能包含*
#### Incorrect database name ''**
- inception检查不支持子查询
#### Invalid remote backup information**
- inception无法连接备份库
### 无法生成回滚语句
- 检查配置文件里面inception相关配置
- 检查inception审核用户和备份用户权限，权限参考
    ```
    — inception备份用户
    GRANT SELECT, INSERT, CREATE ON *.* TO 'inception_bak'
    — inception审核用户（主库配置用户，如果要使用会话管理需要赋予SUPER权限，如果需要使用OSC，请额外配置权限）
    GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, DROP, ALTER,REPLICATION CLIENT,REPLICATION SLAVE ON *.* TO 'inception'
    — archery在线查询用户（从库配置用户）
    GRANT SELECT ON *.* TO 'archery_read'
    ```
- 检查binlog是否开启，并且格式需要为ROW，binlog_row_image为FULL
- 检查DML的表是否存在主键
- 检查语句是否有影响数据
- 检查备份库是否开启autocommit
- 关联更新不会生成备份
### 在线查询报错
- 语句包含mysql关键字，可关闭inception的关键字检测
- 提示语和inception相关，可关闭QUERY_CHECK校验
### 脱敏查询规则未生效
- 检查是否开启了脱敏配置
- 检查脱敏字段是否命中（是否区分大小写，实例名称和从库名称是否一致）
- 检查脱敏规则的正则表达式是否可以匹配到数据，无法匹配的会返回原结果
- 检查是否关闭了QUERY_CHECK参数，导致inception无法解析的语句未脱敏直接返回结果
### 慢日志不显示
- 检查脚本内的配置，hostname和实例配置表中的内容是否保持一致
- 检查慢日志收集表mysql_slow_query_review_history是否存在记录，并且hostname_max是否和实例配置的host:port一致
