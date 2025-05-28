## dmDjango

Django是基于Python的Web应用程序框架，dmDjango是DM提供的Django连接DM数据库的驱动，当前版本为 `2.0.3` ，API详见安装目录下的 `《DM8_dmPython使用手册》` ，目前用于适配 `1.9` 及以上， `3.0` 及以下版本的Django。

### ChangeLogs

#### dmDjango v2.0.3(2025-01-15)

* 修复了连接数据库时需要赋予连接用户 `SOI` 角色的安全问题
* 修复了当表名或者列名带单引号情况，无法正确查询到表或列信息的问题
* 修复了使用 `pip uninstall` 无法卸载包的问题
* 修复了安装时候警告未声明 `zip_safe` 的问题

#### dmDjango v2.0.2(2024-09-25)

* 修复了在Linux环境下使用Django连接DM，处理 `distinct` 和 `cast` 时，语法有误的问题
* 修复了处理数据为时间类型时绑定为 `week` 时出现错误现象

#### dmDjango v2.0.1(2024-08-09)

* 修正了代码格式，移除了冗余代码

#### dmDjango v2.0.0(2023-02-28)

* 新建框架适配包，用于兼容`1.9` 及以上， `3.0` 及以下版本的Django框架