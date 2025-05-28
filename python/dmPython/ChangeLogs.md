## dmPython

此包为Python连接达梦数据库的原生驱动。dmPython whl包下载地址：https://pypi.org/project/dmPythpn/。使用方法详见安装目录下的《DM8_dmPython 使用手册》

## Extensions

-   支持sqlalchemy和django框架

## Change Logs

**dmPython v2.5.22(2025-2-25)**

- 兼容了Oracle在Number类型scale大于0并且为整数时，会输出其小数形式的处理方式

**dmPython v2.5.21(2025-2-19)**

- 增加了对dmPython.CURSOR类型绑定参数执行的支持

**dmPython v2.5.20(2025-1-20)**

- 修复了使用ipv6地址连接达梦数据库失败的问题。
- 修复了当输入参数列中有大字段类型是，获取输出参数失败的问题。

**dmPython v2.5.19(2025-1-6)**

- 修复了bit列值为null时，returning into输出参数报错的问题

**dmPython v2.5.18(2024-12-31)**

- 增加了连接参数dmsvc_path,指定dm_svc.conf路径

**dmPython v2.5.17(2024-12-26)**

- 更改了密码策略，不允许使用默认密码

**dmPython v2.5.16(2024-11-22)**

- 修复了returning into输出参数类型为blob时，会导致程序奔溃的问题
- 修复了dmPython读取bfile有父目录引用时，报错不正常的问题
- 增加了dmPython安装时可以使用drivers目录作为DM_HOME目录的支持

**dmPython v2.5.15(2024-11-20)**

- 修复了dmPython删除不存在的bfile目录时，会导致程序奔溃的问题
- 修复了dmPython的callproc和callfunc函数中的sql注入问题
- 兼容了dm7版本的dpi

**dmPython v2.5.14(2024-11-19)**

- 修复了当update和delete语句影响行数为0时，returing into输出参数会导致程序奔溃的问题

**dmPython v2.5.13(2024-11-14)**

- 修复了DM_HOME的搜索逻辑，会优先在当前目录搜索需要的动态库，然后才会去父目录搜索
- 增加了在使用繁体中文时，使用不支持繁体中文编码的时的报错

**dmPython v2.5.12(2024-11-13)**

- 修复了dmPython使用编码方式PG_ISO_8859_11，PG_KOI8R、PG_SQL_ASCII连接数据库报错的问题

**dmPython v2.5.11(2024-9-20)**

- 修复了绑定参数输入blobl或clob数据时，程序奔溃的问题
- 消除了Python3.12版本安装dmPython时的警告

**dmPython v2.5.10(2024-9-20)**

- 修复了returning into输出参数返回多行结果时，无法输出空数据的问题

**dmPython v2.5.9(2024-8-29)**

- 增加了对多租户连接参数的支持
- 修复了游标读取bfile数据后，退出程序时报错资源清理出错的问题

**dmPython v2.5.8(2024-7-3)**

- 修复了多线程下更新blob和clob数据会发生阻塞的问题
- 增加了对nls_numeric_characters参数的支持，支持以字符串格式返回非标准时间类型
- 修复了超长数据插入时的字符串截断问题

**dmPython v2.5.7(2024-4-15)**

- 适配dpi prepare本地化的修复，调整了一些函数的使用顺序
- 增加了returning into输出参数支持返回多行结果的支持

**dmPython v2.5.6(2023-12-7)**

- 修复了获取变长字符串类型时，相关描述信息不准确的问题

**dmPython v2.5.5(2023-11-8)**

- 增加了对Python3.12版本的支持

**dmPython v2.5.4(2023-10-25)**

- 修复了数据库推荐类型为varchar，传入参数类型为int，数据类型转换失败的错误