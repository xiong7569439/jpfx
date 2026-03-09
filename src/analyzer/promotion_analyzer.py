"""
促销策略分析模块
识别促销类型、计算实际折扣率、追踪促销持续时间
"""

import os
import json
import logging
import re
import statistics
from typing import Dict, Any, List, Optional, Tuple
from collections import defaultdict

logger = logging.getLogger(__name__)


class PromotionAnalyzer:
    """促销策略分析器"""
    
    # 促销类型定义
    PROMOTION_TYPES = {
        'first_order': {
            'name': '首单优惠',
            'keywords': ['first order', 'first purchase', 'new user', '首单', '新用户', '首次'],
            'priority': 1
        },
        'percentage_discount': {
            'name': '百分比折扣',
            'keywords': ['% off', 'percent off', 'discount', '打折', '折'],
            'priority': 1
        },
        'fixed_amount': {
            'name': '固定金额减免',
            'keywords': ['$ off', 'usd off', '减', '立减'],
            'priority': 2
        },
        'bundle': {
            'name': '捆绑销售',
            'keywords': ['bundle', 'combo', 'package', '套餐', '组合', '捆绑'],
            'priority': 2
        },
        'flash_sale': {
            'name': '限时抢购',
            'keywords': ['flash sale', 'limited time', 'countdown', '限时', '秒杀', '抢购'],
            'priority': 1
        },
        'buy_x_get_y': {
            'name': '买赠活动',
            'keywords': ['buy .* get', 'bogo', '买.*送', '赠'],
            'priority': 2
        },
        'coupon': {
            'name': '优惠券',
            'keywords': ['coupon', 'promo code', 'code', '优惠码', '优惠券', '折扣码'],
            'priority': 1
        },
        'cashback': {
            'name': '返现/返利',
            'keywords': ['cashback', 'cash back', 'rebate', '返现', '返利', '返还'],
            'priority': 3
        },
        'loyalty': {
            'name': '会员/忠诚计划',
            'keywords': ['vip', 'member', 'loyalty', '会员', '积分'],
            'priority': 3
        }
    }
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.paths_config = config.get('paths', {})
        
    def analyze(self, parsed_data: Dict[str, Any], date_str: str) -> Dict[str, Any]:
        """
        分析促销策略
        
        Args:
            parsed_data: 解析后的数据
            date_str: 日期字符串
            
        Returns:
            促销分析结果
        """
        results = {
            'date': date_str,
            'promotions_by_site': {},
            'promotions_by_game': {},
            'promotion_summary': {},
            'competitive_insights': []
        }
        
        # 分析每个站点的促销
        for site_name, pages in parsed_data.items():
            site_promotions = []
            
            for page_key, data in pages.items():
                if not page_key.startswith('product'):
                    continue
                    
                game = data.get('game', '')
                promotions = data.get('promotions', [])
                discounts = data.get('discounts', [])
                prices = data.get('prices', [])
                
                # 解析促销信息
                parsed_promos = self._parse_promotions(
                    promotions, discounts, prices, game, site_name
                )
                
                if parsed_promos:
                    site_promotions.extend(parsed_promos)
                    
                    # 按游戏分组
                    if game:
                        if game not in results['promotions_by_game']:
                            results['promotions_by_game'][game] = []
                        results['promotions_by_game'][game].extend(parsed_promos)
                        
            if site_promotions:
                results['promotions_by_site'][site_name] = site_promotions
                
        # 生成促销汇总
        results['promotion_summary'] = self._generate_summary(results)
        
        # 生成竞争洞察
        results['competitive_insights'] = self._generate_insights(results)
        
        return results
        
    def _parse_promotions(self, promotions: List[Dict], 
                         discounts: List[Dict],
                         prices: List[Dict],
                         game: str, 
                         site: str) -> List[Dict[str, Any]]:
        """解析促销信息"""
        parsed = []
        
        # 分析促销码/优惠券
        for promo in promotions:
            promo_type = self._identify_promotion_type(promo.get('raw', ''))
            
            parsed_promo = {
                'game': game,
                'site': site,
                'type': promo_type['type'],
                'type_name': promo_type['name'],
                'raw_text': promo.get('raw', ''),
                'code': promo.get('code', ''),
                'discount_value': None,
                'discount_type': None,
                'actual_discount_pct': None,
                'estimated_savings': None
            }
            
            # 计算折扣率
            discount_calc = self._calculate_discount(
                promo.get('raw', ''), prices
            )
            parsed_promo.update(discount_calc)
            
            parsed.append(parsed_promo)
            
        # 分析折扣信息
        for discount in discounts:
            discount_text = discount.get('raw', '')
            promo_type = self._identify_promotion_type(discount_text)
            
            parsed_discount = {
                'game': game,
                'site': site,
                'type': promo_type['type'],
                'type_name': promo_type['name'],
                'raw_text': discount_text,
                'code': '',
                'discount_value': discount.get('percentage', ''),
                'discount_type': 'percentage',
                'actual_discount_pct': None,
                'estimated_savings': None
            }
            
            # 尝试提取百分比
            pct_match = re.search(r'(\d+)%', discount_text)
            if pct_match:
                parsed_discount['actual_discount_pct'] = int(pct_match.group(1))
                
            parsed.append(parsed_discount)
            
        return parsed
        
    def _identify_promotion_type(self, text: str) -> Dict[str, str]:
        """识别促销类型"""
        text_lower = text.lower()
        
        for type_key, type_info in self.PROMOTION_TYPES.items():
            for keyword in type_info['keywords']:
                if re.search(keyword, text_lower, re.IGNORECASE):
                    return {
                        'type': type_key,
                        'name': type_info['name']
                    }
                    
        return {
            'type': 'other',
            'name': '其他促销'
        }
        
    def _calculate_discount(self, promo_text: str, 
                           prices: List[Dict]) -> Dict[str, Any]:
        """计算实际折扣"""
        result = {
            'discount_value': None,
            'discount_type': None,
            'actual_discount_pct': None,
            'estimated_savings': None
        }
        
        if not prices:
            return result
            
        # 获取基准价格
        base_price = None
        for price in prices:
            value = price.get('value')
            if value and float(value) > 0:
                base_price = float(value)
                break
                
        if not base_price:
            return result
            
        promo_lower = promo_text.lower()
        
        # 百分比折扣
        pct_match = re.search(r'(\d+)%\s*(?:off|discount)', promo_lower)
        if pct_match:
            pct = int(pct_match.group(1))
            result['discount_value'] = pct
            result['discount_type'] = 'percentage'
            result['actual_discount_pct'] = pct
            result['estimated_savings'] = round(base_price * pct / 100, 2)
            return result
            
        # 固定金额减免
        amount_match = re.search(r'\$?(\d+(?:\.\d{2})?)\s*(?:off|discount)', promo_lower)
        if amount_match:
            amount = float(amount_match.group(1))
            result['discount_value'] = amount
            result['discount_type'] = 'fixed_amount'
            if base_price > 0:
                result['actual_discount_pct'] = round((amount / base_price) * 100, 1)
            result['estimated_savings'] = amount
            return result
            
        # 买X送Y - 估算折扣
        bog_match = re.search(r'buy (\d+) get (\d+)', promo_lower)
        if bog_match:
            buy_qty = int(bog_match.group(1))
            get_qty = int(bog_match.group(2))
            total_qty = buy_qty + get_qty
            if total_qty > 0:
                discount_pct = round((get_qty / total_qty) * 100, 1)
                result['discount_type'] = 'buy_x_get_y'
                result['actual_discount_pct'] = discount_pct
                result['estimated_savings'] = round(base_price * get_qty, 2)
            return result
            
        return result
        
    def _generate_summary(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """生成促销汇总"""
        summary = {
            'total_promotions': 0,
            'promotions_by_type': defaultdict(int),
            'sites_with_promotions': [],
            'average_discount': 0,
            'biggest_discount': None,
            'most_active_site': None
        }
        
        all_discounts = []
        site_promo_counts = defaultdict(int)
        
        for site_name, promotions in results['promotions_by_site'].items():
            summary['sites_with_promotions'].append(site_name)
            site_promo_counts[site_name] = len(promotions)
            summary['total_promotions'] += len(promotions)
            
            for promo in promotions:
                promo_type = promo.get('type', 'other')
                summary['promotions_by_type'][promo_type] += 1
                
                discount_pct = promo.get('actual_discount_pct')
                if discount_pct and discount_pct > 0:
                    all_discounts.append(discount_pct)
                    
                # 追踪最大折扣
                current_biggest = 0
                if summary['biggest_discount']:
                    current_biggest = summary['biggest_discount'].get('actual_discount_pct') or 0
                
                if not summary['biggest_discount'] or \
                   (discount_pct and discount_pct > 0 and discount_pct > current_biggest):
                    summary['biggest_discount'] = promo
                    
        # 计算平均折扣
        if all_discounts:
            summary['average_discount'] = round(statistics.mean(all_discounts), 1)
            
        # 找出最活跃的站点
        if site_promo_counts:
            summary['most_active_site'] = max(site_promo_counts.items(), key=lambda x: x[1])
            
        summary['promotions_by_type'] = dict(summary['promotions_by_type'])
        
        return summary
        
    def _generate_insights(self, results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """生成竞争洞察"""
        insights = []
        
        # 按游戏对比促销力度
        for game, promotions in results['promotions_by_game'].items():
            if len(promotions) < 2:
                continue
                
            # 找出各站点的最大折扣
            site_max_discounts = {}
            for promo in promotions:
                site = promo.get('site', '')
                discount = promo.get('actual_discount_pct', 0) or 0
                
                if site not in site_max_discounts or discount > site_max_discounts[site]:
                    site_max_discounts[site] = discount
                    
            if len(site_max_discounts) >= 2:
                sorted_sites = sorted(site_max_discounts.items(), key=lambda x: x[1], reverse=True)
                best_site = sorted_sites[0]
                
                insights.append({
                    'type': 'competitive_promotion',
                    'game': game,
                    'description': f"{game}: {best_site[0]} 促销力度最大 ({best_site[1]}%)",
                    'best_site': best_site[0],
                    'best_discount': best_site[1],
                    'all_discounts': site_max_discounts
                })
                
        # 识别促销类型差异
        promo_types_by_site = defaultdict(set)
        for site_name, promotions in results['promotions_by_site'].items():
            for promo in promotions:
                promo_types_by_site[site_name].add(promo.get('type', ''))
                
        # 找出独特的促销策略
        all_types = set()
        for types in promo_types_by_site.values():
            all_types.update(types)
            
        for site_name, types in promo_types_by_site.items():
            unique_types = types - set().union(*[t for s, t in promo_types_by_site.items() if s != site_name])
            if unique_types:
                type_names = [self.PROMOTION_TYPES.get(t, {}).get('name', t) for t in unique_types]
                insights.append({
                    'type': 'unique_strategy',
                    'site': site_name,
                    'description': f"{site_name} 独有促销类型: {', '.join(type_names)}",
                    'unique_types': list(unique_types)
                })
                
        return insights
        
    def export_to_csv(self, promotion_results: Dict[str, Any], 
                     output_path: str) -> str:
        """
        导出促销数据到CSV
        
        Args:
            promotion_results: 促销分析结果
            output_path: 输出文件路径
            
        Returns:
            输出文件路径
        """
        import csv
        
        with open(output_path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            
            # 写入表头
            writer.writerow([
                '站点', '游戏', '促销类型', '促销描述', '优惠码',
                '折扣值', '折扣类型', '实际折扣率(%)', '预估节省金额'
            ])
            
            # 写入数据
            for site_name, promotions in promotion_results.get('promotions_by_site', {}).items():
                for promo in promotions:
                    writer.writerow([
                        site_name,
                        promo.get('game', ''),
                        promo.get('type_name', ''),
                        promo.get('raw_text', ''),
                        promo.get('code', ''),
                        promo.get('discount_value', ''),
                        promo.get('discount_type', ''),
                        promo.get('actual_discount_pct', ''),
                        promo.get('estimated_savings', '')
                    ])
                    
        logger.info(f"促销数据已导出: {output_path}")
        return output_path
