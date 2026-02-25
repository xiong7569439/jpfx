"""
变化分类器
将变化归类到A-H维度
"""

import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


class ChangeClassifier:
    """变化分类器"""
    
    # 维度定义
    DIMENSIONS = {
        'A': {
            'name': '定价策略',
            'keywords': ['price', 'pricing', 'cost', 'fee', 'discount', 'currency', 
                        '金额', '价格', '费用', '折扣', '币种', '手续费', '阶梯', '礼包'],
            'fields': ['price'],
            'priority': 1
        },
        'B': {
            'name': '促销策略',
            'keywords': ['promo', 'coupon', 'code', 'sale', 'deal', 'offer', 'bonus',
                        '优惠码', '首单', '复购', '节日', '活动', '倒计时', '满减', '买赠'],
            'fields': ['discount', 'promotion'],
            'priority': 1
        },
        'C': {
            'name': '产品策略',
            'keywords': ['game', 'product', 'country', 'region', 'server', 'stock',
                        '游戏', '国家', '区服', '面额', '补货', '缺货', '新增', '下线'],
            'fields': [],
            'priority': 1
        },
        'D': {
            'name': '支付策略',
            'keywords': ['payment', 'pay', 'card', 'paypal', 'alipay', 'risk',
                        '支付', '信用卡', '风控', '失败', '兜底'],
            'fields': ['payment'],
            'priority': 1
        },
        'E': {
            'name': '履约与信任',
            'keywords': ['delivery', 'refund', 'dispute', 'kyc', 'verification', 'support',
                        '到账', '时效', '退款', '争议', '实名', '合规', '客服'],
            'fields': ['delivery'],
            'priority': 1
        },
        'F': {
            'name': '增长渠道',
            'keywords': ['affiliate', 'referral', 'partner', 'reward', 'invite', 'review',
                        '联盟', '返利', '邀请', '奖励', '合作', '评论', '评分'],
            'fields': [],
            'priority': 2
        },
        'G': {
            'name': 'SEO/内容',
            'keywords': ['seo', 'title', 'description', 'meta', 'category', 'link',
                        '目录', '标题', '描述', '内链', '国家页'],
            'fields': [],
            'priority': 3
        },
        'H': {
            'name': '体验与转化',
            'keywords': ['cta', 'button', 'form', 'popup', 'modal', 'ab test',
                        '转化', '按钮', '表单', '弹窗', '引导'],
            'fields': [],
            'priority': 2
        }
    }
    
    def __init__(self):
        pass
        
    def classify(self, change: Dict[str, Any]) -> List[str]:
        """
        对变化进行分类
        
        Args:
            change: 变化数据
            
        Returns:
            维度代码列表（可能有多个）
        """
        dimensions = []
        
        # 1. 根据字段类型判断
        field = change.get('field', '')
        for code, dim in self.DIMENSIONS.items():
            if field in dim.get('fields', []):
                dimensions.append(code)
                
        # 2. 根据描述内容关键词判断
        description = change.get('description', '').lower()
        for code, dim in self.DIMENSIONS.items():
            for keyword in dim.get('keywords', []):
                if keyword.lower() in description:
                    if code not in dimensions:
                        dimensions.append(code)
                    break
                    
        # 3. 根据变化类型辅助判断
        if not dimensions:
            # 标题变化 -> SEO/内容
            if change.get('title_changed'):
                dimensions.append('G')
                
        # 默认分类
        if not dimensions:
            dimensions.append('H')  # 体验与转化作为默认
            
        return dimensions
        
    def get_impact_level(self, dimensions: List[str]) -> str:
        """
        根据维度判断影响级别
        
        Returns:
            high/medium/low
        """
        # 高优先级维度
        high_dims = ['A', 'B', 'C', 'D', 'E']
        # 中优先级维度
        medium_dims = ['F', 'H']
        
        for d in dimensions:
            if d in high_dims:
                return 'high'
                
        for d in dimensions:
            if d in medium_dims:
                return 'medium'
                
        return 'low'
        
    def classify_changes(self, changes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        批量分类变化
        
        Args:
            changes: 变化列表
            
        Returns:
            带分类信息的变化列表
        """
        classified = []
        
        for change in changes:
            dimensions = self.classify(change)
            impact = self.get_impact_level(dimensions)
            
            change_with_class = {
                **change,
                'dimensions': dimensions,
                'dimension_names': [self.DIMENSIONS[d]['name'] for d in dimensions],
                'impact_level': impact,
                'priority': min(self.DIMENSIONS[d]['priority'] for d in dimensions)
            }
            
            classified.append(change_with_class)
            
        # 按优先级排序
        classified.sort(key=lambda x: (x['priority'], x.get('site_name', '')))
        
        return classified
        
    def generate_tldr(self, classified_changes: List[Dict[str, Any]], 
                      max_items: int = 6) -> List[Dict[str, Any]]:
        """
        生成TL;DR（要点摘要）
        
        Args:
            classified_changes: 已分类的变化列表
            max_items: 最大条目数
            
        Returns:
            TL;DR列表
        """
        tldr = []
        
        # 按影响级别分组
        high_impact = [c for c in classified_changes if c['impact_level'] == 'high']
        medium_impact = [c for c in classified_changes if c['impact_level'] == 'medium']
        low_impact = [c for c in classified_changes if c['impact_level'] == 'low']
        
        # 优先取高影响
        for change in high_impact[:max_items]:
            tldr.append({
                'level': '高',
                'site': change.get('site_name', ''),
                'description': change.get('description', '')[:100],
                'dimensions': change.get('dimension_names', [])
            })
            
        # 补充中影响
        if len(tldr) < max_items:
            for change in medium_impact[:max_items - len(tldr)]:
                tldr.append({
                    'level': '中',
                    'site': change.get('site_name', ''),
                    'description': change.get('description', '')[:100],
                    'dimensions': change.get('dimension_names', [])
                })
                
        # 补充低影响
        if len(tldr) < max_items:
            for change in low_impact[:max_items - len(tldr)]:
                tldr.append({
                    'level': '低',
                    'site': change.get('site_name', ''),
                    'description': change.get('description', '')[:100],
                    'dimensions': change.get('dimension_names', [])
                })
                
        return tldr
