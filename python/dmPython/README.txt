
===========================================��װ=============================================

dmPythonԴ������DM��װĿ¼����driversĿ¼(driverĿ¼ΪDM������Ŀ¼)���ṩ��dpiͷ�ļ�����װǰ��Ҫ��黷�����Ƿ����DM��װ����driversĿ¼��������DM_HOMEĿ¼��
export DM_HOME=/opt/dmdbms ����export DM_HOME=/drivers
����·����ʵ�ʻ���Ϊ׼��DM_HOME·�����������includeĿ¼����dpi/includeĿ¼

��Windows����ϵͳ�°�װdmPythonֻ��Ҫֱ��ִ��exe�ļ����ɡ�Windows����ϵͳ������exe�ļ��������£�
1.���뵽dmPythonԴ������Ŀ¼��setup.py�ļ�����·����
2.ִ�����python setup.py bdist_wininst
3.��distĿ¼�»�������ذ�װ�ļ�

LINUX��װ������
1.���뵽dmPythonԴ������Ŀ¼��setup.py�ļ�����·����
2.ִ�����python setup.py bdist_rpm
3.��distĿ¼�»��������rpm��
4.��Linux����ϵͳ��ʹ��rpm����װdmPython����װ��ж������ο����£�
��װ��rpm -ivh dmPython-2.1-7.1-py33-1.x86_64.rpm --nodeps
ж�أ�rpm -e dmPython-2.1-1.x86_64

windows��linuxҲ����ֱ��ʹ��Դ�밲װ���������£�
1.���뵽dmPythonԴ������Ŀ¼��setup.py�ļ�����·����
2.ִ�����python setup.py install


===========================================���������а�������Ϣ=============================================

windowsƽ̨���ɰ�װ��(exe)
	python setup.py bdist_wininst

LINUXƽ̨���ɰ�װ����rprm��
	python setup.py bdist_rpm
	
	����װ�����г����������⣬��
	rpm -ivh file.rpm --nodeps
	
linux��װ���
rpm -ivh dmPython-1.1-7.1-py26-1.x86_64.rpm --nodeps

linuxж����� 
rpm -e dmPython-1.1-1.x86_64

	
Դ��ֱ�Ӱ�װ������ƽ̨��
	python setup.py install
	
64λƽ̨��װʱ��������DM64�꣺
	��װ�ű�setup.py��ȫ�ֱ���defineMacrosʹ��defineMacros = [('DM64', None),];����ʹ��defineMacros = []��
	
ƽִ̨����������ʱ�����Ƚ�������׼��������
���廷������DM_HOME��WINDOWSƽ̨��Ҫ������ӵ���������PATH�У�linux����Ҫ��
ָ��ΪDM��װĿ¼bin���ϲ�Ŀ¼����DM_HOME=C:\dmdbms ���� export DM_HOME=/opt/dmdbms


==============================��
WINƽ̨���������������⣺
Unable to find vcvarsall.bat

����������£�
���뵱ǰʹ��python��װĿ¼��Lib/distutils���ҵ��ļ�msvc9compiler.py��ʹ��UE���������ı��༭������򿪡�
���ļ�msvc9compiler.py���ҵ���
vc_env = query_vcvarsall(VSERSION,plat_spec)

����ʹ�ñ�����װ��VS�İ汾�ţ���Ӧ��װĿ¼���磺C:\Program Files\Microsoft Visual Studio 10.0�������Ϊ��
vc_env = query_vcvarsall(10,plat_spec)


==============================��
WINƽִ̨��import dmPythonʱ�����ܻ������������⣺
>>> import dmPython
Traceback (most recent call last):
  File "<stdin>", line 1, in <module>
ImportError: DLL load failed: �Ҳ���ָ����ģ��

��ʱ��ΪdmPython�Ҳ�����̬��dpi��linuxΪlibdmdpi.so��windowsΪdmdpi.dll��dmdpi.lib������Ҫ��dpi����Ŀ¼ִ�л������û�������ָ��dpi����Ŀ¼��
���а�װDM��ֱ�����û�������ָ��binĿ¼����ָ��drivers/dpi��

linuxΪ����export LD_LIBRARY_PATH=/opt/dmdbms/bin����export LD_LIBRARY_PATH=/drivers/dpi


==============================��
�û�pythonʹ�ù���������undefined symbol:PyUnicodeUCS2_Format
������Ϊ����dmPython�Ļ�����UCS������ִ�л�����ƥ�䵼�£����������������������
1.�ڲ�ͬ�Ĳ���ϵͳ�����б����ʹ��dmPython
2.�����װdmPython��python������UCS�����뵱ǰ����ϵͳ��һ�µ���
�������������dmPythonԴ���޹أ���鵱ǰ��������
�����
��һ��ֱ����ͬһ̨�����ϱ����ʹ�ü���
�ڶ���һ����ʹ��Դ�밲װ��python��Ȼ������pythonȥ�����װdmPython�������Ҫ�����ʹ��Դ�밲װpythonʱ��ʹ�õı��������ϵͳ�Ƿ�һ�£�Դ�밲װpython�ο��������£�
./configure --prefix=$YOUR_PATH --enable-unicode=ucs4
--enable-unicodeѡ��ָ���������ϵͳһ�µı��뼴��


	