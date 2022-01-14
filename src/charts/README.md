# Archery Kubernetes Helm 部署文档 

## 1. 获取依赖 

helm dependency update

## 2. 替换mysql、redis、archery登录密码

### 2.1 mysql
执行以下命令，执行前将${your mysql password}替换为想要设置的mysql密码。
`grep -rn "MYSQL_ROOT_PASSWORD" *|awk -F: '{print $1}'|uniq|xargs sed -i s/MYSQL_ROOT_PASSWORD/${your mysql password}/g`

### 2.2 redis
执行以下命令，执行前将${your redis password}替换为想要设置的redis密码。
`grep -rn "REDIS_PASSWORD" *|awk -F: '{print $1}'|uniq|xargs sed -i s/REDIS_PASSWORD/${your redis password}/g`

### 2.3 archery默认admin登录密码
执行以下命令，执行前将${your archery password}替换为想要设置的archery密码。
`grep -rn "ARCHERY_ADMIN_PASSWORD" *|awk -F: '{print $1}'|uniq|xargs sed -i s/ARCHERY_ADMIN_PASSWORD/${your archery password}/g`

## 3. 更改mysql持久化配置

mysql的存储持久化，请查看values.yaml的方法进行配置。

## 4. LDAP设置

如需启用LDAP，修改value.yaml里comfigmap下settings.py 内相关内容。

## 5. 访问方式

5.1 本机访问 kubectl port-forward pods/archery-xxxxxx 9123:9123 
5.2 集群外访问 将svc配置为nodePort或loadBalance，或开启ingress

默认用户名: admin
密码为2.3中设置的密码
