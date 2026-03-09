"""
每日任务调度器
每天17:30执行竞品监控任务
"""

import os
import sys
import json
import logging
import asyncio
import atexit
import msvcrt
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
from src.analyzer.price_trend import PriceTrendAnalyzer
from src.analyzer.promotion_analyzer import PromotionAnalyzer
from src.analyzer.review_analyzer import ReviewAnalyzer
from src.analyzer.checkout_analyzer import CheckoutAnalyzer
from src.analyzer.payment_monitor import PaymentMonitor
from src.reporter.report_builder import ReportBuilder
from src.reporter.mail_sender import MailSender

logger = logging.getLogger(__name__)


class DailyJob:
    """每日任务"""
    
    # 类级别的锁文件路径和句柄
    _lock_file_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'logs', '.daily_job.lock')
    _lock_handle = None
    
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
        self.price_trend_analyzer = PriceTrendAnalyzer(self.config)
        self.promotion_analyzer = PromotionAnalyzer(self.config)
        self.review_analyzer = ReviewAnalyzer(self.config)
        self.checkout_analyzer = CheckoutAnalyzer(self.config)
        self.payment_monitor = PaymentMonitor(self.config)
        self.report_builder = ReportBuilder(self.config)
        self.mail_sender = MailSender(self.config)
        
    async def run(self, date_str: str = None, discover_urls: bool = False):
        """
        执行每日任务
        
        Args:
            date_str: 日期字符串，默认今天
            discover_urls: 是否重新发现URL
        """
        # 尝试获取任务锁，防止重复执行
        if not self._acquire_lock():
            logger.warning("另一个任务实例正在运行，本次执行被跳过")
            return
            
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
        
        # 收集动态发现的URL并更新清单（用于后续分析）
        discovered_urls = self._collect_discovered_urls(crawl_results)
        if discovered_urls:
            logger.info(f"动态发现URL汇总: {len(discovered_urls)} 个新页面")
            # 合并到url_manifest供后续分析使用
            url_manifest = self._merge_discovered_urls(url_manifest, discovered_urls)
        
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
        
        # Step 5.2: 价格趋势分析（7日）
        logger.info("Step 5.2: 价格趋势分析...")
        price_trends = self.price_trend_analyzer.analyze_trends(date_str, days=7)
        
        # 导出CSV供Excel分析
        trend_csv_path = os.path.join(
            self.paths_config.get('report_output', './reports'),
            f'price_trend_{date_str}.csv'
        )
        self.price_trend_analyzer.export_to_csv(price_trends, trend_csv_path)
        logger.info(f"价格趋势数据已导出: {trend_csv_path}")
        
        # Step 5.3: 促销策略分析（B维度）
        logger.info("Step 5.3: 促销策略分析...")
        promotion_analysis = self.promotion_analyzer.analyze(parsed_data, date_str)
        
        # 导出促销数据CSV
        promo_csv_path = os.path.join(
            self.paths_config.get('report_output', './reports'),
            f'promotion_analysis_{date_str}.csv'
        )
        self.promotion_analyzer.export_to_csv(promotion_analysis, promo_csv_path)
        logger.info(f"促销分析数据已导出: {promo_csv_path}")
        
        # Step 5.4: 库存状态变化分析（P1）
        logger.info("Step 5.4: 库存状态变化分析...")
        stock_changes = self._analyze_stock_changes(parsed_data, date_str)
        
        # Step 5.5: 评价评分变化分析（P1）
        logger.info("Step 5.5: 评价评分变化分析...")
        rating_changes = self._analyze_rating_changes(parsed_data, date_str)
        
        # Step 5.6: 用户反馈深度分析
        logger.info("Step 5.6: 用户反馈深度分析...")
        review_analysis = self.review_analyzer.analyze(parsed_data, date_str)
        
        # 导出反馈分析CSV
        review_csv_path = os.path.join(
            self.paths_config.get('report_output', './reports'),
            f'review_analysis_{date_str}.csv'
        )
        self.review_analyzer.export_to_csv(review_analysis, review_csv_path)
        logger.info(f"反馈分析数据已导出: {review_csv_path}")
        
        # Step 5.7: 结算链路摩擦分析（新增）
        logger.info("Step 5.7: 结算链路摩擦分析...")
        checkout_analysis = self._analyze_checkout_flows(crawl_results)
        
        # Step 5.8: 支付方式监控（新增）
        logger.info("Step 5.8: 支付方式监控...")
        payment_analysis = self.payment_monitor.analyze(parsed_data, date_str)
        
        # 导出支付监控CSV
        payment_csv_path = os.path.join(
            self.paths_config.get('report_output', './reports'),
            f'payment_analysis_{date_str}.csv'
        )
        self.payment_monitor.export_to_csv(payment_analysis, payment_csv_path)
        logger.info(f"支付监控数据已导出: {payment_csv_path}")
        
        # Step 5.9: 新增游戏分析（C维度）
        logger.info("Step 5.9: 新增游戏分析...")
        new_games = self.diff_engine.analyze_new_games(crawl_results, date_str)
        
        # Step 6: 生成报告
        logger.info("Step 6: 生成报告...")
        tldr = self.change_classifier.generate_tldr(classified_changes)
        weak_signals = self.report_builder.identify_weak_signals(crawl_results)
        todos = self.report_builder.extract_todos(classified_changes)
        
        report = self.report_builder.build_report(
            date_str, crawl_results, classified_changes, tldr, weak_signals, todos,
            price_comparisons, stock_changes, rating_changes, new_games, price_trends,
            promotion_analysis, review_analysis, checkout_analysis, payment_analysis
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
        
    @classmethod
    def _acquire_lock(cls) -> bool:
        """
        获取文件锁，防止重复执行
        
        Returns:
            是否成功获取锁
        """
        try:
            # 确保日志目录存在
            os.makedirs(os.path.dirname(cls._lock_file_path), exist_ok=True)
            
            # 以独占模式打开锁文件
            cls._lock_handle = open(cls._lock_file_path, 'w')
            
            # 尝试获取文件锁（Windows使用msvcrt）
            msvcrt.locking(cls._lock_handle.fileno(), msvcrt.LK_NBLCK, 1)
            
            # 如果成功获取锁，写入PID
            cls._lock_handle.write(str(os.getpid()))
            cls._lock_handle.flush()
            
            # 注册退出时释放锁
            atexit.register(cls._release_lock)
            
            logger.info(f"成功获取任务锁，PID: {os.getpid()}")
            return True
            
        except (IOError, OSError, PermissionError):
            # 锁已被其他进程持有
            if cls._lock_handle:
                cls._lock_handle.close()
                cls._lock_handle = None
            logger.warning("任务锁已被其他进程持有，跳过本次执行")
            return False
    
    @classmethod
    def _release_lock(cls):
        """释放文件锁"""
        if cls._lock_handle:
            try:
                msvcrt.locking(cls._lock_handle.fileno(), msvcrt.LK_UNLCK, 1)
                cls._lock_handle.close()
                cls._lock_handle = None
                logger.info("任务锁已释放")
            except Exception as e:
                logger.debug(f"释放锁时出错: {e}")
    
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
    
    def _analyze_checkout_flows(self, crawl_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        分析结算链路摩擦
        
        Args:
            crawl_results: 抓取结果列表
            
        Returns:
            结算链路分析结果
        """
        site_checkout_data = {}
        
        for result in crawl_results:
            site_name = result.get('site_name', '')
            
            # 跳过第三方评价平台
            if site_name.lower() in ['trustpilot']:
                continue
            
            for page in result.get('pages', []):
                if not page.get('success'):
                    continue
                
                snapshot_path = page.get('snapshot_path')
                if not snapshot_path:
                    continue
                
                # 读取快照内容
                try:
                    html_path = f"{snapshot_path}.html"
                    text_path = f"{snapshot_path}.txt"
                    
                    with open(html_path, 'r', encoding='utf-8') as f:
                        html = f.read()
                    with open(text_path, 'r', encoding='utf-8') as f:
                        text = f.read()
                    
                    url = page.get('url', '')
                    
                    # 分析结算流程
                    checkout_data = self.checkout_analyzer.analyze(html, text, url)
                    
                    if checkout_data.get('has_checkout_flow') or checkout_data.get('page_type') in ['cart', 'checkout']:
                        if site_name not in site_checkout_data:
                            site_checkout_data[site_name] = []
                        site_checkout_data[site_name].append(checkout_data)
                        
                except Exception as e:
                    logger.debug(f"结算链路分析失败: {snapshot_path}, {e}")
                    continue
        
        # 对比各站点结算流程
        comparison = self.checkout_analyzer.compare_checkout_flows(site_checkout_data)
        
        return {
            'site_analysis': site_checkout_data,
            'comparison': comparison,
            'summary': self._generate_checkout_summary(site_checkout_data, comparison)
        }
    
    def _generate_checkout_summary(self, site_data: Dict[str, List], 
                                    comparison: Dict[str, Any]) -> str:
        """生成结算链路摘要"""
        lines = []
        
        # 各站点摩擦分数
        for site_name, analyses in site_data.items():
            if analyses:
                avg_score = sum(a.get('friction_score', 0) for a in analyses) / len(analyses)
                lines.append(f"- **{site_name}**: 摩擦分数 {avg_score:.0f}/100")
        
        # 最佳实践
        if comparison.get('best_practice_site'):
            lines.append(f"\n最佳实践: {comparison['best_practice_site']} (分数: {comparison.get('best_friction_score')})")
        
        return '\n'.join(lines) if lines else '未检测到结算流程数据'
    
    def _collect_discovered_urls(self, crawl_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        从抓取结果中收集动态发现的URL
        
        Args:
            crawl_results: 抓取结果列表
            
        Returns:
            动态发现的URL列表
        """
        discovered = []
        
        for site_result in crawl_results:
            site_name = site_result.get('site_name', '')
            
            for page in site_result.get('pages', []):
                # 检查是否有动态发现的商品
                discovered_products = page.get('discovered_products', [])
                
                for product in discovered_products:
                    discovered.append({
                        'site': site_name,
                        'name': product.get('name', ''),
                        'url': product.get('url', ''),
                        'source': product.get('source', '首页热门区域')
                    })
        
        return discovered
    
    def _merge_discovered_urls(self, url_manifest: Dict[str, Any], 
                               discovered_urls: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        将动态发现的URL合并到URL清单中
        
        Args:
            url_manifest: 原始URL清单
            discovered_urls: 动态发现的URL列表
            
        Returns:
            合并后的URL清单
        """
        # 深拷贝避免修改原始数据
        import copy
        merged_manifest = copy.deepcopy(url_manifest)
        
        # 按站点分组
        for item in discovered_urls:
            site_name = item.get('site', '')
            url = item.get('url', '')
            name = item.get('name', '')
            
            if not site_name or not url:
                continue
            
            # 确保站点存在
            if site_name not in merged_manifest:
                merged_manifest[site_name] = []
            
            # 检查URL是否已存在
            existing_urls = {p.get('url', '') for p in merged_manifest[site_name]}
            if url in existing_urls:
                continue
            
            # 添加动态发现的页面
            page_config = {
                'type': 'product',
                'url': url,
                'description': f"动态发现: {name}",
                'game': name,
                'discovered': True,
                'source': item.get('source', '首页热门区域')
            }
            
            # 根据站点添加抓取规则
            if 'lootbar.gg' in url:
                page_config['crawl_rules'] = {
                    'extract_sku_detail': True,
                    'extract_discount_tag': True
                }
            elif 'ldshop.gg' in url:
                page_config['crawl_rules'] = {
                    'set_currency_usd': True,
                    'extract_sku_detail': True,
                    'extract_payment_promo': True
                }
            
            merged_manifest[site_name].append(page_config)
            logger.debug(f"动态发现URL已合并: [{site_name}] {url}")
        
        return merged_manifest
                    

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
