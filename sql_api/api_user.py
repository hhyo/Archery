from rest_framework import views, generics, status, permissions
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema
from .serializers import UserSerializer, UserDetailSerializer, GroupSerializer, \
    ResourceGroupSerializer, TwoFASerializer, UserAuthSerializer, TwoFAVerifySerializer, TwoFASaveSerializer
from .pagination import CustomizedPagination
from .permissions import IsOwner
from .filters import UserFilter
from django.contrib.auth.models import Group
from django.contrib.auth import authenticate, login
from django.conf import settings
from django.http import Http404
from sql.models import Users, ResourceGroup, TwoFactorAuthConfig
from common.twofa import TwoFactorAuthBase, get_authenticator


class UserList(generics.ListAPIView):
    """
    列出所有的user或者创建一个新的user
    """
    filterset_class = UserFilter
    pagination_class = CustomizedPagination
    serializer_class = UserSerializer
    queryset = Users.objects.all().order_by('id')

    @extend_schema(summary="用户清单",
                   request=UserSerializer,
                   responses={200: UserSerializer},
                   description="列出所有用户（过滤，分页）")
    def get(self, request):
        users = self.filter_queryset(self.queryset)
        page_user = self.paginate_queryset(queryset=users)
        serializer_obj = self.get_serializer(page_user, many=True)
        data = {
            'data': serializer_obj.data
        }
        return self.get_paginated_response(data)

    @extend_schema(summary="创建用户",
                   request=UserSerializer,
                   responses={201: UserSerializer},
                   description="创建一个用户")
    def post(self, request):
        serializer = UserSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserDetail(views.APIView):
    """
    用户操作
    """
    serializer_class = UserDetailSerializer

    def get_object(self, pk):
        try:
            return Users.objects.get(pk=pk)
        except Users.DoesNotExist:
            raise Http404

    @extend_schema(summary="更新用户",
                   request=UserDetailSerializer,
                   responses={200: UserDetailSerializer},
                   description="更新一个用户")
    def put(self, request, pk):
        user = self.get_object(pk)
        serializer = UserDetailSerializer(user, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(summary="删除用户",
                   description="删除一个用户")
    def delete(self, request, pk):
        user = self.get_object(pk)
        user.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class GroupList(generics.ListAPIView):
    """
    列出所有的group或者创建一个新的group
    """
    pagination_class = CustomizedPagination
    serializer_class = GroupSerializer
    queryset = Group.objects.all().order_by('id')

    @extend_schema(summary="用户组清单",
                   request=GroupSerializer,
                   responses={200: GroupSerializer},
                   description="列出所有用户组（过滤，分页）")
    def get(self, request):
        groups = self.filter_queryset(self.queryset)
        page_groups = self.paginate_queryset(queryset=groups)
        serializer_obj = self.get_serializer(page_groups, many=True)
        data = {
            'data': serializer_obj.data
        }
        return self.get_paginated_response(data)

    @extend_schema(summary="创建用户组",
                   request=GroupSerializer,
                   responses={201: GroupSerializer},
                   description="创建一个用户组")
    def post(self, request):
        serializer = GroupSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class GroupDetail(views.APIView):
    """
    用户组操作
    """
    serializer_class = GroupSerializer

    def get_object(self, pk):
        try:
            return Group.objects.get(pk=pk)
        except Group.DoesNotExist:
            raise Http404

    @extend_schema(summary="更新用户组",
                   request=GroupSerializer,
                   responses={200: GroupSerializer},
                   description="更新一个用户组")
    def put(self, request, pk):
        group = self.get_object(pk)
        serializer = GroupSerializer(group, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(summary="删除用户组",
                   description="删除一个用户组")
    def delete(self, request, pk):
        group = self.get_object(pk)
        group.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ResourceGroupList(generics.ListAPIView):
    """
    列出所有的resourcegroup或者创建一个新的resourcegroup
    """
    pagination_class = CustomizedPagination
    serializer_class = ResourceGroupSerializer
    queryset = ResourceGroup.objects.all().order_by('group_id')

    @extend_schema(summary="资源组清单",
                   request=ResourceGroupSerializer,
                   responses={200: ResourceGroupSerializer},
                   description="列出所有资源组（过滤，分页）")
    def get(self, request):
        groups = self.filter_queryset(self.queryset)
        page_groups = self.paginate_queryset(queryset=groups)
        serializer_obj = self.get_serializer(page_groups, many=True)
        data = {
            'data': serializer_obj.data
        }
        return self.get_paginated_response(data)

    @extend_schema(summary="创建资源组",
                   request=ResourceGroupSerializer,
                   responses={201: ResourceGroupSerializer},
                   description="创建一个资源组")
    def post(self, request):
        serializer = ResourceGroupSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ResourceGroupDetail(views.APIView):
    """
    资源组操作
    """
    serializer_class = ResourceGroupSerializer

    def get_object(self, pk):
        try:
            return ResourceGroup.objects.get(pk=pk)
        except ResourceGroup.DoesNotExist:
            raise Http404

    @extend_schema(summary="更新资源组",
                   request=ResourceGroupSerializer,
                   responses={200: ResourceGroupSerializer},
                   description="更新一个资源组")
    def put(self, request, pk):
        group = self.get_object(pk)
        serializer = ResourceGroupSerializer(group, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(summary="删除资源组",
                   description="删除一个资源组")
    def delete(self, request, pk):
        group = self.get_object(pk)
        group.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class UserAuth(views.APIView):
    """
    用户认证校验
    """
    permission_classes = [IsOwner]

    @extend_schema(summary="用户认证校验",
                   request=UserAuthSerializer,
                   description="用户认证校验")
    def post(self, request):
        # 参数验证
        serializer = UserAuthSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        result = {'status': 0, 'msg': '认证成功'}
        engineer = request.data['engineer']
        password = request.data['password']

        user = authenticate(username=engineer, password=password)
        if not user:
            result = {'status': 1, 'msg': '用户名或密码错误！'}

        return Response(result)


class TwoFA(views.APIView):
    """
    配置2fa
    """
    permission_classes = [permissions.AllowAny]

    @extend_schema(summary="配置2fa",
                   request=TwoFASerializer,
                   description="启用或关闭2fa")
    def post(self, request):
        # 参数验证
        serializer = TwoFASerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        engineer = request.data['engineer']
        auth_type = request.data['auth_type']
        user = Users.objects.get(username=engineer)
        request_user = request.session.get('user')

        if not request.user.is_authenticated:
            if request_user:
                if request_user != engineer:
                    return Response({'status': 1, 'msg': '登录用户与校验用户不一致！'})
            else:
                return Response({'status': 1, 'msg': '需先校验用户密码！'})

        if auth_type == 'disabled':
            # 关闭2fa
            authenticator = TwoFactorAuthBase(user=user)
            result = authenticator.disable()
        elif auth_type == 'totp':
            # 启用2fa - 先生成secret key
            authenticator = get_authenticator(user=user, auth_type=auth_type)
            result = authenticator.generate_key()
        else:
            # 启用2fa
            authenticator = get_authenticator(user=user, auth_type=auth_type)
            result = authenticator.enable()

        return Response(result)


class TwoFASave(views.APIView):
    """
    保存2fa配置（TOTP)
    """
    permission_classes = [IsOwner]

    @extend_schema(summary="保存2fa配置（TOTP)",
                   request=TwoFASaveSerializer,
                   description="保存2fa配置（TOTP)")
    def post(self, request):
        # 参数验证
        serializer = TwoFASaveSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        engineer = request.data['engineer']
        key = request.data['key']
        user = Users.objects.get(username=engineer)

        authenticator = get_authenticator(user=user, auth_type='totp')
        result = authenticator.save(key)

        return Response(result)


class TwoFAVerify(views.APIView):
    """
    检验2fa密码
    """
    permission_classes = [permissions.AllowAny]

    @extend_schema(summary="检验2fa密码",
                   request=TwoFAVerifySerializer,
                   description="检验2fa密码")
    def post(self, request):
        # 参数验证
        serializer = TwoFAVerifySerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        engineer = request.data['engineer']
        otp = request.data['otp']
        key = request.data['key'] if 'key' in request.data.keys() else None
        user = Users.objects.get(username=engineer)
        request_user = request.session.get('user')

        if not request.user.is_authenticated:
            if request_user:
                if request_user != engineer:
                    return Response({'status': 1, 'msg': '登录用户与校验用户不一致！'})
            else:
                return Response({'status': 1, 'msg': '需先校验用户密码！'})

            twofa_config = TwoFactorAuthConfig.objects.filter(user=user)
            if not twofa_config:
                if key:
                    auth_type = request.data['auth_type']
                else:
                    return Response({'status': 1, 'msg': '用户未配置2FA！'})
            else:
                auth_type = twofa_config[0].auth_type
        else:
            auth_type = request.data['auth_type']

        authenticator = get_authenticator(user=user, auth_type=auth_type)
        result = authenticator.verify(otp, key)

        # 校验通过后自动登录，刷新expire_date
        if result['status'] == 0 and not request.user.is_authenticated:
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            request.session.set_expiry(settings.SESSION_COOKIE_AGE)

        return Response(result)
