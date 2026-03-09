"""
竞品爬虫主模块
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional, Set
from .browser import Crawler, PageOperator

logger = logging.getLogger(__name__)


class CompetitorCrawler:
    """竞品爬虫"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.sites_config = config.get('competitors', [])
        self.paths_config = config.get('paths', {})
        self.discovered_urls_cache: Dict[str, List[Dict[str, str]]] = {}  # 缓存动态发现的URL
        
    async def crawl_site(self, site: Dict[str, Any], pages: List[Dict[str, str]], 
                         date_str: str) -> Dict[str, Any]:
        """
        爬取单个站点
            
        Args:
            site: 站点配置
            pages: 要抓取的页面列表
            date_str: 日期字符串
                
        Returns:
            抓取结果
        """
        site_name = site['name']
        logger.info(f"开始爬取站点: {site_name}")
            
        results = {
            'site_name': site_name,
            'domain': site['domain'],
            'date': date_str,
            'pages': [],
            'success_count': 0,
            'fail_count': 0
        }
            
        async with Crawler(self.config) as crawler:
            for page_info in pages:
                page_type = page_info.get('type', 'unknown')
                url = page_info.get('url')
                wait_for = page_info.get('wait_for')
                crawl_rules = page_info.get('crawl_rules', {})
                    
                if not url:
                    logger.warning(f"页面URL为空: {site_name}/{page_type}")
                    continue
                        
                logger.info(f"抓取页面: {url}")
                    
                # 检测是否为SPA页面
                is_spa = site.get('is_spa', False) or 'lootbar.gg' in url
                spa_wait_time = page_info.get('spa_wait_time', 5000)
                    
                # 抓取页面
                content = await crawler.fetch_page(url, wait_for, is_spa, spa_wait_time)
                    
                # 専项抓取数据（需要活跃页面对象）
                specialist_data = {}
                if content.get('success') and crawl_rules and crawler.browser_manager:
                    try:
                        page_obj = await crawler.browser_manager.new_page()
                        op = PageOperator(page_obj, self.config)
                        await op.goto(url, wait_for, is_spa, spa_wait_time)
    
                        # LootBar首页专项
                        if 'lootbar.gg' in url and page_type == 'homepage':
                            if crawl_rules.get('handle_popup'):
                                popup = await op.lootbar_handle_popup()
                                if popup:
                                    specialist_data['popup'] = popup
                            if crawl_rules.get('extract_carousel'):
                                specialist_data['carousel_banners'] = await op.lootbar_extract_carousel(
                                    crawl_rules.get('carousel_selector')
                                )
                            if crawl_rules.get('extract_trending'):
                                specialist_data['trending_games'] = await op.lootbar_extract_trending(
                                    crawl_rules.get('trending_selector'),
                                    crawl_rules.get('trending_count', 5)
                                )
    
                        # LDShop首页专项
                        elif 'ldshop.gg' in url and page_type == 'homepage':
                            if crawl_rules.get('scroll_to_promotions') and crawl_rules.get('extract_announcements'):
                                specialist_data['announcements'] = await op.ldshop_extract_announcements(
                                    crawl_rules.get('announcement_count', 2)
                                )
    
                        # LDShop产品页专项
                        elif 'ldshop.gg' in url and page_type == 'product':
                            if crawl_rules.get('set_currency_usd'):
                                await op.ldshop_set_currency_usd()
                            if crawl_rules.get('extract_payment_promo'):
                                specialist_data['payment_promos'] = await op.ldshop_extract_payment_promos()
    
                        await page_obj.close()
                    except Exception as e:
                        logger.warning(f"专项抓取失败: {url}, {e}")
    
                # 保存快照
                snapshot_path = self._save_snapshot(
                    site_name, page_type, url, content, date_str
                )
                
                # 修改：移除了死代码 - 动态发现逻辑已整合到专项抓取中
                # 原代码在此处引用已关闭的 page_obj 会导致错误
                # 动态发现功能现通过 op.discover_hot_products() 在专项抓取阶段完成
                discovered_products = []
                    
                page_result = {
                    'type': page_type,
                    'url': url,
                    'final_url': content.get('url', url),
                    'success': content.get('success', False),
                    'snapshot_path': snapshot_path,
                    'title': content.get('title', ''),
                    'meta_description': content.get('meta_description', ''),
                    'error': content.get('error', ''),
                    'specialist_data': specialist_data,  # 新增专项抓取数据
                    'discovered_products': discovered_products  # 动态发现的商品
                }
                    
                if content.get('success'):
                    results['success_count'] += 1
                else:
                    results['fail_count'] += 1
                        
                results['pages'].append(page_result)
                    
        logger.info(f"站点爬取完成: {site_name}, 成功: {results['success_count']}, 失败: {results['fail_count']}")
        return results
        
    def _save_snapshot(self, site_name: str, page_type: str, url: str, 
                       content: Dict[str, Any], date_str: str) -> str:
        """保存页面快照"""
        snapshot_dir = os.path.join(
            self.paths_config.get('snapshot_base', './data/snapshots'),
            date_str,
            site_name
        )
        os.makedirs(snapshot_dir, exist_ok=True)
        
        # 生成文件名
        safe_name = f"{page_type}_{self._url_to_filename(url)}"
        base_path = os.path.join(snapshot_dir, safe_name)
        
        # 保存HTML
        html_path = f"{base_path}.html"
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(content.get('html', ''))
            
        # 保存文本
        text_path = f"{base_path}.txt"
        with open(text_path, 'w', encoding='utf-8') as f:
            f.write(content.get('text', ''))
            
        # 保存元数据
        meta_path = f"{base_path}.json"
        meta = {
            'url': url,
            'final_url': content.get('url', url),
            'title': content.get('title', ''),
            'meta_description': content.get('meta_description', ''),
            'success': content.get('success', False),
            'error': content.get('error', ''),
            'crawl_time': datetime.now().isoformat()
        }
        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
            
        return base_path
        
    def _url_to_filename(self, url: str) -> str:
        """将URL转换为安全文件名"""
        # 移除协议
        url = url.replace('https://', '').replace('http://', '')
        # 替换特殊字符
        url = url.replace('/', '_').replace('?', '_').replace('&', '_')
        # 限制长度
        if len(url) > 100:
            url = url[:100]
        return url
        
    # 修改：移除了 _discover_hot_products 方法
    # 该方法逻辑已整合到专项抓取阶段，通过 op.discover_hot_products() 直接调用

    def get_discovered_urls(self, site_name: str, url_manifest: Dict[str, Any]) -> List[Dict[str, str]]:
        """
        获取动态发现的URL列表（转换为标准页面格式）
        
        Args:
            site_name: 站点名称
            url_manifest: 原始URL清单
            
        Returns:
            动态发现的URL页面列表
        """
        discovered_pages = []
        
        # 获取缓存的动态发现结果
        discovered_products = self.discovered_urls_cache.get(site_name, [])
        
        # 获取已有的URL集合（用于去重）
        existing_urls = set()
        for page in url_manifest.get(site_name, []):
            existing_urls.add(page.get('url', ''))
        
        # 转换发现的商品为页面格式
        for product in discovered_products:
            url = product.get('url', '')
            name = product.get('name', '')
            
            # 跳过已存在的URL
            if url in existing_urls:
                continue
            
            # 构建页面配置
            page_config = {
                'type': 'product',
                'url': url,
                'description': f"动态发现: {name}",
                'game': name,
                'discovered': True,  # 标记为动态发现
                'source': product.get('source', '首页热门区域')
            }
            
            # 根据站点添加特定的抓取规则
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
            
            discovered_pages.append(page_config)
            existing_urls.add(url)
        
        return discovered_pages
    
    async def crawl_all(self, url_manifest: Dict[str, Any], date_str: str) -> List[Dict[str, Any]]:
        """
        爬取所有站点
        
        Args:
            url_manifest: URL清单
            date_str: 日期字符串
            
        Returns:
            所有站点抓取结果
        """
        all_results = []
        
        for site in self.sites_config:
            if not site.get('enabled', True):
                continue
                
            site_name = site['name']
            pages = url_manifest.get(site_name, [])
            
            if not pages:
                logger.warning(f"站点 {site_name} 没有配置页面URL")
                continue
            
            # 第一阶段：抓取预定义的URL（包括首页）
            result = await self.crawl_site(site, pages, date_str)
            
            # 第二阶段：抓取动态发现的URL（如果首页启用了动态发现）
            discovered_pages = self.get_discovered_urls(site_name, url_manifest)
            if discovered_pages:
                logger.info(f"[{site_name}] 开始抓取 {len(discovered_pages)} 个动态发现的页面")
                
                # 创建临时站点配置用于抓取动态URL
                temp_site = site.copy()
                discovered_result = await self.crawl_site(temp_site, discovered_pages, date_str)
                
                # 合并结果
                result['pages'].extend(discovered_result['pages'])
                result['success_count'] += discovered_result['success_count']
                result['fail_count'] += discovered_result['fail_count']
                result['discovered_count'] = len(discovered_pages)
            
            all_results.append(result)
            
        return all_results
