"""
竞品爬虫主模块
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from .browser import Crawler

logger = logging.getLogger(__name__)


class CompetitorCrawler:
    """竞品爬虫"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.sites_config = config.get('competitors', [])
        self.paths_config = config.get('paths', {})
        
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
                
                if not url:
                    logger.warning(f"页面URL为空: {site_name}/{page_type}")
                    continue
                    
                logger.info(f"抓取页面: {url}")
                
                # 抓取页面
                content = await crawler.fetch_page(url, wait_for)
                
                # 保存快照
                snapshot_path = self._save_snapshot(
                    site_name, page_type, url, content, date_str
                )
                
                page_result = {
                    'type': page_type,
                    'url': url,
                    'final_url': content.get('url', url),
                    'success': content.get('success', False),
                    'snapshot_path': snapshot_path,
                    'title': content.get('title', ''),
                    'meta_description': content.get('meta_description', ''),
                    'error': content.get('error', '')
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
                
            result = await self.crawl_site(site, pages, date_str)
            all_results.append(result)
            
        return all_results
