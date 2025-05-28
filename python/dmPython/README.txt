
===========================================安装=============================================

dmPython源码依赖DM安装目录或者drivers目录(driver目录为DM的驱动目录)中提供的dpi头文件，安装前需要检查环境中是否存在DM安装或者drivers目录，并设置DM_HOME目录：
export DM_HOME=/opt/dmdbms 或者export DM_HOME=/drivers
具体路径以实际环境为准，DM_HOME路径下面必须有include目录或者dpi/include目录

在Windows操作系统下安装dmPython只需要直接执行exe文件即可。Windows操作系统下生成exe文件操作如下：
1.进入到dmPython源码所在目录（setup.py文件所在路径）
2.执行命令：python setup.py bdist_wininst
3.在dist目录下会生成相关安装文件

LINUX安装方法：
1.进入到dmPython源码所在目录（setup.py文件所在路径）
2.执行命令：python setup.py bdist_rpm
3.在dist目录下会生成相关rpm包
4.在Linux操作系统下使用rpm包安装dmPython。安装和卸载命令参考如下：
安装：rpm -ivh dmPython-2.1-7.1-py33-1.x86_64.rpm --nodeps
卸载：rpm -e dmPython-2.1-1.x86_64

windows和linux也可以直接使用源码安装，操作如下：
1.进入到dmPython源码所在目录（setup.py文件所在路径）
2.执行命令：python setup.py install


===========================================其他可能有帮助的信息=============================================

windows平台生成安装包(exe)
	python setup.py bdist_wininst

LINUX平台生成安装包（rprm）
	python setup.py bdist_rpm
	
	若安装过程中出现依赖问题，则：
	rpm -ivh file.rpm --nodeps
	
linux安装命令：
rpm -ivh dmPython-1.1-7.1-py26-1.x86_64.rpm --nodeps

linux卸载命令： 
rpm -e dmPython-1.1-1.x86_64

	
源码直接安装（不分平台）
	python setup.py install
	
64位平台安装时，需增加DM64宏：
	安装脚本setup.py中全局变量defineMacros使用defineMacros = [('DM64', None),];否则，使用defineMacros = []。
	
平台执行上述命令时，需先进行如下准备工作：
定义环境变量DM_HOME，WINDOWS平台需要将其添加到环境变量PATH中，linux则不需要：
指定为DM安装目录bin的上层目录，如DM_HOME=C:\dmdbms 或者 export DM_HOME=/opt/dmdbms


==============================》
WIN平台可能遇到如下问题：
Unable to find vcvarsall.bat

解决方案如下：
进入当前使用python安装目录中Lib/distutils，找到文件msvc9compiler.py，使用UE或者其他文本编辑器将其打开。
在文件msvc9compiler.py中找到：
vc_env = query_vcvarsall(VSERSION,plat_spec)

根据使用本机安装的VS的版本号，对应安装目录（如：C:\Program Files\Microsoft Visual Studio 10.0），则改为：
vc_env = query_vcvarsall(10,plat_spec)


==============================》
WIN平台执行import dmPython时，可能会遇到如下问题：
>>> import dmPython
Traceback (most recent call last):
  File "<stdin>", line 1, in <module>
ImportError: DLL load failed: 找不到指定的模块

此时因为dmPython找不到动态库dpi（linux为libdmdpi.so，windows为dmdpi.dll、dmdpi.lib），需要到dpi所在目录执行或者配置环境变量指向dpi所在目录；
若有安装DM，直接配置环境变量指向bin目录或者指向drivers/dpi。

linux为例：export LD_LIBRARY_PATH=/opt/dmdbms/bin或者export LD_LIBRARY_PATH=/drivers/dpi


==============================》
用户python使用过程中遇到undefined symbol:PyUnicodeUCS2_Format
此问题为编译dmPython的环境的UCS编码与执行环境不匹配导致，常见的有以下两种情况：
1.在不同的操作系统环境中编译和使用dmPython
2.编译或安装dmPython的python程序本身UCS编码与当前操作系统不一致导致
这两种情况都与dmPython源码无关，检查当前环境即可
解决：
第一种直接在同一台机子上编译和使用即可
第二种一般是使用源码安装了python，然后再用python去编译或安装dmPython，因此需要检查在使用源码安装python时，使用的编码与操作系统是否一致，源码安装python参考命令如下：
./configure --prefix=$YOUR_PATH --enable-unicode=ucs4
--enable-unicode选项指定成与操作系统一致的编码即可


	