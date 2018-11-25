# -*- coding: UTF-8 -*-

import email
import smtplib
import requests
import logging
import traceback
from threading import Thread
from email import encoders
from email.header import Header
from email.mime.text import MIMEText
from email.utils import formataddr
from common.config import SysConfig

logger = logging.getLogger('default')


class MailSender(object):

    def __init__(self):
        sys_config = SysConfig().sys_config
        self.MAIL_REVIEW_SMTP_SERVER = sys_config.get('mail_smtp_server')
        if sys_config.get('mail_smtp_port'):
            self.MAIL_REVIEW_SMTP_PORT = int(sys_config.get('mail_smtp_port'))
        else:
            self.MAIL_REVIEW_SMTP_PORT = 25
        self.MAIL_REVIEW_FROM_ADDR = sys_config.get('mail_smtp_user')
        self.MAIL_REVIEW_FROM_PASSWORD = sys_config.get('mail_smtp_password')
        self.MAIL_SSL = sys_config.get('mail_ssl')

    @staticmethod
    def _add_attachment(filename):
        """
        添加附件
        :param filename:
        :return:
        """
        file_msg = email.mime.base.MIMEBase('application', 'octet-stream')
        file_msg.set_payload(open(filename, 'rb').read())
        # 附件如果有中文会出现乱码问题，加入gbk
        file_msg.add_header('Content-Disposition', 'attachment', filename=('gbk', '', filename.split('/')[-1]))
        encoders.encode_base64(file_msg)

        return file_msg

    def _send_email(self, subject, body, to, **kwargs):
        """
        发送邮件
        :param subject:
        :param body:
        :param to:
        :param kwargs:
        :return:
        """

        try:
            if to is None or to == ['']:
                logger.error('收件人为空，无法发送邮件')
                return
            list_cc = kwargs.get('list_cc_addr', [])

            # 构造MIMEMultipart对象做为根容器
            main_msg = email.mime.multipart.MIMEMultipart()

            # 添加文本内容
            text_msg = email.mime.text.MIMEText(body, 'plain', 'utf-8')
            main_msg.attach(text_msg)

            # 添加附件
            filename_list = kwargs.get('filename_list')
            if filename_list:
                for filename in kwargs['filename_list']:
                    file_msg = self._add_attachment(filename)
                    main_msg.attach(file_msg)

            # 消息内容:
            main_msg['Subject'] = Header(subject, "utf-8").encode()
            main_msg['From'] = formataddr(["archery 通知", self.MAIL_REVIEW_FROM_ADDR])
            main_msg['To'] = ','.join(to)
            main_msg['Cc'] = ', '.join(str(cc) for cc in list_cc)
            main_msg['Date'] = email.utils.formatdate()

            if self.MAIL_SSL:
                server = smtplib.SMTP_SSL(self.MAIL_REVIEW_SMTP_SERVER, self.MAIL_REVIEW_SMTP_PORT)  # 默认SSL端口是465
            else:
                server = smtplib.SMTP(self.MAIL_REVIEW_SMTP_SERVER, self.MAIL_REVIEW_SMTP_PORT)  # 默认端口是25

            # 如果提供的密码为空，则不需要登录
            if self.MAIL_REVIEW_FROM_PASSWORD != '':
                server.login(self.MAIL_REVIEW_FROM_ADDR, self.MAIL_REVIEW_FROM_PASSWORD)
            server.sendmail(self.MAIL_REVIEW_FROM_ADDR, to + list_cc, main_msg.as_string())
            server.quit()
            logger.debug('邮件推送成功')
        except Exception:
            logger.error('邮件推送失败\n{}'.format(traceback.format_exc()))

    @staticmethod
    def send_ding(url, content):
        """
        发送钉钉消息
        :param url:
        :param content:
        :return:
        """
        try:
            data = {
                "msgtype": "text",
                "text": {
                    "content": "{}".format(content)
                },
            }
            requests.post(url=url, json=data)
            logger.debug('钉钉推送成功')
        except Exception:
            logger.error('钉钉推送失败\n{}'.format(traceback.format_exc()))

    def send_email(self, subject, body, to, **kwargs):
        p = Thread(target=self._send_email, args=(subject, body, to), kwargs=kwargs)
        p.start()
