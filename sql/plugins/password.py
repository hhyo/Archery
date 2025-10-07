"""
本文件存放一些和密码相关的插件

插件提供两个方法, 获取用户名和密码, 用于连接数据库
插件在使用时, 会和 Instance 一起使用, 可以用 self 对象获取 instance 的各种信息

包括名字, 类型, 等等. 通过这些信息, 插件可以获取数据库的用户名和密码
"""

import time
import requests


class DummyMixin:
    """mixin 模板, 用于提供一些基础的方法, 给其他 mixin 继承
    默认从schema 中直接提取 username 和 password
    """

    def get_username_password(self):
        return self.user, self.password


password_cache = {
    "instance_name": {
        "username": "username",
        "password": "password",
        "expires_at": "1740557906.15272",
    }
}


class VaultMixin(DummyMixin):
    """
    和 sqlinstance 搭配使用
    从 vault 中获取用户名和密码, 调用的是 localhost 8000 端口的 vault 服务
    不使用任何 token, 适合 vault-proxy 部署方式, 如需其他部署方式, 可继承后修改配置
    使用的是 static secret, 如需其他获取方式, 可继承后修改配置
    """

    vault_server = "localhost:8200"
    vault_token = ""

    def get_username_password(self):
        if self.instance_name in password_cache:
            if password_cache[self.instance_name]["expires_at"] > time.time():
                return (
                    password_cache[self.instance_name]["username"],
                    password_cache[self.instance_name]["password"],
                )

        vault_role = f"{self.instance_name}-archery-rw"
        response = requests.get(
            f"http://{self.vault_server}/v1/database/static-creds/{vault_role}",
            headers={"X-Vault-Token": self.vault_token},
        )
        response.raise_for_status()
        data = response.json()["data"]
        password_cache[self.instance_name] = {
            "username": data["username"],
            "password": data["password"],
            "expires_at": time.time() + data["ttl"] - 60,
        }
        return data["username"], data["password"]
