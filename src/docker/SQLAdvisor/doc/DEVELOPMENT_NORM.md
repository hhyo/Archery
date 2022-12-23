### SQLAdvisor开发规范    

#### 1.代码中出现的数字等，尽量使用见名知义的宏定义   

- 下面的代码片段是不被推荐的： 
  
```
if (id == 0) {
 //todo sth.
} else {
 //todo sth.
}
```    

- 下面的代码片段是被推荐的：  
 
```
#define TK_COMMENT 0

if (id == TK_COMMENT) {
 //todo sth.
} else {
 //todo sth.
}
```   

#### 2.commit log书写规范

```
本次提交的描述信息。（issue #no）
```

例如：

```
git commit -m "bugfix: 修复 动态修改权重不生效。(issue #12)"
git commit -m "feature: 新增 标记tag，可进行从库流量配置功能。(issue #13)"
```
