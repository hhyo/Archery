#!/usr/bin/env python
# -*- coding: UTF-8 -*-

from multiprocessing import Process
import email
from email import encoders
from email.header import Header
from email.mime.text import MIMEText
from email.utils import parseaddr, formataddr
import smtplib

from django.conf import settings


class MailSender(object):

    def __init__(self):
        try:
            self.MAIL_REVIEW_SMTP_SERVER = getattr(settings, 'MAIL_REVIEW_SMTP_SERVER')
            self.MAIL_REVIEW_SMTP_PORT = int(getattr(settings, 'MAIL_REVIEW_SMTP_PORT'))
            self.MAIL_REVIEW_FROM_ADDR = getattr(settings, 'MAIL_REVIEW_FROM_ADDR')
            self.MAIL_REVIEW_FROM_PASSWORD = getattr(settings, 'MAIL_REVIEW_FROM_PASSWORD')
            self.MAIL_REVIEW_DBA_ADDR = getattr(settings, 'MAIL_REVIEW_DBA_ADDR')

        except AttributeError as a:
            print("Error: %s" % a)
        except ValueError as v:
            print("Error: %s" % v)

    def _format_addr(self, s):
        name, addr = parseaddr(s)
        return formataddr((Header(name, 'utf-8').encode(), addr))

    def _add_attachment(self, filename):
        '''''
            添加附件
        '''
        file_msg = email.mime.base.MIMEBase('application', 'octet-stream')
        file_msg.set_payload(open(filename, 'rb').read())
        # 附件如果有中文会出现乱码问题，加入gbk
        file_msg.add_header('Content-Disposition', 'attachment', filename=('gbk', '', filename.split('/')[-1]))
        encoders.encode_base64(file_msg)

        return file_msg

    def _send(self, strTitle, strContent, listToAddr, filename_list=None):
        '''''
            发送邮件
        '''
        # 构造MIMEMultipart对象做为根容器
        main_msg = email.mime.multipart.MIMEMultipart()

        # 添加文本内容
        text_msg = email.mime.text.MIMEText(strContent, 'plain', 'utf-8')
        main_msg.attach(text_msg)

        # 添加附件
        if filename_list:
            for filename in filename_list:
                file_msg = self._add_attachment(filename)
                main_msg.attach(file_msg)

        # 收发件人地址和邮件标题:
        main_msg['From'] = formataddr(["archer 通知", self.MAIL_REVIEW_FROM_ADDR])
        main_msg['To'] = ','.join(listToAddr)
        main_msg['Subject'] = Header(strTitle, "utf-8").encode()
        main_msg['Date'] = email.utils.formatdate()

        server = smtplib.SMTP(self.MAIL_REVIEW_SMTP_SERVER, self.MAIL_REVIEW_SMTP_PORT)  # SMTP协议默认端口是25
        # server.set_debuglevel(1)

        # 如果提供的密码为空，则不需要登录SMTP server
        if self.MAIL_REVIEW_FROM_PASSWORD != '':
            server.login(self.MAIL_REVIEW_FROM_ADDR, self.MAIL_REVIEW_FROM_PASSWORD)
        sendResult = server.sendmail(self.MAIL_REVIEW_FROM_ADDR, listToAddr, main_msg.as_string())
        server.quit()

    # 调用方应该调用此方法，采用子进程方式异步阻塞地发送邮件，避免邮件服务挂掉影响archer主服务
    def sendEmail(self, strTitle, strContent, listToAddr, filename_list=None):
        p = Process(target=self._send, args=(strTitle, strContent, listToAddr, filename_list))
        p.start()
