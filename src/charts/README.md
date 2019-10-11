1、setting:
根目录values.yaml下配置,相关configMap的文件，settings.py，soar.yaml，analysis_slow_query.sh等,找出与mysql,redis的数据库连接
charts/goinception,charts/inception目录下的values.yaml配置修改，主要与mysql连接的配置
mysql的存储持久化，请查看values.yaml的方法进行配置

2、dependency:
cd charts/archeryk8s && helm dependency update

3、install:
helm install ./ --name archery --namespace=default

4、run:
kubectl exec -it archery-xxxx bash
/////////////////////////////////////
source /opt/venv4archery/bin/activate
python3 manage.py makemigrations sql
python3 manage.py migrate 
#数据初始化
python3 manage.py loaddata initial_data.json
#创建管理用户
python3 manage.py createsuperuser

5、visit:
i 本机访问
kubectl port-forward pods/archery-xxxxxx 9123:9123
ii 集群外访问
将svc配置为nodePort或loadBalance，或开启ingress

