from rest_framework import views, generics, status, serializers
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema
from .serializers import InstanceSerializer, InstanceDetailSerializer, TunnelSerializer, \
    AliyunRdsSerializer, InstanceResourceSerializer, InstanceResourceListSerializer
from .pagination import CustomizedPagination
from .filters import InstanceFilter
from sql.models import Instance, Tunnel, AliyunRdsConfig
from sql.engines import get_engine
from django.http import Http404
import MySQLdb


class InstanceList(generics.ListAPIView):
    """
    列出所有的instance或者创建一个新的instance配置
    """
    filterset_class = InstanceFilter
    pagination_class = CustomizedPagination
    serializer_class = InstanceSerializer
    queryset = Instance.objects.all().order_by('id')

    @extend_schema(summary="实例清单",
                   request=InstanceSerializer,
                   responses={200: InstanceSerializer},
                   description="列出所有实例（过滤，分页）")
    def get(self, request):
        instances = self.filter_queryset(self.queryset)
        page_ins = self.paginate_queryset(queryset=instances)
        serializer_obj = self.get_serializer(page_ins, many=True)
        data = {
            'data': serializer_obj.data
        }
        return self.get_paginated_response(data)

    @extend_schema(summary="创建实例",
                   request=InstanceSerializer,
                   responses={201: InstanceSerializer},
                   description="创建一个实例配置")
    def post(self, request):
        serializer = InstanceSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class InstanceDetail(views.APIView):
    """
    实例操作
    """
    serializer_class = InstanceDetailSerializer

    def get_object(self, pk):
        try:
            return Instance.objects.get(pk=pk)
        except Instance.DoesNotExist:
            raise Http404

    @extend_schema(summary="更新实例",
                   request=InstanceDetailSerializer,
                   responses={200: InstanceDetailSerializer},
                   description="更新一个实例配置")
    def put(self, request, pk):
        instance = self.get_object(pk)
        serializer = InstanceDetailSerializer(instance, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(summary="删除实例",
                   description="删除一个实例配置")
    def delete(self, request, pk):
        instance = self.get_object(pk)
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class TunnelList(generics.ListAPIView):
    """
    列出所有的tunnel或者创建一个新的tunnel配置
    """
    pagination_class = CustomizedPagination
    serializer_class = TunnelSerializer
    queryset = Tunnel.objects.all().order_by('id')

    @extend_schema(summary="隧道清单",
                   request=TunnelSerializer,
                   responses={200: TunnelSerializer},
                   description="列出所有隧道（过滤，分页）")
    def get(self, request):
        tunnels = self.filter_queryset(self.queryset)
        page_tunnels = self.paginate_queryset(queryset=tunnels)
        serializer_obj = self.get_serializer(page_tunnels, many=True)
        data = {
            'data': serializer_obj.data
        }
        return self.get_paginated_response(data)

    @extend_schema(summary="创建隧道",
                   request=TunnelSerializer,
                   responses={201: TunnelSerializer},
                   description="创建一个隧道配置")
    def post(self, request):
        serializer = TunnelSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AliyunRdsList(generics.ListAPIView):
    """
    列出所有的AliyunRDS或者创建一个新的AliyunRDS配置
    """
    pagination_class = CustomizedPagination
    serializer_class = AliyunRdsSerializer
    queryset = AliyunRdsConfig.objects.all().select_related('ak').order_by('id')

    @extend_schema(summary="AliyunRDS清单",
                   request=AliyunRdsSerializer,
                   responses={200: AliyunRdsSerializer},
                   description="列出所有AliyunRDS（过滤，分页）")
    def get(self, request):
        aliyunrds = self.filter_queryset(self.queryset)
        page_rds = self.paginate_queryset(queryset=aliyunrds)
        serializer_obj = self.get_serializer(page_rds, many=True)
        data = {
            'data': serializer_obj.data
        }
        return self.get_paginated_response(data)

    @extend_schema(summary="创建AliyunRDS",
                   request=AliyunRdsSerializer,
                   responses={201: AliyunRdsSerializer},
                   description="创建一个AliyunRDS配置（包含一个CloudAccessKey）")
    def post(self, request):
        serializer = AliyunRdsSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class InstanceResource(views.APIView):
    """
    获取实例内的资源信息，database、schema、table、column
    """

    @extend_schema(summary="实例资源",
                   request=InstanceResourceSerializer,
                   responses={200: InstanceResourceListSerializer},
                   description="获取实例内的资源信息")
    def post(self, request):
        # 参数验证
        serializer = InstanceResourceSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        instance_id = request.data['instance_id']
        resource_type = request.data['resource_type']
        db_name = request.data['db_name'] if 'db_name' in request.data.keys() else ''
        schema_name = request.data['schema_name'] if 'schema_name' in request.data.keys() else ''
        tb_name = request.data['tb_name'] if 'tb_name' in request.data.keys() else ''
        instance = Instance.objects.get(pk=instance_id)

        try:
            # escape
            db_name = MySQLdb.escape_string(db_name).decode('utf-8')
            schema_name = MySQLdb.escape_string(schema_name).decode('utf-8')
            tb_name = MySQLdb.escape_string(tb_name).decode('utf-8')

            query_engine = get_engine(instance=instance)
            if resource_type == 'database':
                resource = query_engine.get_all_databases()
            elif resource_type == 'schema' and db_name:
                resource = query_engine.get_all_schemas(db_name=db_name)
            elif resource_type == 'table' and db_name:
                resource = query_engine.get_all_tables(db_name=db_name, schema_name=schema_name)
            elif resource_type == 'column' and db_name and tb_name:
                resource = query_engine.get_all_columns_by_tb(db_name=db_name, tb_name=tb_name, schema_name=schema_name)
            else:
                raise serializers.ValidationError({'errors': '不支持的资源类型或者参数不完整！'})
        except Exception as msg:
            raise serializers.ValidationError({'errors': msg})
        else:
            if resource.error:
                raise serializers.ValidationError({'errors': resource.error})
            else:
                resource = {'count': len(resource.rows),
                            'result': resource.rows}
                serializer_obj = InstanceResourceListSerializer(resource)
                return Response(serializer_obj.data)
