"""
价格趋势分析模块
分析历史价格走势，计算竞争力评分，识别异常波动
"""

import os
import json
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict
import statistics

logger = logging.getLogger(__name__)


class PriceTrendAnalyzer:
    """价格趋势分析器"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.target_games = config.get('target_games', [])
        self.paths_config = config.get('paths', {})
        
    def analyze_trends(self, date_str: str, days: int = 7) -> Dict[str, Any]:
        """
        分析价格趋势
        
        Args:
            date_str: 当前日期字符串
            days: 分析天数（默认7天）
            
        Returns:
            价格趋势分析结果
        """
        results = {
            'date': date_str,
            'analysis_days': days,
            'game_trends': {},
            'competitiveness': {},
            'anomalies': []
        }
        
        # 加载历史价格数据
        historical_data = self._load_historical_prices(date_str, days)
        
        for game in self.target_games:
            game_name = game['name']
            trend = self._analyze_game_trend(game_name, historical_data, days)
            if trend:
                results['game_trends'][game_name] = trend
                
                # 计算竞争力评分
                competitiveness = self._calculate_competitiveness(game_name, trend)
                if competitiveness:
                    results['competitiveness'][game_name] = competitiveness
                    
                # 检测异常波动
                anomalies = self._detect_anomalies(trend)
                if anomalies:
                    results['anomalies'].extend(anomalies)
                    
        return results
        
    def _load_historical_prices(self, end_date_str: str, days: int) -> Dict[str, Dict[str, Any]]:
        """加载历史价格数据"""
        historical_data = defaultdict(lambda: defaultdict(dict))
        
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
        
        for i in range(days):
            current_date = end_date - timedelta(days=i)
            date_str = current_date.strftime('%Y-%m-%d')
            
            # 加载该日期的解析数据
            parsed_data = self._load_parsed_data(date_str)
            
            for site_name, pages in parsed_data.items():
                for page_key, data in pages.items():
                    game = data.get('game', '')
                    if not game:
                        continue
                        
                    prices = data.get('prices', [])
                    if prices:
                        # 过滤有效价格并取最低价格
                        valid_prices = []
                        for p in prices:
                            val = p.get('value', '')
                            if val and str(val).replace('.', '').replace(',', '').isdigit():
                                try:
                                    valid_prices.append((float(str(val).replace(',', '')), p))
                                except:
                                    pass
                        
                        if valid_prices:
                            min_price_val, min_price = min(valid_prices, key=lambda x: x[0])
                            historical_data[game][site_name][date_str] = {
                                'price': min_price_val,
                                'raw': min_price.get('raw', ''),
                                'currency': min_price.get('currency', 'USD')
                            }
                        
        return dict(historical_data)
        
    def _load_parsed_data(self, date_str: str) -> Dict[str, Any]:
        """加载解析后的数据"""
        parsed_base = self.paths_config.get('parsed_base', './data/parsed')
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
                if not filename.endswith('.json'):
                    continue
                    
                filepath = os.path.join(site_dir, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        page_data = json.load(f)
                        
                    file_base = filename.replace('.json', '')
                    parts = file_base.split('_', 1)
                    page_type = parts[0] if parts else 'unknown'
                    
                    if page_type == 'product':
                        game = page_data.get('game', '')
                        if game:
                            key = f"product_{game}"
                            data[site_name][key] = page_data
                        else:
                            data[site_name][page_type] = page_data
                    else:
                        data[site_name][page_type] = page_data
                        
                except Exception as e:
                    logger.error(f"加载解析数据失败: {filepath}, 错误: {e}")
                    
        return data
        
    def _analyze_game_trend(self, game_name: str, 
                           historical_data: Dict[str, Any], 
                           days: int) -> Optional[Dict[str, Any]]:
        """分析单个游戏的价格趋势"""
        if game_name not in historical_data:
            return None
            
        game_data = historical_data[game_name]
        
        trend = {
            'game': game_name,
            'site_trends': {},
            'price_range': {},
            'volatility': {}
        }
        
        for site_name, date_prices in game_data.items():
            if not date_prices:
                continue
                
            # 提取价格序列
            dates = sorted(date_prices.keys())
            prices = [date_prices[d]['price'] for d in dates if date_prices[d]['price'] > 0]
            
            if len(prices) < 2:
                continue
                
            # 计算趋势指标
            trend_analysis = self._calculate_trend_metrics(dates, date_prices)
            trend['site_trends'][site_name] = trend_analysis
            
        # 计算整体价格区间
        all_prices = []
        for site_data in trend['site_trends'].values():
            if 'prices' in site_data:
                all_prices.extend([p for p in site_data['prices'] if p > 0])
                
        if all_prices:
            trend['price_range'] = {
                'min': min(all_prices),
                'max': max(all_prices),
                'avg': statistics.mean(all_prices),
                'median': statistics.median(all_prices)
            }
            
        return trend
        
    def _calculate_trend_metrics(self, dates: List[str], 
                                date_prices: Dict[str, Any]) -> Dict[str, Any]:
        """计算趋势指标"""
        prices = [date_prices[d]['price'] for d in dates if date_prices[d]['price'] > 0]
        
        if not prices:
            return {}
            
        metrics = {
            'dates': dates,
            'prices': prices,
            'latest_price': prices[-1],
            'latest_date': dates[-1],
            'price_change': 0,
            'price_change_pct': 0,
            'trend_direction': 'stable',
            'volatility': 0
        }
        
        if len(prices) >= 2:
            # 价格变化
            first_price = prices[0]
            latest_price = prices[-1]
            
            if first_price > 0:
                metrics['price_change'] = latest_price - first_price
                metrics['price_change_pct'] = round(
                    ((latest_price - first_price) / first_price) * 100, 2
                )
                
            # 趋势方向
            if metrics['price_change_pct'] > 5:
                metrics['trend_direction'] = 'up'
            elif metrics['price_change_pct'] < -5:
                metrics['trend_direction'] = 'down'
            else:
                metrics['trend_direction'] = 'stable'
                
            # 波动率（标准差/平均值）
            if len(prices) >= 3:
                try:
                    std = statistics.stdev(prices)
                    avg = statistics.mean(prices)
                    if avg > 0:
                        metrics['volatility'] = round((std / avg) * 100, 2)
                except:
                    pass
                    
        return metrics
        
    def _calculate_competitiveness(self, game_name: str, 
                                   trend: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """计算价格竞争力评分"""
        site_trends = trend.get('site_trends', {})
        
        if len(site_trends) < 2:
            return None
            
        # 获取各站点最新价格
        latest_prices = {}
        for site_name, site_data in site_trends.items():
            if 'latest_price' in site_data and site_data['latest_price'] > 0:
                latest_prices[site_name] = site_data['latest_price']
                
        if len(latest_prices) < 2:
            return None
            
        # 排序价格
        sorted_prices = sorted(latest_prices.items(), key=lambda x: x[1])
        
        competitiveness = {
            'game': game_name,
            'rankings': [],
            'topuplive_position': None,
            'price_gap_to_cheapest': 0,
            'price_gap_to_most_expensive': 0,
            'competitiveness_score': 0  # 0-100，越高越有竞争力
        }
        
        # 计算排名
        for rank, (site_name, price) in enumerate(sorted_prices, 1):
            competitiveness['rankings'].append({
                'rank': rank,
                'site': site_name,
                'price': price
            })
            
            if site_name == 'TOPUPlive':
                competitiveness['topuplive_position'] = rank
                
        # 计算TOPUPlive的竞争力
        if 'TOPUPlive' in latest_prices:
            topuplive_price = latest_prices['TOPUPlive']
            cheapest_price = sorted_prices[0][1]
            most_expensive_price = sorted_prices[-1][1]
            
            competitiveness['price_gap_to_cheapest'] = round(
                topuplive_price - cheapest_price, 2
            )
            competitiveness['price_gap_to_most_expensive'] = round(
                most_expensive_price - topuplive_price, 2
            )
            
            # 竞争力评分：基于排名和价格差距
            total_sites = len(sorted_prices)
            if total_sites > 1:
                rank_score = ((total_sites - competitiveness['topuplive_position']) / 
                             (total_sites - 1)) * 100
                
                # 如果是最低价，额外加分
                if competitiveness['topuplive_position'] == 1:
                    rank_score = 100
                    
                competitiveness['competitiveness_score'] = round(rank_score, 1)
                
        return competitiveness
        
    def _detect_anomalies(self, trend: Dict[str, Any]) -> List[Dict[str, Any]]:
        """检测异常价格波动"""
        anomalies = []
        site_trends = trend.get('site_trends', {})
        game_name = trend.get('game', '')
        
        for site_name, site_data in site_trends.items():
            prices = site_data.get('prices', [])
            dates = site_data.get('dates', [])
            
            if len(prices) < 3:
                continue
                
            # 计算平均价格和标准差
            avg_price = statistics.mean(prices)
            
            try:
                std_price = statistics.stdev(prices)
            except:
                continue
                
            # 检测异常点（超过2个标准差）
            for i, (date, price) in enumerate(zip(dates, prices)):
                if std_price > 0:
                    z_score = abs(price - avg_price) / std_price
                    
                    if z_score > 2:  # 超过2个标准差视为异常
                        # 判断是上涨还是下跌
                        change_type = 'spike' if price > avg_price else 'drop'
                        
                        anomalies.append({
                            'game': game_name,
                            'site': site_name,
                            'date': date,
                            'price': price,
                            'avg_price': round(avg_price, 2),
                            'deviation_pct': round(((price - avg_price) / avg_price) * 100, 1),
                            'type': change_type,
                            'severity': 'high' if z_score > 3 else 'medium'
                        })
                        
        return anomalies
        
    def export_to_csv(self, trend_results: Dict[str, Any], 
                     output_path: str) -> str:
        """
        导出价格趋势数据到CSV（便于Excel分析）
        
        Args:
            trend_results: 趋势分析结果
            output_path: 输出文件路径
            
        Returns:
            输出文件路径
        """
        import csv
        
        with open(output_path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            
            # 写入表头
            writer.writerow([
                '游戏', '站点', '日期', '价格', '价格变化率(%)', 
                '趋势方向', '波动率(%)', '竞争力排名', '竞争力评分'
            ])
            
            # 写入数据
            for game_name, trend in trend_results.get('game_trends', {}).items():
                competitiveness = trend_results.get('competitiveness', {}).get(game_name, {})
                rankings = {r['site']: r['rank'] for r in competitiveness.get('rankings', [])}
                score = competitiveness.get('competitiveness_score', 0)
                
                for site_name, site_data in trend.get('site_trends', {}).items():
                    dates = site_data.get('dates', [])
                    prices = site_data.get('prices', [])
                    change_pct = site_data.get('price_change_pct', 0)
                    direction = site_data.get('trend_direction', 'stable')
                    volatility = site_data.get('volatility', 0)
                    rank = rankings.get(site_name, '-')
                    
                    for date, price in zip(dates, prices):
                        writer.writerow([
                            game_name, site_name, date, price,
                            change_pct if date == dates[-1] else '',
                            direction if date == dates[-1] else '',
                            volatility if date == dates[-1] else '',
                            rank if date == dates[-1] else '',
                            score if date == dates[-1] and site_name == 'TOPUPlive' else ''
                        ])
                        
        logger.info(f"价格趋势数据已导出: {output_path}")
        return output_path
