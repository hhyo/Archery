from unittest.mock import patch, MagicMock, call
import unittest
from parameterized import parameterized
from sql.storage import DynamicStorage


class TestDynamicStorage(unittest.TestCase):
    """
    测试 DynamicStorage 类的行为
    """

    def setUp(self):
        """通用配置数据"""
        self.local_config = {
            "storage_type": "local",
            "local_path": "/tmp/files/",
        }

        self.sftp_config = {
            "storage_type": "sftp",
            "sftp_host": "sftp.example.com",
            "sftp_user": "user",
            "sftp_password": "pass",
            "sftp_port": 22,
            "sftp_path": "/uploads/",
        }

        self.s3c_config = {
            "storage_type": "s3c",
            "s3c_access_key_id": "AKIA...",
            "s3c_access_key_secret": "secret",
            "s3c_endpoint": "http://s3.example.com",
            "s3c_bucket_name": "my-bucket",
            "s3c_region": "us-east-1",
            "s3c_path": "data/",
        }

        self.azure_config = {
            "storage_type": "azure",
            "azure_account_name": "myaccount",
            "azure_account_key": "azurekey",
            "azure_container": "container",
            "azure_path": "azure-data/",
        }

    @parameterized.expand(
        [
            (
                "local",
                "FileSystemStorage",
                {
                    "location": "/tmp/files/",
                    "base_url": "/tmp/files/",
                },
            ),
            (
                "sftp",
                "SFTPStorage",
                {
                    "host": "sftp.example.com",
                    "params": {
                        "username": "user",
                        "password": "pass",
                        "port": 22,
                    },
                    "root_path": "/uploads/",
                },
            ),
            (
                "s3c",
                "S3Boto3Storage",
                {
                    "access_key": "AKIA...",
                    "secret_key": "secret",
                    "bucket_name": "my-bucket",
                    "region_name": "us-east-1",
                    "endpoint_url": "http://s3.example.com",
                    "location": "data/",
                    "file_overwrite": False,
                    "addressing_style": "virtual",
                },
            ),
            (
                "azure",
                "AzureStorage",
                {
                    "account_name": "myaccount",
                    "account_key": "azurekey",
                    "azure_container": "container",
                    "location": "azure-data/",
                },
            ),
        ]
    )
    def test_storage_initialization(self, storage_type, storage_class, expected_kwargs):
        """参数化测试存储后端初始化"""
        config_dict = getattr(self, f"{storage_type}_config")

        with patch(f"sql.storage.{storage_class}") as mock_storage:
            DynamicStorage(config_dict=config_dict)

            # 验证正确的存储类被调用
            mock_storage.assert_called_once()

            # 验证调用参数
            actual_kwargs = mock_storage.call_args[1]
            self.assertDictEqual(actual_kwargs, expected_kwargs)

    @parameterized.expand(
        [
            ("save", "test.txt", "content"),
            ("open", "test.txt", "rb"),
            ("delete", "test.txt", None),
            ("exists", "test.txt", None),
            ("size", "test.txt", None),
        ]
    )
    def test_method_proxying(self, method, filename, content):
        """测试方法代理到底层存储"""
        mock_storage = MagicMock()
        with patch.object(DynamicStorage, "_init_storage", return_value=mock_storage):
            storage = DynamicStorage(config_dict=self.local_config)

            # 调用代理方法
            method_call = getattr(storage, method)
            if content:
                method_call(filename, content)
            else:
                method_call(filename)

            # 验证底层存储方法被调用
            underlying_call = getattr(mock_storage, method)
            if content:
                underlying_call.assert_called_once_with(filename, content)
            else:
                underlying_call.assert_called_once_with(filename)

    def test_close_behavior(self):
        """测试 close 方法的两种场景"""
        # 场景1：底层存储有 close 方法
        mock_storage_with_close = MagicMock()
        mock_storage_with_close.close = MagicMock()

        with patch.object(
            DynamicStorage, "_init_storage", return_value=mock_storage_with_close
        ):
            storage = DynamicStorage(config_dict=self.sftp_config)
            storage.close()
            mock_storage_with_close.close.assert_called_once()

        # 场景2：底层存储无 close 方法
        mock_storage_without_close = MagicMock()
        delattr(mock_storage_without_close, "close")

        with patch.object(
            DynamicStorage, "_init_storage", return_value=mock_storage_without_close
        ):
            storage = DynamicStorage(config_dict=self.local_config)
            try:
                storage.close()  # 不应报错
            except Exception as e:
                self.fail(f"close() raised {e}")

    def test_storage_operation_exceptions(self):
        """测试存储操作异常处理"""
        for method in ["open", "save", "delete", "exists", "size"]:
            with self.subTest(method=method):
                with patch.object(DynamicStorage, "_init_storage") as mock_init:
                    mock_storage = MagicMock()
                    mock_init.return_value = mock_storage

                    # 模拟底层存储抛出异常
                    getattr(mock_storage, method).side_effect = Exception("存储错误")

                    storage = DynamicStorage(config_dict=self.local_config)

                    with self.assertRaises(Exception) as context:
                        if method == "save":
                            getattr(storage, method)("test.txt", "content")
                        else:
                            getattr(storage, method)("test.txt")

                    self.assertIn("存储错误", str(context.exception))

    def test_init_unsupported_storage_type(self):
        """测试不支持的存储类型抛出 ValueError"""
        config = {"storage_type": "unsupported"}
        with self.assertRaises(ValueError) as context:
            DynamicStorage(config_dict=config)
        self.assertIn("不支持的存储类型", str(context.exception))

    def test_check_connection_local(self):
        """测试本地存储连接检查"""
        storage = DynamicStorage(config_dict=self.local_config)
        success, msg = storage.check_connection()
        self.assertTrue(success)
        self.assertEqual(msg, "本地存储连接成功")

    def test_check_connection_sftp(self):
        """测试 SFTP 连接检查"""
        with patch("sql.storage.SFTPStorage") as mock_sftp_class:
            mock_sftp_instance = MagicMock()
            mock_sftp_class.return_value = mock_sftp_instance

            # 成功场景
            storage = DynamicStorage(config_dict=self.sftp_config)
            success, msg = storage.check_connection()
            mock_sftp_instance.__enter__().listdir.assert_called_once_with(".")
            self.assertTrue(success)
            self.assertEqual(msg, "SFTP 连接成功")

            # 失败场景
            mock_sftp_instance.__enter__().listdir.side_effect = Exception("连接失败")
            success, msg = storage.check_connection()
            self.assertFalse(success)
            self.assertIn("连接失败", msg)

    def test_check_connection_s3c(self):
        """测试 S3 兼容存储连接检查"""
        with patch("sql.storage.S3Boto3Storage") as mock_s3_class:
            mock_s3_instance = MagicMock()
            mock_s3_class.return_value = mock_s3_instance

            # 设置 bucket_name 属性
            mock_s3_instance.bucket_name = "my-bucket"

            # 成功场景
            mock_client = MagicMock()
            mock_s3_instance.connection.meta.client = mock_client

            storage = DynamicStorage(config_dict=self.s3c_config)
            success, msg = storage.check_connection()
            mock_client.head_bucket.assert_called_once_with(Bucket="my-bucket")
            self.assertTrue(success)
            self.assertEqual(msg, "S3 存储连接成功")

            # 失败场景
            mock_client.head_bucket.side_effect = Exception("Bucket 不存在")
            success, msg = storage.check_connection()
            self.assertFalse(success)
            self.assertIn("Bucket 不存在", msg)

    def test_check_connection_azure(self):
        """测试 Azure Blob 存储连接检查"""
        with patch("sql.storage.AzureStorage") as mock_azure_class:
            mock_azure_instance = MagicMock()
            mock_azure_class.return_value = mock_azure_instance

            # 成功场景
            mock_client = MagicMock()
            mock_azure_instance.client = mock_client

            storage = DynamicStorage(config_dict=self.azure_config)
            success, msg = storage.check_connection()
            mock_client.get_container_properties.assert_called_once()
            self.assertTrue(success)
            self.assertEqual(msg, "Azure Blob 存储连接成功")

            # 失败场景
            mock_client.get_container_properties.side_effect = Exception("容器不存在")
            success, msg = storage.check_connection()
            self.assertFalse(success)
            self.assertIn("容器不存在", msg)
