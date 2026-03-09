"""
竞品间价格对比分析
对比同一游戏在不同竞品的定价差异
"""

import json
import logging
from typing import Dict, Any, List, Optional

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
            # 尝试多种方式匹配游戏数据
            game_data = None
            
            # 方式1: 使用 product_{game_name} 格式
            product_key = f"product_{game_name}"
            if product_key in pages:
                game_data = pages[product_key]
            
            # 方式2: 遍历所有页面查找匹配的游戏
            if not game_data:
                for page_key, data in pages.items():
                    if page_key.startswith('product') and data.get('game') == game_name:
                        game_data = data
                        break
            
            # 方式3: 检查普通 product key
            if not game_data and 'product' in pages:
                data = pages['product']
                if data.get('game') == game_name:
                    game_data = data
            
            # 提取价格
            if game_data:
                prices = game_data.get('prices', [])
                # 过滤掉无效价格（value为空或0）
                valid_prices = [p for p in prices if p.get('value') and float(p.get('value') or 0) > 0]
                if valid_prices:
                    # 取最低价格
                    min_price = min(valid_prices, key=lambda x: float(x.get('value', 0)))
                    site_prices[site_name] = min_price
                    logger.info(f"{site_name} - {game_name}: 找到价格 {min_price['raw']}")
                        
        # 如果只有一个站点有价格，无法对比
        if len(site_prices) < 2:
            logger.warning(f"{game_name}: 只有 {len(site_prices)} 个站点有价格数据，无法对比")
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
            logger.info(f"{game_name}: 价格对比完成，价差 {price_diff_pct:.1f}%")
            
        return comparisons
        
    def load_parsed_data(self, date_str: str) -> Dict[str, Any]:
        """加载解析后的数据"""
        import os
        parsed_base = self.config.get('paths', {}).get('parsed_base', './data/parsed')
        parsed_dir = os.path.join(parsed_base, date_str)
        
        data = {}
        
        if not os.path.exists(parsed_dir):
            logger.warning(f"解析数据目录不存在: {parsed_dir}")
            return data
            
        for site_name in os.listdir(parsed_dir):
            site_dir = os.path.join(parsed_dir, site_name)
            if not os.path.isdir(site_dir):
                continue
                
            data[site_name] = {}
            
            for filename in os.listdir(site_dir):
                if not filename.endswith('.json'):
                    continue
                    
                filepath = os.path.join(site_dir, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        page_data = json.load(f)
                        
                        # 从文件名推断页面类型和标识
                        # 文件名格式: {page_type}_{identifier}.json
                        file_base = filename.replace('.json', '')
                        parts = file_base.split('_', 1)
                        page_type = parts[0] if parts else 'unknown'
                        
                        # 对于产品页，使用游戏名称作为key以便匹配
                        if page_type == 'product':
                            game = page_data.get('game', '')
                            if game:
                                key = f"product_{game}"
                                # 如果已存在该游戏的数据，优先保留有价格数据的
                                if key in data[site_name]:
                                    existing_prices = data[site_name][key].get('prices', [])
                                    new_prices = page_data.get('prices', [])
                                    if len(new_prices) > len(existing_prices):
                                        data[site_name][key] = page_data
                                else:
                                    data[site_name][key] = page_data
                            else:
                                # 尝试从文件名推断游戏
                                game_from_file = self._extract_game_from_filename(filename)
                                if game_from_file:
                                    key = f"product_{game_from_file}"
                                    if key in data[site_name]:
                                        existing_prices = data[site_name][key].get('prices', [])
                                        new_prices = page_data.get('prices', [])
                                        if len(new_prices) > len(existing_prices):
                                            data[site_name][key] = page_data
                                    else:
                                        data[site_name][key] = page_data
                                else:
                                    data[site_name][page_type] = page_data
                        else:
                            data[site_name][page_type] = page_data
                            
                except Exception as e:
                    logger.error(f"加载解析数据失败: {filepath}, 错误: {e}")
                        
        return data
        
    def _extract_game_from_filename(self, filename: str) -> str:
        """从文件名推断游戏名称"""
        # 游戏关键词映射
        game_keywords = {
            'genshin': '原神',
            'genshin-impact': '原神',
            'genshinimpact': '原神',
            'pubg': 'PUBG',
            'pubg-mobile': 'PUBG',
            'honkai': '崩坏星穹铁道',
            'honkai-star-rail': '崩坏星穹铁道',
            'star-rail': '崩坏星穹铁道',
            'zenless': '绝区零',
            'zenless-zone-zero': '绝区零',
            'wuthering': '鸣潮',
            'wuthering-waves': '鸣潮',
            'mlbb': '无尽对决',
            'mobile-legends': '无尽对决',
            'honor-of-kings': '王者荣耀',
            'hok': '王者荣耀',
            'delta-force': '三角洲行动',
            'arena-breakout': '暗区突围',
        }
        
        filename_lower = filename.lower()
        for keyword, game_name in game_keywords.items():
            if keyword in filename_lower:
                return game_name
        return ''
