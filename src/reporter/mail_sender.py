"""
邮件发送器
发送日报邮件
"""

import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any

logger = logging.getLogger(__name__)


class MailSender:
    """邮件发送器"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.mail_config = config.get('mail', {})
        
    def send_report(self, report: str, date_str: str) -> bool:
        """
        发送日报邮件
        
        Args:
            report: 报告内容
            date_str: 日期字符串
            
        Returns:
            是否发送成功
        """
        if not self.mail_config.get('enabled', False):
            logger.info("邮件发送已禁用")
            return False
            
        # 检查配置
        smtp_host = self.mail_config.get('smtp_host')
        smtp_port = self.mail_config.get('smtp_port', 587)
        smtp_user = self.mail_config.get('smtp_user')
        smtp_password = self.mail_config.get('smtp_password')
        recipient = self.mail_config.get('recipient')
        
        if not all([smtp_host, smtp_user, smtp_password, recipient]):
            logger.error("邮件配置不完整，无法发送")
            return False
            
        try:
            # 构建邮件
            subject = self.mail_config.get('subject_template', '竞品策略变动日报 - {date}')
            subject = subject.format(date=date_str)
            
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = smtp_user
            msg['To'] = recipient
            
            # 添加纯文本内容
            msg.attach(MIMEText(report, 'plain', 'utf-8'))
            
            # 连接SMTP并发送
            with smtplib.SMTP(smtp_host, smtp_port) as server:
                if self.mail_config.get('use_tls', True):
                    server.starttls()
                server.login(smtp_user, smtp_password)
                server.send_message(msg)
                
            logger.info(f"邮件发送成功: {recipient}")
            return True
            
        except Exception as e:
            logger.error(f"邮件发送失败: {e}")
            return False
            
    def send_test_email(self) -> bool:
        """发送测试邮件"""
        test_report = """# 竞品策略监控日报 - 测试

这是测试邮件，用于验证邮件配置是否正确。

如果收到此邮件，说明邮件发送功能正常。
"""
        return self.send_report(test_report, "测试")
