# dmSQLAlchemy

此包为Python的SQLAlchemy包连接达梦数据库的适配框架，当前版本为 `1.4.40` ，API详见安装目录下的 `《DM8_dmPython使用手册》` ，目前用于适配1.4版本的SQLAlchemy。

## ChangeLogs

#### dmSQLAlchemy v1.4.41(2025-01-21)

* 修复了连接句柄使用 `IPV6` 格式主机名无法连接到数据库的问题

#### dmSQLAlchemy v1.4.40(2025-01-20)

* 改进了执行策略，当前获取表与序列信息将不再从 `sysobjects` 系统表获取以减少数据量

#### dmSQLAlchemy v1.4.39(2025-01-16)

* 修复了列名或表名为大小写共存的情况下，执行插入语句报错的问题

* 修复了当列名或表名为保留字的情况下，执行插入语句报错的问题
* 变更了主键策略，当前版本下，integer类型的主键将不再自动添加 `自增` 属性

#### dmSQLAlchemy v1.4.38(2024.12.10)

* 修复了如果安装dmSQLAlchemy时没安装SQLAlchemy会安装最新版的问题
* 修复了特定情况下 `fetch` 语句拼写错误
* 修正了绑定策略，当前 `boolean` 类型将在数据库中被绑定为 `smallint` 类型
* 修复了将 `rowid` 当做 `inserted_primary_key` 错误返回的问题

#### dmSQLAlchemy v1.4.37(2024.10.31)

* 修复了部分类型无法对应到 `SQLAlchemy` 支持类型的问题，当前类型支持详见 `《DM8_dmPython使用手册》`  5.3节类型映射

* 修复了自增列自增值设置报错问题

* 修复了当列带有 `Computed` 属性时未正确创建列的问题

* 修复了向blob数据段执行插入操作，插入 `NONE`  时实际插入 `'NONE'`  的问题


#### dmSQLAlchemy v1.4.36(2024.08.27)

* 修复了单条语句执行时长最大为30秒的问题，现执行语句默认将不再限制执行时长
* 新增了对于SQLAlchemy的 `array` 类型的支持
* 修复了在低于 `1.4.38` 版本上执行 `SELECT` 时报错的问题

#### dmSQLAlchemy v1.4.35(2023.01.06)

* 修复了主键为自增列的情况下执行插入操作报错的问题