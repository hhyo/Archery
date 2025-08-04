from django.core.files.storage import FileSystemStorage
from storages.backends.s3boto3 import S3Boto3Storage
from storages.backends.azure_storage import AzureStorage
from storages.backends.sftpstorage import SFTPStorage
from django.conf import settings
import os
import re
from sql.models import Config
from django.core.cache import cache


def get_sys_config():
    all_config = Config.objects.all().values("item", "value")
    sys_config = {}
    for items in all_config:
        sys_config[items["item"]] = items["value"]
    return sys_config


class DynamicStorage:
    """动态存储适配器，根据配置选择实际存储后端"""

    def __init__(self, storage_type=None, config_dict=None):
        """根据存储服务进行文件的上传下载"""

        # 获取系统配置
        self.config = config_dict or get_sys_config()

        # 存储类型
        self.storage_type = self.config.get("storage_type", "local")

        # 本地存储相关配置信息
        self.local_path = self.config.get("local_path", "downloads/DataExportFile/")

        # SFTP 存储相关配置信息
        self.sftp_host = self.config.get("sftp_host", "")
        self.sftp_user = self.config.get("sftp_user", "")
        self.sftp_password = self.config.get("sftp_password", "")
        self.sftp_port = int(self.config.get("sftp_port", 22))
        self.sftp_path = self.config.get("sftp_path", "")

        # OSS 存储相关配置信息
        self.oss_access_key_id = self.config.get("oss_access_key_id", "")
        self.oss_access_key_secret = self.config.get("oss_access_key_secret", "")
        self.oss_endpoint = self.config.get("oss_endpoint", "")
        self.oss_bucket_name = self.config.get("oss_bucket_name", "")
        self.oss_path = self.config.get("oss_path", "")

        # AWS S3 存储相关配置信息
        self.s3_access_key = self.config.get("s3_access_key", "")
        self.s3_secret_key = self.config.get("s3_secret_key", "")
        self.s3_bucket = self.config.get("s3_bucket", "")
        self.s3_region = self.config.get("s3_region", "")
        self.s3_path = self.config.get("s3_path", "")

        # Azure Blob 存储相关配置信息
        self.azure_account_name = self.config.get("azure_account_name", "")
        self.azure_account_key = self.config.get("azure_account_key", "")
        self.azure_container = self.config.get("azure_container", "")
        self.azure_path = self.config.get("azure_path", "")

        self.storage = self._init_storage()

    def _init_storage(self):
        """根据配置初始化存储后端"""
        storage_backends = {
            "local": self._init_local_storage,
            "sftp": self._init_sftp_storage,
            "oss": self._init_oss_storage,
            "s3": self._init_s3_storage,
            "azure": self._init_azure_storage
        }

        init_func = storage_backends.get(self.storage_type)
        if init_func:
            return init_func()
        raise ValueError(f"不支持的存储类型: {self.storage_type}")

    def _init_local_storage(self):
        return FileSystemStorage(
            location=str(self.local_path),
            base_url=f"{self.local_path}",
        )

    def _init_sftp_storage(self):
        return SFTPStorage(
            host=self.sftp_host,
            params={
                "username": self.sftp_user,
                "password": self.sftp_password,
                "port": self.sftp_port,
            },
            root_path=self.sftp_path,
        )

    def _init_oss_storage(self):
        # 阿里云OSS 使用 S3 兼容接口，经测试，OSS的endpoint只能使用http://，否则会报aws-chunked encoding is not supported with the specified x-amz-content-sha256 value相关错误
        return S3Boto3Storage(
            access_key=self.oss_access_key_id,
            secret_key=self.oss_access_key_secret,
            bucket_name=self.oss_bucket_name,
            location=self.oss_path,
            endpoint_url=self.oss_endpoint,
            file_overwrite=False,
            addressing_style="virtual",
        )

    def _init_s3_storage(self):
        return S3Boto3Storage(
            access_key=self.s3_access_key,
            secret_key=self.s3_secret_key,
            bucket_name=self.s3_bucket,
            region_name=self.s3_region,
            location=self.s3_path,
            file_overwrite=False,
        )

    def _init_azure_storage(self):
        return AzureStorage(
            account_name=self.azure_account_name,
            account_key=self.azure_account_key,
            azure_container=self.azure_container,
            location=self.azure_path,
        )

    # 代理存储方法
    def save(self, name, content):
        if self.storage_type == "sftp":
            with self.storage as s:  # 参考官方文档SFTPStorage 使用with as确保SFTP底层ssh连接关闭。
                return s.save(name, content)
        else:
            return self.storage.save(name, content)

    def open(self, name, mode="rb"):
        return self.storage.open(name, mode)

    def delete(self, name):
        return self.storage.delete(name)

    def exists(self, name):
        return self.storage.exists(name)

    def size(self, name):
        return self.storage.size(name)

    def close(self):
        if hasattr(self.storage, "close"):
            return self.storage.close()

    def url(self, name):
        if hasattr(self.storage, "url"):
            return self.storage.url(name)
        return f"/download/{name}"

    def check_connection(self):
        """测试存储连接是否有效"""
        connection_checks = {
            "sftp": self._check_sftp_connection,
            "oss": self._check_oss_s3_connection,
            "s3": self._check_oss_s3_connection,
            "azure": self._check_azure_connection
        }

        check_func = connection_checks.get(self.storage_type)
        if check_func:
            return check_func()
        # 本地存储默认连接有效
        return True

    def _check_sftp_connection(self):
        with self.storage as s:
            s.listdir(".")
        return True

    def _check_oss_s3_connection(self):
        client = self.storage.connection.meta.client
        client.head_bucket(Bucket=self.storage.bucket_name)
        return True

    def _check_azure_connection(self):
        container_client = self.storage.client.get_container_client(
            self.storage.azure_container
        )
        container_client.get_container_properties()
        return True
