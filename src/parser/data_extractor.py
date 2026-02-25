"""
结构化数据提取器
从页面内容中提取价格、支付、时效等关键信息
"""

import re
import json
import logging
from typing import Dict, Any, List, Optional
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class DataExtractor:
    """数据提取器"""
    
    # 价格相关正则
    PRICE_PATTERNS = [
        r'\$\s*[\d,]+\.?\d*',  # $99.99
        r'€\s*[\d,]+\.?\d*',  # €99.99
        r'£\s*[\d,]+\.?\d*',  # £99.99
        r'¥\s*[\d,]+',         # ¥999
        r'[\d,]+\.?\d*\s*USD', # 99.99 USD
        r'[\d,]+\.?\d*\s*EUR', # 99.99 EUR
        r'[\d,]+\.?\d*\s*GBP', # 99.99 GBP
    ]
    
    # 折扣相关正则
    DISCOUNT_PATTERNS = [
        r'(\d+)%\s*off',
        r'save\s*(\d+)%',
        r'discount\s*(\d+)%',
        r'(\d+)%\s*discount',
        r'-(\d+)%',
    ]
    
    # 时效相关正则
    DELIVERY_PATTERNS = [
        r'within\s+(\d+)\s*minutes?',
        r'within\s+(\d+)\s*hours?',
        r'instant',
        r'immediately',
        r'\d+-\d+\s*minutes?',
        r'\d+-\d+\s*hours?',
    ]
    
    # 库存状态关键词
    STOCK_KEYWORDS = [
        'in stock', 'available', 'out of stock', 'sold out', 'unavailable',
        'temporarily unavailable', 'coming soon', 'notify me', 'back in stock',
        '有货', '缺货', '售罄', '补货', '到货通知'
    ]
    
    # 评价评分相关正则
    RATING_PATTERNS = [
        r'(\d+\.?\d*)\s*stars?',  # 4.5 stars
        r'rating[:\s]*(\d+\.?\d*)',  # rating: 4.5
        r'(\d+\.?\d*)\s*out of\s*5',  # 4.5 out of 5
        r'★+',  # 星级符号
    ]
    
    REVIEW_COUNT_PATTERNS = [
        r'(\d+[\d,]*)\s*reviews?',  # 1,234 reviews
        r'(\d+[\d,]*)\s*ratings?',  # 1,234 ratings
    ]
    
    # 支付方式关键词
    PAYMENT_KEYWORDS = [
        'credit card', 'visa', 'mastercard', 'amex', 'american express',
        'paypal', 'alipay', 'wechat', 'wechat pay', 'unionpay',
        'bank transfer', 'wire transfer', 'local payment',
        'crypto', 'bitcoin', 'ethereum', 'usdt',
        'paysafecard', 'sofort', 'ideal', 'giropay',
    ]
    
    def __init__(self):
        pass
        
    def extract(self, html: str, text: str, url: str) -> Dict[str, Any]:
        """
        提取页面结构化数据
        
        Args:
            html: 页面HTML
            text: 页面纯文本
            url: 页面URL
            
        Returns:
            结构化数据字典
        """
        soup = BeautifulSoup(html, 'lxml')
        
        data = {
            'url': url,
            'prices': self._extract_prices(text),
            'discounts': self._extract_discounts(text),
            'payments': self._extract_payments(text),
            'delivery_time': self._extract_delivery_time(text),
            'promotions': self._extract_promotions(text),
            'games': self._extract_games(text),
            'countries': self._extract_countries(text),
            'stock_status': self._extract_stock_status(text),
            'rating': self._extract_rating(text),
            'review_count': self._extract_review_count(text),
        }
        
        return data
        
    def _extract_prices(self, text: str) -> List[Dict[str, str]]:
        """提取价格信息"""
        prices = []
        
        for pattern in self.PRICE_PATTERNS:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                price_str = match.group(0)
                # 提取数值
                numeric = re.findall(r'[\d,]+\.?\d*', price_str)
                if numeric:
                    prices.append({
                        'raw': price_str,
                        'value': numeric[0].replace(',', ''),
                        'currency': self._detect_currency(price_str)
                    })
                    
        # 去重
        seen = set()
        unique_prices = []
        for p in prices:
            key = f"{p['value']}_{p['currency']}"
            if key not in seen:
                seen.add(key)
                unique_prices.append(p)
                
        return unique_prices
        
    def _detect_currency(self, price_str: str) -> str:
        """检测货币类型"""
        price_str = price_str.upper()
        if '$' in price_str or 'USD' in price_str:
            return 'USD'
        elif '€' in price_str or 'EUR' in price_str:
            return 'EUR'
        elif '£' in price_str or 'GBP' in price_str:
            return 'GBP'
        elif '¥' in price_str:
            return 'JPY/CNY'
        return 'UNKNOWN'
        
    def _extract_discounts(self, text: str) -> List[Dict[str, str]]:
        """提取折扣信息"""
        discounts = []
        text_lower = text.lower()
        
        for pattern in self.DISCOUNT_PATTERNS:
            matches = re.finditer(pattern, text_lower)
            for match in matches:
                discount_pct = match.group(1) if match.groups() else ''
                discounts.append({
                    'raw': match.group(0),
                    'percentage': discount_pct,
                    'context': self._get_context(text_lower, match.start(), 50)
                })
                
        return discounts
        
    def _extract_payments(self, text: str) -> List[str]:
        """提取支付方式"""
        payments = []
        text_lower = text.lower()
        
        for keyword in self.PAYMENT_KEYWORDS:
            if keyword in text_lower:
                payments.append(keyword)
                
        return list(set(payments))
        
    def _extract_delivery_time(self, text: str) -> List[Dict[str, str]]:
        """提取到账时效"""
        delivery = []
        text_lower = text.lower()
        
        for pattern in self.DELIVERY_PATTERNS:
            matches = re.finditer(pattern, text_lower)
            for match in matches:
                delivery.append({
                    'raw': match.group(0),
                    'context': self._get_context(text_lower, match.start(), 50)
                })
                
        return delivery
        
    def _extract_promotions(self, text: str) -> List[Dict[str, str]]:
        """提取促销信息"""
        promotions = []
        text_lower = text.lower()
        
        # 优惠码
        promo_patterns = [
            r'promo\s*code[:\s]*(\w+)',
            r'coupon[:\s]*(\w+)',
            r'discount\s*code[:\s]*(\w+)',
            r'code[:\s]*(\w+)',
        ]
        
        for pattern in promo_patterns:
            matches = re.finditer(pattern, text_lower)
            for match in matches:
                promotions.append({
                    'type': 'promo_code',
                    'code': match.group(1) if match.groups() else '',
                    'raw': match.group(0)
                })
                
        # 限时活动
        if any(word in text_lower for word in ['limited time', 'flash sale', 'hot deal', 'special offer']):
            promotions.append({
                'type': 'limited_time',
                'description': '限时活动'
            })
            
        return promotions
        
    def _extract_games(self, text: str) -> List[str]:
        """提取游戏名称"""
        games = []
        text_lower = text.lower()
        
        game_keywords = {
            'genshin impact': '原神',
            'pubg': 'PUBG',
            'honkai star rail': '崩坏星穹铁道',
            'zenless zone zero': '绝区零',
            'wuthering waves': '鸣潮',
        }
        
        for keyword, name in game_keywords.items():
            if keyword in text_lower:
                games.append(name)
                
        return games
        
    def _extract_countries(self, text: str) -> List[str]:
        """提取国家/地区信息"""
        countries = []
        text_lower = text.lower()
        
        country_keywords = {
            'united states': '美国',
            'usa': '美国',
            'united kingdom': '英国',
            'uk': '英国',
            'germany': '德国',
            'france': '法国',
            'japan': '日本',
            'korea': '韩国',
            'singapore': '新加坡',
            'malaysia': '马来西亚',
            'australia': '澳大利亚',
            'canada': '加拿大',
        }
        
        for keyword, name in country_keywords.items():
            if keyword in text_lower:
                countries.append(name)
                
        return list(set(countries))
        
    def _extract_stock_status(self, text: str) -> Dict[str, Any]:
        """提取库存状态"""
        text_lower = text.lower()
        status = {
            'in_stock': False,
            'out_of_stock': False,
            'coming_soon': False,
            'notify_available': False,
            'keywords_found': []
        }
        
        # 检查库存状态
        if any(k in text_lower for k in ['in stock', 'available', '有货']):
            status['in_stock'] = True
            status['keywords_found'].append('in_stock')
        if any(k in text_lower for k in ['out of stock', 'sold out', 'unavailable', '缺货', '售罄']):
            status['out_of_stock'] = True
            status['keywords_found'].append('out_of_stock')
        if any(k in text_lower for k in ['coming soon', '即将上线']):
            status['coming_soon'] = True
            status['keywords_found'].append('coming_soon')
        if any(k in text_lower for k in ['notify me', '到货通知']):
            status['notify_available'] = True
            status['keywords_found'].append('notify_available')
            
        return status
        
    def _extract_rating(self, text: str) -> Optional[float]:
        """提取评分"""
        text_lower = text.lower()
        
        for pattern in self.RATING_PATTERNS:
            matches = re.finditer(pattern, text_lower)
            for match in matches:
                if '★' in match.group(0):
                    # 星级符号计数
                    return float(match.group(0).count('★'))
                elif match.groups():
                    try:
                        return float(match.group(1))
                    except ValueError:
                        continue
        return None
        
    def _extract_review_count(self, text: str) -> Optional[int]:
        """提取评价数量"""
        text_lower = text.lower()
        
        for pattern in self.REVIEW_COUNT_PATTERNS:
            matches = re.finditer(pattern, text_lower)
            for match in matches:
                if match.groups():
                    try:
                        count_str = match.group(1).replace(',', '')
                        return int(count_str)
                    except ValueError:
                        continue
        return None
        
    def _get_context(self, text: str, position: int, window: int = 50) -> str:
        """获取文本上下文"""
        start = max(0, position - window)
        end = min(len(text), position + window)
        return text[start:end].strip()
        
    def extract_from_snapshot(self, snapshot_path: str) -> Dict[str, Any]:
        """从快照文件提取数据"""
        # 读取HTML
        html_path = f"{snapshot_path}.html"
        text_path = f"{snapshot_path}.txt"
        meta_path = f"{snapshot_path}.json"
        
        try:
            with open(html_path, 'r', encoding='utf-8') as f:
                html = f.read()
        except FileNotFoundError:
            html = ''
            
        try:
            with open(text_path, 'r', encoding='utf-8') as f:
                text = f.read()
        except FileNotFoundError:
            text = ''
            
        try:
            with open(meta_path, 'r', encoding='utf-8') as f:
                meta = json.load(f)
                url = meta.get('url', '')
        except FileNotFoundError:
            url = ''
            
        return self.extract(html, text, url)
