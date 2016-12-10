# archer
基于inception的自动化SQL操作平台

### 主要功能
* 发起inception SQL上线，工单提交
* 工单DBA人工审核、sql执行
* 历史工单展示
* 回滚数据展示
* 提交工单发邮件功能
* OSC打通
* 主库集群配置

### 安装步骤：
1. 安装python3：
tar -xzvf Python-3.4.1.tar.gz && cd Python-3.4.1 && ./configure --prefix=/path/to/python3 && make && make install
2. 安装django：
tar -xzvf Django-1.8.17 && cd Django-1.8.17 && python3 setup.py install
3. 启动服务：
bash startup.sh
4. 创建系统root用户（该用户可以使用django admin）：
cd archer && python3 manage.py createsuperuser
