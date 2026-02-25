"""
报告生成模块
"""

from .report_builder import ReportBuilder
from .mail_sender import MailSender

__all__ = [
    'ReportBuilder',
    'MailSender',
]
