# coding = utf-8
import json

from django.shortcuts import render
from django.http import HttpResponse, HttpResponseRedirect
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required

from .models import users, master_config, workflow
from .dao import Dao

dao = Dao()

# Create your views here.
def login(request):
    return render(request, 'login.html')

def logout(request):
    if request.session.get('login_username', False):
        del request.session['login_username']
    return render(request, 'login.html')

#ajax接口，登录页面调用，用来验证用户名密码
@csrf_exempt
def authenticate(request):
    """认证机制做的非常简单，密码没有加密，各位看官自行实现，建议类似md5单向加密即可。"""
    if request.is_ajax():
        strUsername = request.POST.get('username')
        strPassword = request.POST.get('password')
    else:
        strUsername = request.POST['username']
        strPassword = request.POST['password']
    
    result = {}
    #服务端二次验证参数
    if strUsername == "" or strPassword == "" or strUsername is None or strPassword is None:
        result = {'status':2, 'msg':'登录用户名或密码为空，请重新输入!', 'data':''}

    login_user = users.objects.filter(username=strUsername, password=strPassword)
    if len(login_user) == 1:
        #return HttpResponseRedirect('/allworkflow/')
        request.session['login_username'] = strUsername
        result = {'status':0, 'msg':'ok', 'data':''}
    else:
        result = {'status':1, 'msg':'用户名或密码错误，请重新输入！', 'data':''}
    return HttpResponse(json.dumps(result), content_type='application/json')

#首页，也是查看所有SQL工单页面
def allworkflow(request):
    context = {'currentMenu':'allworkflow'}
    return render(request, 'allWorkflow.html', context)

#提交SQL的页面
def submitSql(request):
    masters = master_config.objects.all()
    if len(masters) == 0:
       context = {'errMsg': '集群数为0，可能后端数据没有配置集群'}
       return render(request, 'error.html', context) 
    
    #获取所有集群名称
    listAllClusterName = [master.cluster_name for master in masters]

    dictAllClusterDb = {}
    #每一个都首先获取主库地址在哪里
    for clusterName in listAllClusterName:
        listMasters = master_config.objects.filter(cluster_name=clusterName)
        if len(listMasters) != 1:
            context = {'errMsg': '存在两个集群名称一样的集群，请修改数据库'}
            return render(request, 'error.html', context)
        #取出该集群的名称以及连接方式，为了后面连进去获取所有databases
        masterHost = listMasters[0].master_host
        masterPort = listMasters[0].master_port
        masterUser = listMasters[0].master_user
        masterPassword = listMasters[0].master_password

        listDb = dao.getAlldbByCluster(masterHost, masterPort, masterUser, masterPassword)
        dictAllClusterDb[clusterName] = listDb

    #获取所有审核人
    reviewMen = users.objects.filter(role='审核人')
    if len(reviewMen) == 0:
       context = {'errMsg': '审核人为0，请配置审核人'}
       return render(request, 'error.html', context) 
    listAllReviewMen = [user.username for user in reviewMen]
  
    context = {'currentMenu':'submitsql', 'dictAllClusterDb':dictAllClusterDb, 'reviewMen':reviewMen}
    return render(request, 'submitSql.html', context)

#提交SQL给inception进行解析
def autoreview(request):
    return HttpResponse("aaa")

#展示SQL工单详细内容，以及可以人工审核，审核通过即可执行
def detail(request):
    return HttpResponse("bbb")

#展示回滚的SQL
def rollback(request):
    return HttpResponse("rollback")

