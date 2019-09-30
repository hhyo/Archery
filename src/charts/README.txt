1、setting:
根目录values.yaml下配置,相关configMap的文件，settings.py，soar.yaml，analysis_slow_query.sh等,找出与mysql,redis的数据库连接
charts/goinception,charts/inception目录下的values.yaml配置修改，主要与mysql连接的配置

2、dependency:
cd charts/archeryk8s && helm dependency update

3、install:
helm install ./ --name archery --set-file ruleJson=rule.json --namespace=default

4、run:
kubectl exec -it archeryk8s-xxxx bash
/////////////////////////////////////
source /opt/venv4archery/bin/activate
python3 manage.py makemigrations sql
python3 manage.py migrate 
# 数据初始化
python3 manage.py loaddata initial_data.json
# 创建管理用户
python3 manage.py createsuperuser

5、visit:
kubectl port-forward pods/archery-xxxxxx 9123:9123

