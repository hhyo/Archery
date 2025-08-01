from django.core.files.storage import FileSystemStorage
from storages.backends.s3boto3 import S3Boto3Storage
from storages.backends.azure_storage import AzureStorage
from storages.backends.sftpstorage import SFTPStorage
from pathlib import Path
from django.conf import settings
import os
from sql.models import Config

def get_sys_config():
    all_config = Config.objects.all().values("item", "value")
    sys_config = {}
    for items in all_config:
        sys_config[items["item"]] = items["value"]
    return sys_config

class DynamicStorage:
    """动态存储适配器，根据配置选择实际存储后端"""
    
    def __init__(
        self, storage_type=None, config_dict=None
    ):
        """根据存储服务进行文件的上传下载"""

        # 获取系统配置
        #self.config = get_sys_config()
        self.config = config_dict or get_sys_config()

        # 存储类型
        self.storage_type = self.config["storage_type"]

        # 本地存储相关配置信息
        self.local_path = Path(self.config.get("local_path", ""))
        self.base_download_path = Path(settings.BASE_DIR).resolve() / "downloads"
        self.full_download_path = self.base_download_path / self.local_path

        # SFTP 存储相关配置信息
        self.sftp_host = self.config["sftp_host"]
        self.sftp_user = self.config["sftp_user"]
        self.sftp_password = self.config["sftp_password"]
        self.sftp_port = int(self.config.get("sftp_port", 22))
        self.sftp_path = self.config["sftp_path"]

        # OSS 存储相关配置信息
        self.oss_access_key_id = self.config["oss_access_key_id"]
        self.oss_access_key_secret = self.config["oss_access_key_secret"]
        self.oss_endpoint = self.config["oss_endpoint"]
        self.oss_bucket_name = self.config["oss_bucket_name"]
        self.oss_path = self.config["oss_path"]

        # AWS S3 存储相关配置信息
        self.s3_access_key = self.config["s3_access_key"]
        self.s3_secret_key = self.config["s3_secret_key"]
        self.s3_bucket = self.config["s3_bucket"]
        self.s3_region = self.config["s3_region"]
        self.s3_path = self.config["s3_path"]

        # Azure Blob 存储相关配置信息
        self.azure_account_name = self.config["azure_account_name"]
        self.azure_account_key = self.config["azure_account_key"]
        self.azure_container = self.config["azure_container"]
        self.azure_path = self.config["azure_path"]

        self.storage = self._init_storage()

    def _init_storage(self):
        """根据配置初始化存储后端"""

        if self.storage_type == 'local':
            return FileSystemStorage(
                location=self.full_download_path,
                base_url=f'{self.full_download_path}'
            )
        
        elif self.storage_type == 'sftp':
            return SFTPStorage(
                host=self.sftp_host,
                params={
                    "username": self.sftp_user,
                    "password": self.sftp_password,
                    "port": self.sftp_port,
                    },
                root_path=self.sftp_path,
            )
        
        elif self.storage_type == 'oss':
            # 阿里云OSS 使用 S3 兼容接口，经测试，OSS的endpoint只能使用http://，否则会报aws-chunked encoding is not supported with the specified x-amz-content-sha256 value相关错误
            return S3Boto3Storage(
                access_key=self.oss_access_key_id,
                secret_key=self.oss_access_key_secret,
                bucket_name=self.oss_bucket_name,
                location=self.oss_path,
                endpoint_url=self.oss_endpoint,
                file_overwrite=False,
                addressing_style='virtual',
            )
        
        elif self.storage_type == 's3':
            return S3Boto3Storage(
                access_key=self.s3_access_key,
                secret_key=self.s3_secret_key,
                bucket_name=self.s3_bucket,
                region_name=self.s3_region,
                location=self.s3_path,
                file_overwrite=False,
            )
        
        elif self.storage_type == 'azure':
            return AzureStorage(
                account_name=self.azure_account_name,
                account_key=self.azure_account_key,
                azure_container=self.azure_container,
                location=self.azure_path,
            )
        
        raise ValueError(f"不支持的存储类型: {self.storage_type}")
    
    # 代理存储方法
    def save(self, name, content):
        if self.storage_type == 'sftp':
            with self.storage as s: # 参考官方文档SFTPStorage 使用with as确保SFTP底层ssh连接关闭。
                return s.save(name, content)
        else:
            return self.storage.save(name, content)
    
    def open(self, name, mode='rb'):
        return self.storage.open(name, mode)
    
    def delete(self, name):
        return self.storage.delete(name)
    
    def exists(self, name):
        return self.storage.exists(name)

    def size(self, name):
        return self.storage.size(name)

    def close(self):
        if hasattr(self.storage, 'close'):
            return self.storage.close()

    def url(self, name):
        if hasattr(self.storage, 'url'):
            return self.storage.url(name)
        return f"/download/{name}"

    def check_connection(self):
        """测试存储连接是否有效"""
        if self.storage_type == 'local':
            if self.base_download_path not in self.full_download_path.parents:
                raise PermissionError(f"不允许访问 BASE_DIR 外的路径: {self.full_download_path}，只允许在 {self.base_download_path} 下的路径")
            if not os.path.isdir(self.full_download_path):
                raise ValueError(f"本地路径不存在: {self.full_download_path}")
            if not os.access(self.full_download_path, os.R_OK | os.W_OK):
                raise PermissionError(f"路径权限不足: {self.full_download_path}")
        elif self.storage_type == 'sftp':
            with self.storage as s:
                s.listdir('.')
        
        elif self.storage_type in ['oss', 's3']:
            # 使用S3兼容接口测试
            client = self.storage.connection.meta.client
            client.head_bucket(Bucket=self.storage.bucket_name)
            
        elif self.storage_type == 'azure':
            container_client = self.storage.client.get_container_client(
                self.storage.container_name
            )
            container_client.get_container_properties()