import logging
from django.core.files.storage import FileSystemStorage
from storages.backends.s3boto3 import S3Boto3Storage
from storages.backends.azure_storage import AzureStorage
from storages.backends.sftpstorage import SFTPStorage
from common.config import SysConfig
import json

logger = logging.getLogger("default")


class DynamicStorage:
    """动态存储适配器，根据配置选择实际存储后端"""

    def __init__(self, storage_type=None, config_dict=None):
        """根据存储服务进行文件的上传下载"""

        # 获取系统配置
        self.config = config_dict or SysConfig()

        # 存储类型
        self.storage_type = self.config.get("storage_type", "local")

        # 本地存储相关配置信息
        self.local_path = self.config.get("local_path", "downloads/DataExportFile/")

        # SFTP 存储相关配置信息
        self.sftp_host = self.config.get("sftp_host", "")
        self.sftp_user = self.config.get("sftp_user", "")
        self.sftp_password = self.config.get("sftp_password", "")
        self.sftp_port = self.config.get("sftp_port", "")
        self.sftp_path = self.config.get("sftp_path", "")
        self.sftp_custom_params_str = self.config.get("sftp_custom_params", "")

        # S3 Compatible 存储相关配置信息
        self.s3c_access_key_id = self.config.get("s3c_access_key_id", "")
        self.s3c_access_key_secret = self.config.get("s3c_access_key_secret", "")
        self.s3c_endpoint = self.config.get("s3c_endpoint", "")
        self.s3c_bucket_name = self.config.get("s3c_bucket_name", "")
        self.s3c_region = self.config.get("s3c_region", "")
        self.s3c_path = self.config.get("s3c_path", "")
        self.s3c_custom_params_str = self.config.get("s3c_custom_params", "")

        # Azure Blob 存储相关配置信息
        self.azure_account_name = self.config.get("azure_account_name", "")
        self.azure_account_key = self.config.get("azure_account_key", "")
        self.azure_container = self.config.get("azure_container", "")
        self.azure_path = self.config.get("azure_path", "")
        self.azure_custom_params_str = self.config.get("azure_custom_params", "")

        self.storage = self._init_storage()

        self.open = self.storage.open
        self.exists = self.storage.exists
        self.size = self.storage.size
        self.delete = self.storage.delete
        self.url = self.storage.url
        self.save = self.storage.save

        if hasattr(self.storage, "close"):
            self.close = self.storage.close
        else:
            self.close = lambda: None

    def _init_storage(self):
        """根据配置初始化存储后端"""
        storage_backends = {
            "local": self._init_local_storage,
            "sftp": self._init_sftp_storage,
            "s3c": self._init_s3c_storage,
            "azure": self._init_azure_storage,
        }

        init_func = storage_backends.get(self.storage_type)
        if init_func:
            return init_func()
        raise ValueError(f"不支持的存储类型: {self.storage_type}")

    def _init_local_storage(self):
        # 基础参数
        local_params = {
            "location": str(self.local_path),
            "base_url": f"{self.local_path}",
        }

        return FileSystemStorage(**local_params)

    def _init_sftp_storage(self):
        # 基础参数
        sftp_params = {
            "host": self.sftp_host,
            "params": {
                "username": self.sftp_user,
                "password": self.sftp_password,
                "port": self.sftp_port,
            },
            "root_path": self.sftp_path,
        }

        if self.sftp_custom_params_str.strip():
            try:
                self.sftp_custom_params = json.loads(self.sftp_custom_params_str)
            except json.JSONDecodeError:
                # 无效 JSON 时使用空字典
                self.sftp_custom_params = {}
        else:
            # 空字符串直接设为空字典
            self.sftp_custom_params = {}

        # 添加自定义参数
        sftp_params.update(self.sftp_custom_params)

        return SFTPStorage(**sftp_params)

    def _init_s3c_storage(self):
        """
        s3c兼容存储
        阿里云OSS经测试
            addressing_style必须为virtual，否则无法连接，
            endpoint只能使用http://，否则save文件会报aws-chunked encoding is not supported with the specified x-amz-content-sha256 value相关错误
        """

        # 基础参数
        s3c_params = {
            "access_key": self.s3c_access_key_id,
            "secret_key": self.s3c_access_key_secret,
            "bucket_name": self.s3c_bucket_name,
            **({"region_name": self.s3c_region} if self.s3c_region else {}),
            "endpoint_url": self.s3c_endpoint,
            "location": self.s3c_path,
            "file_overwrite": False,
        }

        if self.s3c_custom_params_str.strip():
            try:
                self.s3c_custom_params = json.loads(self.s3c_custom_params_str)
            except json.JSONDecodeError:
                # 无效 JSON 时使用空字典
                self.s3c_custom_params = {}
        else:
            # 空字符串直接设为空字典
            self.s3c_custom_params = {}

        # 添加自定义参数
        s3c_params.update(self.s3c_custom_params)

        return S3Boto3Storage(**s3c_params)

    def _init_azure_storage(self):
        # 基础参数
        azure_params = {
            "account_name": self.azure_account_name,
            "account_key": self.azure_account_key,
            "azure_container": self.azure_container,
            "location": self.azure_path,
        }

        if self.azure_custom_params_str.strip():
            try:
                self.azure_custom_params = json.loads(self.azure_custom_params_str)
            except json.JSONDecodeError:
                # 无效 JSON 时使用空字典
                self.azure_custom_params = {}
        else:
            # 空字符串直接设为空字典
            self.azure_custom_params = {}

        # 添加自定义参数
        azure_params.update(self.azure_custom_params)

        return AzureStorage(**azure_params)

    def check_connection(self):
        """测试存储连接是否有效，返回 (状态, 错误信息)"""
        # 本地存储默认连接有效，无需测试
        if self.storage_type == "local":
            return True, "本地存储连接成功"

        connection_checks = {
            "sftp": self._check_sftp_connection,
            "s3c": self._check_s3c_connection,
            "azure": self._check_azure_connection,
        }

        check_func = connection_checks.get(self.storage_type)
        if check_func:
            return check_func()

        # 不支持的存储类型
        return False, f"不支持的存储类型: {self.storage_type}"

    def _check_sftp_connection(self):
        """检查 SFTP 连接"""
        try:
            with self.storage as s:
                s.listdir(".")
            return True, "SFTP 连接成功"
        except Exception as e:
            return False, f"SFTP 连接失败: {str(e)}"

    def _check_s3c_connection(self):
        """检查 S3 兼容存储连接"""
        try:
            client = self.storage.connection.meta.client
            client.head_bucket(Bucket=self.storage.bucket_name)
            return True, "S3 存储连接成功"
        except Exception as e:
            return False, f"S3 存储连接失败: {str(e)}"

    def _check_azure_connection(self):
        """检查 Azure Blob 存储连接"""
        try:
            container_client = self.storage.client
            container_client.get_container_properties()
            return True, "Azure Blob 存储连接成功"
        except Exception as e:
            return False, f"Azure Blob 存储连接失败: {str(e)}"
