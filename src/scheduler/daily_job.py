"""
每日任务调度器
每天17:30执行竞品监控任务
"""

import os
import sys
import json
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.config_loader import get_config
from src.collector.crawler import CompetitorCrawler
from src.parser.data_extractor import DataExtractor
from src.parser.page_navigator import PageNavigator
from src.analyzer.diff_engine import DiffEngine
from src.analyzer.change_classifier import ChangeClassifier
from src.analyzer.price_comparison import PriceComparisonAnalyzer
from src.reporter.report_builder import ReportBuilder
from src.reporter.mail_sender import MailSender

logger = logging.getLogger(__name__)


class DailyJob:
    """每日任务"""
    
    def __init__(self, config_dir: str = "./config"):
        self.config = get_config(config_dir)
        self.paths_config = self.config.get('paths', {})
        
        # 初始化组件
        self.crawler = CompetitorCrawler(self.config)
        self.data_extractor = DataExtractor()
        self.page_navigator = PageNavigator(self.config)
        self.diff_engine = DiffEngine(self.config)
        self.change_classifier = ChangeClassifier()
        self.price_analyzer = PriceComparisonAnalyzer(self.config)
        self.report_builder = ReportBuilder(self.config)
        self.mail_sender = MailSender(self.config)
        
    async def run(self, date_str: str = None, discover_urls: bool = False):
        """
        执行每日任务
        
        Args:
            date_str: 日期字符串，默认今天
            discover_urls: 是否重新发现URL
        """
        if date_str is None:
            date_str = datetime.now().strftime('%Y-%m-%d')
            
        logger.info(f"=" * 50)
        logger.info(f"开始执行竞品监控任务: {date_str}")
        logger.info(f"=" * 50)
        
        # Step 0: 检查昨日快照
        yesterday_str = self.diff_engine.get_yesterday_date(date_str)
        has_baseline = self._check_baseline_exists(yesterday_str)
        
        if not has_baseline:
            logger.warning(f"未找到昨日快照 ({yesterday_str})，将建立基线")
            
        # Step 1: 获取URL清单
        url_manifest = self._get_url_manifest(discover_urls)
        
        if not url_manifest:
            logger.error("URL清单为空，任务终止")
            return
            
        # Step 2: 抓取今日页面
        logger.info("Step 2: 抓取今日页面...")
        crawl_results = await self.crawler.crawl_all(url_manifest, date_str)
        
        # Step 3: 提取结构化数据
        logger.info("Step 3: 提取结构化数据...")
        self._extract_and_save_data(crawl_results, date_str)
        
        # Step 4: 差异对比
        logger.info("Step 4: 差异对比...")
        if has_baseline:
            changes = self.diff_engine.analyze_all_changes(crawl_results, date_str)
        else:
            changes = []
            logger.info("首次运行，跳过差异对比，建立基线")
            
        # Step 5: 变化归类
        logger.info("Step 5: 变化归类...")
        classified_changes = self.change_classifier.classify_changes(changes)
        
        # Step 5.1: 竞品间价格对比分析（P0）
        logger.info("Step 5.1: 竞品间价格对比分析...")
        parsed_data = self.price_analyzer.load_parsed_data(date_str)
        price_comparisons = self.price_analyzer.analyze(parsed_data, date_str)
        
        # Step 5.2: 库存状态变化分析（P1）
        logger.info("Step 5.2: 库存状态变化分析...")
        stock_changes = self._analyze_stock_changes(parsed_data, date_str)
        
        # Step 5.3: 评价评分变化分析（P1）
        logger.info("Step 5.3: 评价评分变化分析...")
        rating_changes = self._analyze_rating_changes(parsed_data, date_str)
        
        # Step 5.4: 新增游戏分析（C维度）
        logger.info("Step 5.4: 新增游戏分析...")
        new_games = self.diff_engine.analyze_new_games(crawl_results, date_str)
        
        # Step 6: 生成报告
        logger.info("Step 6: 生成报告...")
        tldr = self.change_classifier.generate_tldr(classified_changes)
        weak_signals = self.report_builder.identify_weak_signals(crawl_results)
        todos = self.report_builder.extract_todos(classified_changes)
        
        report = self.report_builder.build_report(
            date_str, crawl_results, classified_changes, tldr, weak_signals, todos,
            price_comparisons, stock_changes, rating_changes, new_games
        )
        
        # 保存报告
        report_path = self.report_builder.save_report(report, date_str)
        logger.info(f"报告已保存: {report_path}")
        
        # Step 7: 发送邮件
        logger.info("Step 7: 发送邮件...")
        success = self.mail_sender.send_report(report, date_str)
        if success:
            logger.info("邮件发送成功")
        else:
            logger.warning("邮件发送失败或未配置")
            
        logger.info(f"=" * 50)
        logger.info(f"任务完成: {date_str}")
        logger.info(f"=" * 50)
        
    def _check_baseline_exists(self, date_str: str) -> bool:
        """检查基线是否存在"""
        snapshot_base = self.paths_config.get('snapshot_base', './data/snapshots')
        snapshot_dir = os.path.join(snapshot_base, date_str)
        return os.path.exists(snapshot_dir) and len(os.listdir(snapshot_dir)) > 0
        
    def _get_url_manifest(self, discover_urls: bool = False) -> Dict[str, Any]:
        """获取URL清单"""
        manifest_path = self.paths_config.get('url_manifest', './config/url_manifest.json')
        
        if discover_urls or not os.path.exists(manifest_path):
            logger.info("需要发现URL...")
            # URL发现逻辑将在Phase 6实现
            # 现在返回空，需要手动配置初始URL
            return {}
        else:
            return self.page_navigator.load_manifest(manifest_path)
            
    def _extract_and_save_data(self, crawl_results: List[Dict[str, Any]], date_str: str):
        """提取并保存结构化数据"""
        parsed_base = self.paths_config.get('parsed_base', './data/parsed')
        
        for result in crawl_results:
            site_name = result['site_name']
            
            for page in result.get('pages', []):
                if not page.get('success'):
                    continue
                    
                snapshot_path = page.get('snapshot_path')
                if not snapshot_path:
                    continue
                    
                # 提取数据
                data = self.data_extractor.extract_from_snapshot(snapshot_path)
                
                # 保存解析结果
                parsed_dir = os.path.join(parsed_base, date_str, site_name)
                os.makedirs(parsed_dir, exist_ok=True)
                
                filename = os.path.basename(snapshot_path) + '.json'
                parsed_path = os.path.join(parsed_dir, filename)
                
                with open(parsed_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                    
    def _analyze_stock_changes(self, parsed_data: Dict[str, Any], date_str: str) -> List[Dict[str, Any]]:
        """分析库存状态变化（P1）"""
        changes = []
        yesterday_str = self.diff_engine.get_yesterday_date(date_str)
        yesterday_data = self.price_analyzer.load_parsed_data(yesterday_str)
        
        for site_name, pages in parsed_data.items():
            for page_type, data in pages.items():
                if page_type != 'product':
                    continue
                    
                game = data.get('game', '')
                current_stock = data.get('stock_status', {})
                
                # 对比昨日数据
                if site_name in yesterday_data and page_type in yesterday_data[site_name]:
                    yesterday_stock = yesterday_data[site_name][page_type].get('stock_status', {})
                    
                    # 检测状态变化
                    if current_stock.get('out_of_stock') != yesterday_stock.get('out_of_stock'):
                        if current_stock.get('out_of_stock'):
                            changes.append({
                                'site': site_name,
                                'game': game,
                                'status': '新缺货',
                                'type': 'stock_out'
                            })
                        else:
                            changes.append({
                                'site': site_name,
                                'game': game,
                                'status': '恢复有货',
                                'type': 'stock_in'
                            })
                            
        return changes
        
    def _analyze_rating_changes(self, parsed_data: Dict[str, Any], date_str: str) -> List[Dict[str, Any]]:
        """分析评价评分变化（P1）"""
        changes = []
        yesterday_str = self.diff_engine.get_yesterday_date(date_str)
        yesterday_data = self.price_analyzer.load_parsed_data(yesterday_str)
        
        for site_name, pages in parsed_data.items():
            for page_type, data in pages.items():
                if page_type != 'product':
                    continue
                    
                game = data.get('game', '')
                current_rating = data.get('rating')
                current_reviews = data.get('review_count')
                
                if site_name in yesterday_data and page_type in yesterday_data[site_name]:
                    yesterday_data_page = yesterday_data[site_name][page_type]
                    yesterday_rating = yesterday_data_page.get('rating')
                    yesterday_reviews = yesterday_data_page.get('review_count')
                    
                    # 检测评分变化
                    if current_rating != yesterday_rating or current_reviews != yesterday_reviews:
                        rating_change = ''
                        if current_rating and yesterday_rating:
                            diff = current_rating - yesterday_rating
                            if diff > 0:
                                rating_change = f'上升{diff:.1f}'
                            elif diff < 0:
                                rating_change = f'下降{abs(diff):.1f}'
                                
                        review_change = ''
                        if current_reviews and yesterday_reviews:
                            diff = current_reviews - yesterday_reviews
                            if diff > 0:
                                review_change = f'+{diff}'
                                
                        changes.append({
                            'site': site_name,
                            'game': game,
                            'rating': current_rating,
                            'review_count': current_reviews,
                            'change': f'评分{rating_change}, 评价{review_change}' if rating_change or review_change else '无变化'
                        })
                        
        return changes
                    

def run_job():
    """运行任务的入口函数（供调度器调用）"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('./logs/daily_job.log', encoding='utf-8')
        ]
    )
    
    job = DailyJob()
    asyncio.run(job.run())


if __name__ == '__main__':
    run_job()
