from rest_framework import views, generics, status
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema
from .serializers import UserSerializer, UserDetailSerializer, GroupSerializer, ResourceGroupSerializer
from .pagination import CustomizedPagination
from .filters import UserFilter
from django.contrib.auth.models import Group
from django.http import Http404
from sql.models import Users, ResourceGroup


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
