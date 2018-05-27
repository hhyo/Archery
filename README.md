#说明
基于archer，调整部分自需功能
## 功能功能
1. 项目组管理  
   支持自定义项目组，项目组成员之间审批流程隔离、主库配置隔离
2. 审批流程改造  
   SQL上线审核、查询权限审核接入工作流，审批流程支持多级，自主配置
3. 跳过inception执行工单  
   对于inception不支持的语法，如子查询更新，由审核人人工审核，DBA可以跳过inception直接执行，但无法生成回滚语句  
4. 快速上线其他实例  
   在工单详情可快速提交相同SQL内容到其他实例，可适用于test>beta>ga等多套环境维护的需求


## 部署
安装步骤可参考archer源项目
### 采取docker部署
archer镜像对应的是版本是:lihuanhuan
* inception镜像: https://dev.aliyun.com/detail.html?spm=5176.1972343.2.12.7b475aaaLiCfMf&repoId=142093
* archer镜像: https://dev.aliyun.com/detail.html?spm=5176.1972343.2.38.XtXtLh&repoId=142147    

