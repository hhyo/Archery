# -*- coding:utf-8 -*-
"""
@author: EliasChiang
@license: Apache Licence
@file: ssh_tunnel.py
@time: 2020/05/09
"""
from sshtunnel import SSHTunnelForwarder


class SSHConnection(object):
    """
    ssh隧道连接类，用于映射ssh隧道端口到本地，连接结束时需要清理
    """
    def __init__(self, host, port, tun_host, tun_port, tun_user, tun_password):
        self.host = host
        self.port = int(port)
        self.tun_host = tun_host
        self.tun_port = int(tun_port)
        self.tun_user = tun_user
        self.tun_password = tun_password
        self.server = SSHTunnelForwarder(
            ssh_address_or_host=(self.tun_host, self.tun_port),
            ssh_username=self.tun_user,
            ssh_password=self.tun_password,
            remote_bind_address=(self.host, self.port),
        )
        self.server.start()

    def __del__(self):
        self.server.close()

    def get_ssh(self):
        """
        获取ssh映射的端口
        :param request:
        :return:
        """
        return "127.0.0.1", self.server.local_bind_port
