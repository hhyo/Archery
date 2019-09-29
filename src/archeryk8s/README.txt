1、setting:
values.yaml下配置
相关configMap的文件，settings.py，soar.yaml，analysis_slow_query.sh等
找出与mysql,redis,mongo的数据库连接

2、install:
helm install ./ --name archeryk8s --set-file ruleJson=rule.json --namespace=default
NAME:   archeryk8s
LAST DEPLOYED: Thu Sep 26 15:12:02 2019
NAMESPACE: default
STATUS: DEPLOYED

RESOURCES:
==> v1/ConfigMap
NAME                DATA  AGE
archery-config      5     2s
goinception-config  1     2s
inception-config    1     2s
my-config           1     2s

==> v1/Pod(related)
NAME                                    READY  STATUS             RESTARTS  AGE
archeryk8s-57f64bc5f6-6wpmm             0/1    Init:0/1           0         1s
archeryk8s-goinception-dd8c75b6f-bq7f7  0/1    ContainerCreating  0         1s
archeryk8s-inception-6dfcd97675-q48jh   0/1    ContainerCreating  0         1s
archeryk8s-mongo-8556d84d56-p7rlx       0/1    ContainerCreating  0         1s
archeryk8s-redis-77cc949674-scssh       0/1    ContainerCreating  0         1s
mysql-75dcc94c89-tdpwh                  0/1    ContainerCreating  0         1s

==> v1/Service
NAME                    TYPE       CLUSTER-IP     EXTERNAL-IP  PORT(S)    AGE
archeryk8s              ClusterIP  172.21.0.47    <none>       9123/TCP   1s
archeryk8s-goinception  ClusterIP  172.21.12.235  <none>       4000/TCP   2s
archeryk8s-inception    ClusterIP  172.21.8.106   <none>       6669/TCP   2s
mongo                   ClusterIP  None           <none>       27017/TCP  2s
mysql                   ClusterIP  None           <none>       3306/TCP   1s
redis                   ClusterIP  None           <none>       6379/TCP   1s

==> v1beta2/Deployment
NAME                    READY  UP-TO-DATE  AVAILABLE  AGE
archeryk8s              0/1    1           0          1s
archeryk8s-goinception  0/1    1           0          1s
archeryk8s-inception    0/1    1           0          1s
archeryk8s-mongo        0/1    1           0          1s
archeryk8s-redis        0/1    1           0          1s
mysql                   0/1    1           0          1s


NOTES:
1. Get the application URL by running these commands:
  export POD_NAME=$(kubectl get pods --namespace default -l "app.kubernetes.io/name=archeryk8s,app.kubernetes.io/instance=archeryk8s" -o jsonpath="{.items[0].metadata.name}")
  echo "Visit http://127.0.0.1:9123 to use your application"
  kubectl port-forward $POD_NAME 9123:9123

3、run:
kubectl exec -it archeryk8s-xxxx bash
/////////////////////////////////////
source /opt/venv4archery/bin/activate
python3 manage.py makemigrations sql  
python3 manage.py migrate 

# 数据初始化
python3 manage.py loaddata initial_data.json

# 创建管理用户
python3 manage.py createsuperuser

4、visit:
kubectl port-forward pods/archery-xxxxxx 9123:9123

