#!/usr/bin/env python
# -*- coding: UTF-8 -*-


import time
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

    def _send(self, strTitle, strContent, listToAddr):
        msg = MIMEText(strContent, 'plain', 'utf-8')
        # 收件人地址:

        msg['From'] = self._format_addr(self.MAIL_REVIEW_FROM_ADDR)
        #msg['To'] = self._format_addr(listToAddr)
        msg['To'] = ','.join(listToAddr)
        msg['Subject'] = Header(strTitle, "utf-8").encode()

        server = smtplib.SMTP(self.MAIL_REVIEW_SMTP_SERVER, self.MAIL_REVIEW_SMTP_PORT)  # SMTP协议默认端口是25
        #server.set_debuglevel(1)

        #如果提供的密码为空，则不需要登录SMTP server
        if self.MAIL_REVIEW_FROM_PASSWORD != '':
            server.login(self.MAIL_REVIEW_FROM_ADDR, self.MAIL_REVIEW_FROM_PASSWORD)
        sendResult = server.sendmail(self.MAIL_REVIEW_FROM_ADDR, listToAddr, msg.as_string())
        server.quit()

    #调用方应该调用此方法，采用子进程方式异步阻塞地发送邮件，避免邮件服务挂掉影响archer主服务
    def sendEmail(self, strTitle, strContent, listToAddr):
        p = Process(target=self._send, args=(strTitle, strContent, listToAddr))
        p.start()
