1、setting: 根目录values.yaml下配置,相关configMap的文件，settings.py，soar.yaml，analysis_slow_query.sh等,找出与mysql,redis的数据库连接 charts/goinception,charts/inception目录下的values.yaml配置修改，主要与mysql连接的配置 mysql的存储持久化，请查看values.yaml的方法进行配置

2、dependency: cd charts/archeryk8s && helm dependency update

3、install: helm install ./ --name archery --namespace=default

4、visit:

i 本机访问 kubectl port-forward pods/archery-xxxxxx 9123:9123 
ii 集群外访问 将svc配置为nodePort或loadBalance，或开启ingress

默认关闭ingress，如需开启ingress，请在values.yaml设置为true，并修改ingress默认域名配置。


默认用户名：admin
默认密码：Archery2019

