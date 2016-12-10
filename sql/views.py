# coding = utf-8
import json

from django.shortcuts import render
from django.http import HttpResponse, HttpResponseRedirect
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required

from .models import users, master_config, workflow

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

def allworkflow(request):
    context = {'currentMenu':'allworkflow'}
    return render(request, 'allWorkflow.html', context)

def submitSql(request):
    context = {'currentMenu':'submitsql'}
    return render(request, 'submitSql.html', context)

