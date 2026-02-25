"""
差异分析引擎
对比今日与昨日快照，发现变化
"""

import os
import json
import difflib
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger(__name__)


class DiffEngine:
    """差异分析引擎"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.paths_config = config.get('paths', {})
        
    def get_yesterday_date(self, today_str: str) -> str:
        """获取昨天日期字符串"""
        today = datetime.strptime(today_str, '%Y-%m-%d')
        yesterday = today - timedelta(days=1)
        return yesterday.strftime('%Y-%m-%d')
        
    def load_snapshot_data(self, site_name: str, page_type: str, 
                           date_str: str) -> Optional[Dict[str, Any]]:
        """加载指定日期的快照数据"""
        snapshot_dir = os.path.join(
            self.paths_config.get('snapshot_base', './data/snapshots'),
            date_str,
            site_name
        )
        
        # 查找匹配的文件
        if not os.path.exists(snapshot_dir):
            return None
            
        for filename in os.listdir(snapshot_dir):
            if filename.startswith(f"{page_type}_") and filename.endswith('.json'):
                meta_path = os.path.join(snapshot_dir, filename)
                try:
                    with open(meta_path, 'r', encoding='utf-8') as f:
                        meta = json.load(f)
                        
                    # 读取文本内容
                    text_path = meta_path.replace('.json', '.txt')
                    if os.path.exists(text_path):
                        with open(text_path, 'r', encoding='utf-8') as f:
                            meta['text'] = f.read()
                            
                    return meta
                except Exception as e:
                    logger.error(f"加载快照失败: {meta_path}, 错误: {e}")
                    
        return None
        
    def compare_text(self, old_text: str, new_text: str) -> List[Dict[str, Any]]:
        """
        对比文本差异
        
        Returns:
            差异列表，每项包含type(add/remove/change)和content
        """
        old_lines = old_text.splitlines()
        new_lines = new_text.splitlines()
        
        differ = difflib.Differ()
        diff = list(differ.compare(old_lines, new_lines))
        
        changes = []
        for line in diff:
            if line.startswith('+ '):
                changes.append({
                    'type': 'add',
                    'content': line[2:]
                })
            elif line.startswith('- '):
                changes.append({
                    'type': 'remove',
                    'content': line[2:]
                })
                
        return changes
        
    def compare_structured_data(self, old_data: Dict[str, Any], 
                                 new_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        对比结构化数据差异
        
        Returns:
            字段差异列表
        """
        differences = []
        
        # 对比价格
        old_prices = {f"{p['value']}_{p['currency']}": p for p in old_data.get('prices', [])}
        new_prices = {f"{p['value']}_{p['currency']}": p for p in new_data.get('prices', [])}
        
        # 新增价格
        for key, price in new_prices.items():
            if key not in old_prices:
                differences.append({
                    'field': 'price',
                    'type': 'add',
                    'value': price,
                    'description': f"新增价格: {price['raw']}"
                })
                
        # 移除价格
        for key, price in old_prices.items():
            if key not in new_prices:
                differences.append({
                    'field': 'price',
                    'type': 'remove',
                    'value': price,
                    'description': f"移除价格: {price['raw']}"
                })
                
        # 对比折扣
        old_discounts = set(d['raw'] for d in old_data.get('discounts', []))
        new_discounts = set(d['raw'] for d in new_data.get('discounts', []))
        
        added_discounts = new_discounts - old_discounts
        for d in added_discounts:
            differences.append({
                'field': 'discount',
                'type': 'add',
                'value': d,
                'description': f"新增折扣: {d}"
            })
            
        # 对比支付方式
        old_payments = set(old_data.get('payments', []))
        new_payments = set(new_data.get('payments', []))
        
        added_payments = new_payments - old_payments
        for p in added_payments:
            differences.append({
                'field': 'payment',
                'type': 'add',
                'value': p,
                'description': f"新增支付方式: {p}"
            })
            
        removed_payments = old_payments - new_payments
        for p in removed_payments:
            differences.append({
                'field': 'payment',
                'type': 'remove',
                'value': p,
                'description': f"移除支付方式: {p}"
            })
            
        # 对比时效
        old_delivery = set(d['raw'] for d in old_data.get('delivery_time', []))
        new_delivery = set(d['raw'] for d in new_data.get('delivery_time', []))
        
        added_delivery = new_delivery - old_delivery
        for d in added_delivery:
            differences.append({
                'field': 'delivery',
                'type': 'add',
                'value': d,
                'description': f"新增时效承诺: {d}"
            })
            
        # 对比促销
        old_promos = set(p['raw'] for p in old_data.get('promotions', []))
        new_promos = set(p['raw'] for p in new_data.get('promotions', []))
        
        added_promos = new_promos - old_promos
        for p in added_promos:
            differences.append({
                'field': 'promotion',
                'type': 'add',
                'value': p,
                'description': f"新增促销: {p}"
            })
            
        return differences
        
    def analyze_page_changes(self, site_name: str, page_type: str, 
                             today_str: str) -> Optional[Dict[str, Any]]:
        """
        分析单个页面的变化
        
        Returns:
            变化结果，如果无昨日数据返回None
        """
        yesterday_str = self.get_yesterday_date(today_str)
        
        # 加载昨日数据
        old_data = self.load_snapshot_data(site_name, page_type, yesterday_str)
        if not old_data:
            logger.info(f"无昨日数据: {site_name}/{page_type}")
            return None
            
        # 加载今日数据
        new_data = self.load_snapshot_data(site_name, page_type, today_str)
        if not new_data:
            logger.warning(f"无今日数据: {site_name}/{page_type}")
            return None
            
        # 对比文本
        text_changes = self.compare_text(
            old_data.get('text', ''),
            new_data.get('text', '')
        )
        
        # 对比结构化数据
        # 这里需要重新提取结构化数据，或者从parsed目录加载
        structured_changes = []  # 将在外部填充
        
        return {
            'site_name': site_name,
            'page_type': page_type,
            'url': new_data.get('url', ''),
            'title_changed': old_data.get('title') != new_data.get('title'),
            'old_title': old_data.get('title', ''),
            'new_title': new_data.get('title', ''),
            'text_changes': text_changes,
            'structured_changes': structured_changes,
            'has_changes': len(text_changes) > 0 or len(structured_changes) > 0
        }
        
    def analyze_new_games(self, crawl_results: List[Dict[str, Any]], 
                          today_str: str) -> List[Dict[str, Any]]:
        """
        分析各站点新增的游戏
        
        Returns:
            新增游戏列表
        """
        new_games = []
        yesterday_str = self.get_yesterday_date(today_str)
        
        for site_result in crawl_results:
            site_name = site_result['site_name']
            
            # 获取今日抓取的游戏列表
            today_games = set()
            for page in site_result.get('pages', []):
                if page.get('success') and page.get('type') == 'product':
                    game_name = self._extract_game_from_page(page)
                    if game_name:
                        today_games.add(game_name)
                        
            # 获取昨日抓取的游戏列表
            yesterday_games = set()
            yesterday_data = self.load_snapshot_data(site_name, 'homepage', yesterday_str)
            if yesterday_data:
                # 从昨日首页提取游戏列表
                yesterday_text = yesterday_data.get('text', '')
                yesterday_games = self._extract_games_from_text(yesterday_text)
                
            # 找出新增游戏
            added_games = today_games - yesterday_games
            for game in added_games:
                new_games.append({
                    'site_name': site_name,
                    'game': game,
                    'type': 'new_game',
                    'description': f'{site_name} 新增游戏: {game}'
                })
                
        return new_games
        
    def _extract_game_from_page(self, page: Dict[str, Any]) -> str:
        """从页面信息中提取游戏名"""
        # 从snapshot_path或description中提取
        desc = page.get('description', '')
        if '充值页' in desc:
            return desc.replace('充值页', '').strip()
        return ''
        
    def _extract_games_from_text(self, text: str) -> set:
        """从文本中提取游戏列表"""
        games = set()
        game_keywords = {
            '原神': ['原神', 'Genshin Impact'],
            'PUBG': ['PUBG', 'PUBG Mobile'],
            '崩坏星穹铁道': ['崩坏星穹铁道', 'Honkai Star Rail'],
            '绝区零': ['绝区零', 'Zenless Zone Zero'],
            '鸣潮': ['鸣潮', 'Wuthering Waves']
        }
        
        text_lower = text.lower()
        for game_name, keywords in game_keywords.items():
            for keyword in keywords:
                if keyword.lower() in text_lower:
                    games.add(game_name)
                    break
                    
        return games
        
    def analyze_all_changes(self, crawl_results: List[Dict[str, Any]], 
                           today_str: str) -> List[Dict[str, Any]]:
        """
        分析所有站点的变化
        
        Args:
            crawl_results: 今日抓取结果
            today_str: 今日日期字符串
            
        Returns:
            所有变化列表
        """
        all_changes = []
        
        for site_result in crawl_results:
            site_name = site_result['site_name']
            
            for page in site_result.get('pages', []):
                if not page.get('success'):
                    continue
                    
                page_type = page['type']
                
                # 分析变化
                change = self.analyze_page_changes(site_name, page_type, today_str)
                if change and change.get('has_changes'):
                    all_changes.append(change)
                    
        return all_changes
