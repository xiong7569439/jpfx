#!/usr/bin/env python3
"""
竞品策略监控系统 - 主入口

使用方法:
    python main.py                    # 运行今日监控任务
    python main.py --date 2024-01-15  # 运行指定日期任务
    python main.py --discover         # 重新发现URL
    python main.py --schedule         # 启动定时调度
    python main.py --init             # 初始化（发现URL并建立基线）
"""

import os
import sys
import argparse
import logging
from datetime import datetime

# 确保日志目录存在
os.makedirs('./logs', exist_ok=True)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(
            f'./logs/monitor_{datetime.now().strftime("%Y%m%d")}.log',
            encoding='utf-8'
        )
    ]
)

logger = logging.getLogger(__name__)


def run_monitor(date_str: str = None, discover_urls: bool = False):
    """运行监控任务"""
    from src.scheduler.daily_job import DailyJob
    import asyncio
    
    job = DailyJob()
    asyncio.run(job.run(date_str=date_str, discover_urls=discover_urls))


def start_scheduler():
    """启动定时调度器"""
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger
    from src.scheduler.daily_job import run_job
    import pytz
    
    scheduler = BackgroundScheduler(timezone=pytz.timezone('Asia/Shanghai'))
    
    # 每天17:00执行
    trigger = CronTrigger(hour=17, minute=0)
    scheduler.add_job(run_job, trigger, id='daily_competitor_monitor')
    
    scheduler.start()
    logger.info("定时调度器已启动，每天17:00执行任务")
    
    try:
        # 保持程序运行
        while True:
            import time
            time.sleep(60)
    except KeyboardInterrupt:
        logger.info("正在关闭调度器...")
        scheduler.shutdown()


def init_system():
    """初始化系统"""
    logger.info("=" * 50)
    logger.info("初始化竞品监控系统")
    logger.info("=" * 50)
    
    # 1. 检查依赖
    try:
        import playwright
        logger.info("Playwright 已安装")
    except ImportError:
        logger.error("Playwright 未安装，请运行: pip install -r requirements.txt")
        return
        
    # 2. 检查配置
    config_files = ['./config/sites.yaml', './config/scheduler.yaml', './config/settings.yaml']
    for f in config_files:
        if os.path.exists(f):
            logger.info(f"配置存在: {f}")
        else:
            logger.error(f"配置缺失: {f}")
            return
            
    # 3. 检查目录结构
    dirs = ['./data/snapshots', './data/parsed', './data/history', './reports', './logs']
    for d in dirs:
        os.makedirs(d, exist_ok=True)
        logger.info(f"目录就绪: {d}")
        
    logger.info("=" * 50)
    logger.info("初始化完成")
    logger.info("=" * 50)
    logger.info("下一步:")
    logger.info("  1. 配置邮件: 编辑 config/settings.yaml")
    logger.info("  2. 发现URL: 运行 python main.py --discover")
    logger.info("  3. 建立基线: 运行 python main.py")
    logger.info("  4. 启动定时: 运行 python main.py --schedule")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='竞品策略监控系统')
    parser.add_argument('--date', type=str, help='指定日期 (YYYY-MM-DD)')
    parser.add_argument('--discover', action='store_true', help='重新发现URL')
    parser.add_argument('--schedule', action='store_true', help='启动定时调度')
    parser.add_argument('--init', action='store_true', help='初始化系统')
    
    args = parser.parse_args()
    
    if args.init:
        init_system()
    elif args.schedule:
        start_scheduler()
    else:
        date_str = args.date
        discover = args.discover
        run_monitor(date_str=date_str, discover_urls=discover)


if __name__ == '__main__':
    main()
