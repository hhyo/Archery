from unittest.mock import patch, MagicMock, call
import unittest
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

        self.s3_config = {
            "storage_type": "s3",
            "s3_access_key": "AKIA...",
            "s3_secret_key": "secret",
            "s3_bucket": "my-bucket",
            "s3_region": "us-east-1",
            "s3_path": "data/",
        }

        self.oss_config = {
            "storage_type": "oss",
            "oss_access_key_id": "OSSAK...",
            "oss_access_key_secret": "osssecret",
            "oss_endpoint": "http://oss-cn-beijing.aliyuncs.com",
            "oss_bucket_name": "oss-bucket",
            "oss_path": "oss-data/",
        }

        self.azure_config = {
            "storage_type": "azure",
            "azure_account_name": "myaccount",
            "azure_account_key": "azurekey",
            "azure_container": "container",
            "azure_path": "azure-data/",
        }

    def test_init_local_storage(self):
        """测试本地存储初始化"""

        with patch("sql.storage.FileSystemStorage") as mock_fs:
            mock_fs_instance = MagicMock()
            mock_fs.return_value = mock_fs_instance

            storage = DynamicStorage(config_dict=self.local_config)

            mock_fs.assert_called_once_with(
                location="/tmp/files/",
                base_url="/tmp/files/",
            )
            self.assertEqual(storage.storage_type, "local")

    def test_init_sftp_storage(self):
        """测试 SFTP 存储初始化"""

        with patch("sql.storage.SFTPStorage") as mock_sftp:
            mock_sftp_instance = MagicMock()
            mock_sftp.return_value = mock_sftp_instance

            storage = DynamicStorage(config_dict=self.sftp_config)

            mock_sftp.assert_called_once_with(
                host="sftp.example.com",
                params={
                    "username": "user",
                    "password": "pass",
                    "port": 22,
                },
                root_path="/uploads/",
            )

    def test_init_s3_storage(self):
        """测试 AWS S3 存储初始化"""

        with patch("sql.storage.S3Boto3Storage") as mock_s3:
            mock_s3_instance = MagicMock()
            mock_s3.return_value = mock_s3_instance

            storage = DynamicStorage(config_dict=self.s3_config)

            mock_s3.assert_called_once_with(
                access_key="AKIA...",
                secret_key="secret",
                bucket_name="my-bucket",
                region_name="us-east-1",
                location="data/",
                file_overwrite=False,
            )

    def test_init_oss_storage(self):
        """测试阿里云 OSS 存储初始化"""

        with patch("sql.storage.S3Boto3Storage") as mock_oss:
            mock_oss_instance = MagicMock()
            mock_oss.return_value = mock_oss_instance

            storage = DynamicStorage(config_dict=self.oss_config)

            mock_oss.assert_called_once_with(
                access_key="OSSAK...",
                secret_key="osssecret",
                bucket_name="oss-bucket",
                location="oss-data/",
                endpoint_url="http://oss-cn-beijing.aliyuncs.com",
                file_overwrite=False,
                addressing_style="virtual",
            )

    def test_init_azure_storage(self):
        """测试 Azure Blob 存储初始化"""

        with patch("sql.storage.AzureStorage") as mock_azure:
            mock_azure_instance = MagicMock()
            mock_azure.return_value = mock_azure_instance

            storage = DynamicStorage(config_dict=self.azure_config)

            mock_azure.assert_called_once_with(
                account_name="myaccount",
                account_key="azurekey",
                azure_container="container",
                location="azure-data/",
            )

    def test_init_unsupported_storage_type(self):
        """测试不支持的存储类型抛出 ValueError"""

        config = {"storage_type": "unsupported"}
        with self.assertRaises(ValueError) as context:
            DynamicStorage(config_dict=config)
        self.assertIn("不支持的存储类型", str(context.exception))

    def test_save_calls_underlying_save(self):
        """测试 save 方法代理"""

        mock_storage = MagicMock()
        with patch.object(DynamicStorage, "_init_storage", return_value=mock_storage):
            storage = DynamicStorage(config_dict=self.local_config)
            storage.save("test.txt", "content")

            mock_storage.save.assert_called_once_with("test.txt", "content")

    def test_save_with_sftp_uses_context_manager(self):
        """测试 SFTP 的 save 使用 with 语句"""

        mock_sftp = MagicMock()
        with patch("sql.storage.SFTPStorage") as mock_sftp_class:
            mock_sftp_class.return_value = mock_sftp
            storage = DynamicStorage(config_dict=self.sftp_config)
            storage.save("file.txt", "content")

            # 验证使用了 with
            mock_sftp.__enter__.assert_called_once()
            mock_sftp.__enter__().save.assert_called_once_with("file.txt", "content")
            mock_sftp.__exit__.assert_called_once()

    def test_open_calls_underlying_open(self):
        """测试 open 方法代理"""

        mock_storage = MagicMock()
        with patch.object(DynamicStorage, "_init_storage", return_value=mock_storage):
            storage = DynamicStorage(config_dict=self.local_config)
            storage.open("test.txt", "rb")

            mock_storage.open.assert_called_once_with("test.txt", "rb")

    def test_delete_calls_underlying_delete(self):
        """测试 delete 方法代理"""

        mock_storage = MagicMock()
        with patch.object(DynamicStorage, "_init_storage", return_value=mock_storage):
            storage = DynamicStorage(config_dict=self.local_config)
            storage.delete("test.txt")

            mock_storage.delete.assert_called_once_with("test.txt")

    def test_exists_calls_underlying_exists(self):
        """测试 exists 方法代理"""

        mock_storage = MagicMock()
        with patch.object(DynamicStorage, "_init_storage", return_value=mock_storage):
            storage = DynamicStorage(config_dict=self.local_config)
            storage.exists("test.txt")

            mock_storage.exists.assert_called_once_with("test.txt")

    def test_size_calls_underlying_size(self):
        """测试 size 方法代理"""

        mock_storage = MagicMock()
        with patch.object(DynamicStorage, "_init_storage", return_value=mock_storage):
            storage = DynamicStorage(config_dict=self.local_config)
            storage.size("test.txt")

            mock_storage.size.assert_called_once_with("test.txt")

    def test_close_calls_underlying_close_if_exists(self):
        """测试 close 调用底层 close（如 SFTP）"""

        mock_storage = MagicMock()
        mock_storage.close = MagicMock()

        with patch.object(DynamicStorage, "_init_storage", return_value=mock_storage):
            storage = DynamicStorage(config_dict=self.sftp_config)
            storage.close()

            mock_storage.close.assert_called_once()

    def test_close_does_nothing_if_no_close_method(self):
        """
        测试 close 方法在底层存储无 close 时不报错
        """

        mock_storage = MagicMock()
        # 模拟 close 存在但调用会出错（或不存在）
        delattr(mock_storage, "close")  # 删除 close 属性

        with patch.object(DynamicStorage, "_init_storage", return_value=mock_storage):
            storage = DynamicStorage(config_dict=self.local_config)
            try:
                storage.close()  # 不应报错
            except Exception as e:
                self.fail(f"close() raised {e}")

    def test_url_calls_underlying_url_if_supported(self):
        """测试 url 返回底层 url"""

        mock_storage = MagicMock()
        mock_storage.url = MagicMock(return_value="https://example.com/file.txt")

        with patch.object(DynamicStorage, "_init_storage", return_value=mock_storage):
            storage = DynamicStorage(config_dict=self.s3_config)
            result = storage.url("file.txt")

            self.assertEqual(result, "https://example.com/file.txt")
            mock_storage.url.assert_called_once_with("file.txt")

    def test_url_returns_fallback_if_no_url_method(self):
        mock_storage = MagicMock()
        # 删除 url 属性，模拟不支持 url()
        del mock_storage.url

        with patch.object(DynamicStorage, "_init_storage", return_value=mock_storage):
            storage = DynamicStorage(config_dict=self.local_config)
            result = storage.url("file.txt")
            self.assertEqual(result, "/download/file.txt")

    def test_check_connection_local_always_true(self):
        """本地存储连接默认为 True"""

        with patch.object(DynamicStorage, "_init_storage"):
            storage = DynamicStorage(config_dict=self.local_config)
            result = storage.check_connection()
            self.assertTrue(result)

    def test_check_connection_sftp_calls_listdir_in_context(self):
        """SFTP check_connection 使用 with 并 listdir"""

        mock_sftp = MagicMock()
        with patch("sql.storage.SFTPStorage") as mock_sftp_class:
            mock_sftp_class.return_value = mock_sftp
            storage = DynamicStorage(config_dict=self.sftp_config)
            storage.check_connection()

            mock_sftp.__enter__.assert_called_once()
            mock_sftp.__enter__().listdir.assert_called_once_with(".")
            mock_sftp.__exit__.assert_called_once()

    def test_check_connection_s3_calls_head_bucket(self):
        """S3/OSS check_connection 调用 head_bucket"""

        mock_s3 = MagicMock()
        mock_s3.bucket_name = "my-bucket"
        mock_client = MagicMock()
        mock_s3.connection.meta.client = mock_client

        with patch.object(DynamicStorage, "_init_storage", return_value=mock_s3):
            storage = DynamicStorage(config_dict=self.s3_config)
            storage.check_connection()

            mock_client.head_bucket.assert_called_once_with(Bucket="my-bucket")

    def test_check_connection_azure_calls_get_container_properties(self):
        """Azure check_connection 调用 get_container_properties"""

        mock_azure = MagicMock()
        mock_azure.azure_container = "container"
        mock_container_client = MagicMock()
        mock_azure.client.get_container_client.return_value = mock_container_client

        with patch.object(DynamicStorage, "_init_storage", return_value=mock_azure):
            storage = DynamicStorage(config_dict=self.azure_config)
            storage.check_connection()

            mock_azure.client.get_container_client.assert_called_once_with("container")
            mock_container_client.get_container_properties.assert_called_once()

    def test_check_connection_unsupported_type_returns_true_for_local(self):
        """未知类型默认视为本地存储"""

        config = {"storage_type": "unknown"}
        with patch.object(DynamicStorage, "_init_storage"):
            storage = DynamicStorage(config_dict=config)
            result = storage.check_connection()
            self.assertTrue(result)
