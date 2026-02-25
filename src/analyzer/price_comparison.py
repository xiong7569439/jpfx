"""
竞品间价格对比分析
对比同一游戏在不同竞品的定价差异
"""

import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class PriceComparisonAnalyzer:
    """价格对比分析器"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.target_games = config.get('target_games', [])
        
    def analyze(self, parsed_data: Dict[str, Any], date_str: str) -> List[Dict[str, Any]]:
        """
        分析竞品间价格对比
        
        Args:
            parsed_data: 各站点解析后的数据 {site_name: {page_type: data}}
            date_str: 日期字符串
            
        Returns:
            价格对比结果列表
        """
        comparisons = []
        
        # 按游戏分组对比
        for game in self.target_games:
            game_name = game['name']
            game_comparisons = self._compare_game_prices(game_name, parsed_data)
            if game_comparisons:
                comparisons.extend(game_comparisons)
                
        return comparisons
        
    def _compare_game_prices(self, game_name: str, 
                             parsed_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """对比单个游戏的价格"""
        comparisons = []
        
        # 收集各站点该游戏的价格
        site_prices = {}
        for site_name, pages in parsed_data.items():
            for page_type, data in pages.items():
                if page_type == 'product' and data.get('game') == game_name:
                    prices = data.get('prices', [])
                    if prices:
                        # 取最低价格
                        min_price = min(prices, key=lambda x: float(x.get('value', 0) or 0))
                        site_prices[site_name] = min_price
                        
        # 如果只有一个站点有价格，无法对比
        if len(site_prices) < 2:
            return comparisons
            
        # 找出最低价和最高价
        sorted_sites = sorted(site_prices.items(), 
                             key=lambda x: float(x[1].get('value', 0) or 0))
        
        cheapest_site = sorted_sites[0]
        most_expensive_site = sorted_sites[-1]
        
        # 计算价差
        cheapest_value = float(cheapest_site[1].get('value', 0))
        expensive_value = float(most_expensive_site[1].get('value', 0))
        
        if cheapest_value > 0:
            price_diff_pct = ((expensive_value - cheapest_value) / cheapest_value) * 100
            
            comparisons.append({
                'type': 'price_comparison',
                'game': game_name,
                'cheapest_site': cheapest_site[0],
                'cheapest_price': cheapest_site[1]['raw'],
                'most_expensive_site': most_expensive_site[0],
                'most_expensive_price': most_expensive_site[1]['raw'],
                'price_diff_pct': round(price_diff_pct, 2),
                'description': f"{game_name}: {cheapest_site[0]}({cheapest_site[1]['raw']}) 比 {most_expensive_site[0]}({most_expensive_site[1]['raw']}) 低 {price_diff_pct:.1f}%"
            })
            
        return comparisons
        
    def load_parsed_data(self, date_str: str) -> Dict[str, Any]:
        """加载解析后的数据"""
        import os
        parsed_base = self.config.get('paths', {}).get('parsed_base', './data/parsed')
        parsed_dir = os.path.join(parsed_base, date_str)
        
        data = {}
        
        if not os.path.exists(parsed_dir):
            return data
            
        for site_name in os.listdir(parsed_dir):
            site_dir = os.path.join(parsed_dir, site_name)
            if not os.path.isdir(site_dir):
                continue
                
            data[site_name] = {}
            
            for filename in os.listdir(site_dir):
                if filename.endswith('.json'):
                    filepath = os.path.join(site_dir, filename)
                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            page_data = json.load(f)
                            # 从文件名推断页面类型
                            page_type = filename.replace('.json', '').split('_')[0]
                            data[site_name][page_type] = page_data
                    except Exception as e:
                        logger.error(f"加载解析数据失败: {filepath}, 错误: {e}")
                        
        return data
