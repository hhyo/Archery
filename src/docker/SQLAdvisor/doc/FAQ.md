## SQLAdvisor FAQ


> 该文档中的FAQ主要整理自SQLAdvisor用户QQ交流群(231434335)大家的交流内容，将共性的问题进行整理、积累，方便大家回顾和学习。持续更新中...


### Q1: SQLAdvisor支持哪些SQL

 insert、update、delete、select、insert select 、select join、update t1 t2 等常见SQL有支持


### Q2: SQLAdvisor有哪些需要注意的地主
 - SQL中的子查询、or条件、使用函数的条件 会忽略不处理。
 - 命令行传入sql参数时，注意sql中的双引号、反引号 都需要用\转义。建议使用配置文件形式调用


