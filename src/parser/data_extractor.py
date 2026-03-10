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
        r'US\$\s*[\d,]+\.?\d*',  # US$99.99 (LDShop格式)
        r'from\s+US\$\s*[\d,]+',  # from US$64
        r'only\s+US\$\s*[\d,]+',  # only US$1
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
        r'delivery\s+in\s+(\d+)\s*min',
        r'arrive\s+in\s+(\d+)\s*min',
        r'completed?\s+in\s+(\d+)\s*min',
        r'processed?\s+in\s+(\d+)\s*min',
        r'\d+\s*min(?:utes)?\s*delivery',
        r'fast\s+delivery',
        r'quick\s+delivery',
        r'24[\s/]*7',
        r'around\s+the\s+clock',
    ]
    
    # 交付承诺关键词
    DELIVERY_COMMITMENT_KEYWORDS = [
        'delivery time', 'delivery guarantee', 'arrival time',
        'processing time', 'completion time', 'shipping time',
        'delivery promise', 'guaranteed delivery',
        '到账时间', '发货时效', '交付承诺', '到账承诺',
        '预计时间', '处理时间', '完成时间'
    ]
    
    # 异常声明关键词
    DELIVERY_EXCEPTION_KEYWORDS = [
        'delay', 'exception', 'maintenance', 'busy', 'high demand',
        'may take longer', 'temporarily', 'unavailable',
        '延迟', '异常', '维护', '繁忙', '高峰期', '可能延长'
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
    
    # 修改：移除了空的__init__方法，使用默认的类初始化
        
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
        
        # 检查是否为Trustpilot页面
        if 'trustpilot.com' in url:
            return self._extract_trustpilot_data(soup, text, url)
        
        # 提取游戏列表
        games = self._extract_games(text)
        
        # 提取SKU价格映射（带规格名称）
        sku_prices = self._extract_sku_prices(soup, text, url)
        
        # 提取交付承诺（增强版）
        delivery_commitment = self.extract_delivery_commitment(html, text, url)
        
        data = {
            'url': url,
            'prices': self._extract_prices(text),  # 保留原有价格列表用于兑容
            'sku_prices': sku_prices,  # 新增：带SKU规格的价格列表
            'discounts': self._extract_discounts(text, soup, url),  # 改进：带SKU关联的折扣
            'payments': self._extract_payments(text),
            'delivery_time': self._extract_delivery_time(text),
            'delivery_commitment': delivery_commitment,  # 新增：交付承诺详情
            'promotions': self._extract_promotions(text),
            'games': games,
            'countries': self._extract_countries(text),
            'stock_status': self._extract_stock_status(text),
            # 注意：rating 和 review_count 不再从网站页面提取
            # 评价数据统一从 Trustpilot 获取
            'rating': None,
            'review_count': None,
            'game': games[0] if games else None,  # 主游戏名称（用于价格对比）
            'discount_tags': self._extract_discount_tags(soup, url),  # 新增：SKU级折扣标签
            'payment_promos': self._extract_payment_promos(soup, text, url),  # 新增：支付渠道促销
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
        
    def _extract_sku_prices(self, soup: BeautifulSoup, text: str, url: str) -> List[Dict[str, Any]]:
        """
        提取SKU价格映射（带规格名称）
        支持多种网站结构
        """
        sku_prices = []
        
        # 根据URL判断网站类型
        if 'lootbar.gg' in url:
            sku_prices = self._extract_lootbar_skus(soup)
        elif 'ldshop.gg' in url:
            sku_prices = self._extract_ldshop_skus(soup)
        elif 'topuplive.com' in url:
            sku_prices = self._extract_topuplive_skus(soup, text)
        else:
            # 通用提取逻辑
            sku_prices = self._extract_generic_skus(soup, text)
        
        return sku_prices
        
    def _extract_lootbar_skus(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """提取LootBar网站的SKU价格"""
        sku_prices = []
        
        # LootBar的SKU列表项选择器
        sku_items = soup.find_all('li', class_='topup-list-con-item')
        
        for item in sku_items:
            try:
                # 提取SKU名称
                name_elem = item.find('div', class_='topup-name')
                sku_name = name_elem.get_text(strip=True) if name_elem else ''
                
                # 提取价格（折扣价）
                price_elem = item.find('div', class_='discount-price')
                if price_elem:
                    price_text = price_elem.get_text(strip=True)
                    price_match = re.search(r'\$\s*([\d,]+\.?\d*)', price_text)
                    if price_match:
                        price_value = price_match.group(1).replace(',', '')
                        
                        # 提取原价
                        original_price_elem = item.find('div', class_='discount-del')
                        original_price = None
                        if original_price_elem:
                            orig_match = re.search(r'\$\s*([\d,]+\.?\d*)', original_price_elem.get_text(strip=True))
                            if orig_match:
                                original_price = orig_match.group(1).replace(',', '')
                        
                        # 提取折扣信息
                        discount_elem = item.find('div', class_='c-save-tag')
                        discount = None
                        if discount_elem:
                            discount_match = re.search(r'-?\$?([\d,]+\.?\d*)', discount_elem.get_text(strip=True))
                            if discount_match:
                                discount = discount_match.group(1).replace(',', '')
                        
                        sku_prices.append({
                            'sku_name': sku_name,
                            'price': price_value,
                            'currency': 'USD',
                            'original_price': original_price,
                            'discount': discount,
                            'sku_id': self._generate_sku_id(sku_name)
                        })
            except Exception as e:
                logger.debug(f"提取LootBar SKU失败: {e}")
                continue
        
        return sku_prices
        
    def _extract_ldshop_skus(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """提取LDShop网站的SKU价格"""
        sku_prices = []
        
        # LDShop使用 card-wrapper 作为商品卡片容器
        # 从HTML结构看：
        # - 商品名在 <p class="line-clamp-2..."> 中
        # - 价格在 <span> 中，格式如 "S$ 96.70"
        # - 折扣信息在另一个 <span> 中
        
        # 首先尝试 card-wrapper 选择器
        card_wrappers = soup.find_all('div', class_=lambda c: c and 'card-wrapper' in c)
        
        for card in card_wrappers:
            try:
                # 提取SKU名称 - 在 line-clamp-2 类的 p 标签中
                name = ''
                name_elem = card.find('p', class_=lambda c: c and 'line-clamp-2' in c)
                if name_elem:
                    name = name_elem.get_text(strip=True)
                
                # 如果没找到，尝试其他选择器
                if not name:
                    for name_selector in ['.product-name', '.item-name', 'h3', 'h4', '.title', '[class*="name"]']:
                        name_elem = card.select_one(name_selector)
                        if name_elem:
                            name = name_elem.get_text(strip=True)
                            break
                
                # 提取价格 - 在 bottom-wrapper 内的第一个价格
                price = None
                price_text = ''
                
                # 查找 bottom-wrapper
                bottom_wrapper = card.find('div', class_=lambda c: c and 'bottom-wrapper' in c)
                if bottom_wrapper:
                    # 在 bottom-wrapper 内查找价格
                    price_span = bottom_wrapper.find('span')
                    if price_span:
                        price_text = price_span.get_text(strip=True)
                        # 匹配价格格式：S$ 96.70 或 $ 96.70
                        price_match = re.search(r'[\$S\$]\s*([\d,]+\.?\d*)', price_text)
                        if price_match:
                            price = price_match.group(1).replace(',', '')
                
                # 如果没找到，尝试其他选择器
                if not price:
                    for price_selector in ['.price', '.current-price', '[class*="price"]', '.amount']:
                        price_elem = card.select_one(price_selector)
                        if price_elem:
                            price_text = price_elem.get_text(strip=True)
                            price_match = re.search(r'[\d,]+\.?\d*', price_text)
                            if price_match:
                                price = price_match.group(0).replace(',', '')
                                break
                
                if name and price:
                    sku_prices.append({
                        'sku_name': name,
                        'price': price,
                        'currency': self._detect_currency(price_text) if price_text else 'USD',
                        'sku_id': self._generate_sku_id(name)
                    })
            except Exception:
                continue
        
        # 如果没找到任何SKU，尝试其他选择器作为备选
        if not sku_prices:
            selectors = [
                '.product-item',
                '.price-card',
                '[class*="product"]',
                '[class*="item"]'
            ]
            
            for selector in selectors:
                items = soup.select(selector)
                for item in items:
                    try:
                        name = ''
                        for name_selector in ['.product-name', '.item-name', 'h3', 'h4', '.title']:
                            name_elem = item.select_one(name_selector)
                            if name_elem:
                                name = name_elem.get_text(strip=True)
                                break
                        
                        price = None
                        price_text = ''
                        for price_selector in ['.price', '.current-price', '[class*="price"]', '.amount']:
                            price_elem = item.select_one(price_selector)
                            if price_elem:
                                price_text = price_elem.get_text(strip=True)
                                price_match = re.search(r'[\d,]+\.?\d*', price_text)
                                if price_match:
                                    price = price_match.group(0).replace(',', '')
                                    break
                        
                        if name and price:
                            sku_prices.append({
                                'sku_name': name,
                                'price': price,
                                'currency': self._detect_currency(price_text) if price_text else 'USD',
                                'sku_id': self._generate_sku_id(name)
                            })
                    except Exception:
                        continue
        
        return sku_prices
        
    def _extract_topuplive_skus(self, soup: BeautifulSoup, text: str = '') -> List[Dict[str, Any]]:
        """提取TOPUPlive网站的SKU价格"""
        sku_prices = []
        
        # 策略1: 尝试从页面中的价格卡片结构提取
        selectors = [
            '.product-card',
            '.price-item',
            '[class*="package"]',
            '[class*="sku"]',
            '[class*="product"]',
            '[class*="item"]',
            '.game-item',
            '.top-up-item',
        ]
        
        for selector in selectors:
            items = soup.select(selector)
            for item in items:
                try:
                    # 尝试提取名称
                    name = ''
                    for name_selector in ['.package-name', '.product-title', 'h3', 'h4', '.name', '[class*="title"]', '[class*="name"]']:
                        name_elem = item.select_one(name_selector)
                        if name_elem:
                            name = name_elem.get_text(strip=True)
                            break
                    
                    # 尝试提取价格
                    price = None
                    price_text = ''
                    for price_selector in ['.price', '.current-price', '.sale-price', '[class*="price"]', '[class*="amount"]']:
                        price_elem = item.select_one(price_selector)
                        if price_elem:
                            price_text = price_elem.get_text(strip=True)
                            price_match = re.search(r'[\d,]+\.?\d*', price_text)
                            if price_match:
                                price = price_match.group(0).replace(',', '')
                                break
                    
                    if name and price:
                        sku_prices.append({
                            'sku_name': name,
                            'price': price,
                            'currency': self._detect_currency(price_text) if price_text else 'USD',
                            'sku_id': self._generate_sku_id(name)
                        })
                except Exception:
                    continue
        
        # 策略2: 从页面文本中提取 SKU 名称 + 价格模式
        # TOPUPlive 常见模式：
        # - "60 Genesis Crystals\nS$\n1.12\n1.27" (多行格式)
        # - "60 Genesis Crystals - $0.99" (单行格式)
        if not sku_prices or len(sku_prices) < 3:
            # 多行模式：SKU名称 + S$ + 价格 + 原价
            # 例如：
            # 60 Genesis Crystals
            # S$
            # 1.12
            # 1.27
            multiline_pattern = r'([\w\s\-\*\+]+(?:Crystals?|Crystal|UC|Diamonds?|Gems?|Coins?|Tokens?|Points?|Golds?|Moon|Bundle)[\w\s\-\*\+]*?)\nS\$\s*\n?([\d,]+\.?\d*)'
            
            matches = re.finditer(multiline_pattern, text, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                try:
                    sku_name = match.group(1).strip()
                    price = match.group(2).replace(',', '')
                    # 过滤掉过短或无效的名称
                    if len(sku_name) > 3 and float(price) > 0 and 'S$' not in sku_name:
                        sku_prices.append({
                            'sku_name': sku_name,
                            'price': price,
                            'currency': 'SGD',
                            'sku_id': self._generate_sku_id(sku_name)
                        })
                except (ValueError, IndexError):
                    continue
            
            # 单行模式匹配
            if len(sku_prices) < 3:
                patterns = [
                    # 匹配 "数量 单位/商品名 价格" 格式
                    r'(\d+(?:\s*\+\s*\d+)?\s*(?:Genesis Crystals?|UC|diamonds?|gems?|coins?|tokens?|points?|golds?)[^\n\$]{0,50})\s*[-:]?\s*\$\s*([\d,]+\.?\d*)',
                    # 匹配 "数量+数量 单位" 格式（如 6480+1600）
                    r'(\d+\s*\+\s*\d+\s*[^\n\$]{0,50})\s*[-:]?\s*\$\s*([\d,]+\.?\d*)',
                    # 匹配通用商品名 + 价格
                    r'((?:\d+\s+)?(?:Crystal|Shard|Diamond|Gem|Coin|Token)[^\n\$]{0,30})\s*[-:]?\s*\$\s*([\d,]+\.?\d*)',
                ]
                
                for pattern in patterns:
                    matches = re.finditer(pattern, text, re.IGNORECASE)
                    for match in matches:
                        try:
                            sku_name = match.group(1).strip()
                            price = match.group(2).replace(',', '')
                            # 过滤掉过短的名称
                            if len(sku_name) > 3 and float(price) > 0:
                                sku_prices.append({
                                    'sku_name': sku_name,
                                    'price': price,
                                    'currency': 'USD',
                                    'sku_id': self._generate_sku_id(sku_name)
                                })
                        except (ValueError, IndexError):
                            continue
        
        # 去重
        seen = set()
        unique_prices = []
        for p in sku_prices:
            key = f"{p['sku_id']}_{p['price']}"
            if key not in seen:
                seen.add(key)
                unique_prices.append(p)
        
        return unique_prices
        
    def _extract_generic_skus(self, soup: BeautifulSoup, text: str) -> List[Dict[str, Any]]:
        """通用SKU提取逻辑"""
        sku_prices = []
        
        # 尝试从文本中匹配 SKU 名称 + 价格的模式
        # 常见模式："60 Genesis Crystals - $0.99" 或 "60 Genesis Crystals $0.99"
        patterns = [
            r'(\d+\s*(?:Genesis Crystals?|UC|diamonds?|gems?|coins?)[^\n\$]{0,50})\s*[-:]?\s*\$\s*([\d,]+\.?\d*)',
            r'(\d+\+\d+\s*[^\n\$]{0,50})\s*[-:]?\s*\$\s*([\d,]+\.?\d*)',
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                sku_name = match.group(1).strip()
                price = match.group(2).replace(',', '')
                sku_prices.append({
                    'sku_name': sku_name,
                    'price': price,
                    'currency': 'USD',
                    'sku_id': self._generate_sku_id(sku_name)
                })
        
        return sku_prices
        
    def _generate_sku_id(self, sku_name: str) -> str:
        """
        生成SKU唯一标识
        用于跨天对比同一SKU的价格变化
        """
        # 提取关键信息：数量+单位
        # 例如："60+30 Genesis Crystal" -> "60_30_genesis_crystal"
        normalized = sku_name.lower()
        # 移除特殊字符
        normalized = re.sub(r'[^\w\s+]', '', normalized)
        # 替换空格为下划线
        normalized = re.sub(r'\s+', '_', normalized.strip())
        return normalized
        
    def _detect_currency(self, price_str: str) -> str:
        """检测货币类型"""
        price_str = price_str.upper()
        if 'US$' in price_str or '$' in price_str or 'USD' in price_str:
            return 'USD'
        elif '€' in price_str or 'EUR' in price_str:
            return 'EUR'
        elif '£' in price_str or 'GBP' in price_str:
            return 'GBP'
        elif '¥' in price_str:
            return 'JPY/CNY'
        return 'UNKNOWN'
        
    def _extract_discounts(self, text: str, soup: BeautifulSoup = None, url: str = '') -> List[Dict[str, str]]:
        """
        提取折扣信息，并尝试关联到具体的商品/SKU名称
        """
        discounts = []
        text_lower = text.lower()
        
        # 首先尝试从HTML结构中提取带SKU名称的折扣（更精确）
        if soup and url:
            structured_discounts = self._extract_sku_discounts_from_html(soup, url)
            if structured_discounts:
                return structured_discounts
        
        # 回退到文本提取（带上下文分析）
        for pattern in self.DISCOUNT_PATTERNS:
            matches = re.finditer(pattern, text_lower)
            for match in matches:
                discount_pct = match.group(1) if match.groups() else ''
                context = self._get_context(text_lower, match.start(), 80)
                
                # 尝试从上下文中提取商品名称
                product_name = self._extract_product_name_from_context(context)
                
                discounts.append({
                    'raw': match.group(0),
                    'percentage': discount_pct,
                    'context': context,
                    'product_name': product_name  # 新增：关联的商品名称
                })
                
        return discounts
    
    def _extract_sku_discounts_from_html(self, soup: BeautifulSoup, url: str) -> List[Dict[str, Any]]:
        """
        从HTML结构中提取带SKU名称的折扣信息
        支持 LootBar 和 LDShop
        """
        discounts = []
        
        try:
            if 'lootbar.gg' in url:
                # LootBar: 每个SKU项包含名称和折扣
                items = soup.find_all('li', class_='topup-list-con-item')
                for item in items:
                    name_elem = item.find('div', class_='topup-name')
                    sku_name = name_elem.get_text(strip=True) if name_elem else ''
                    
                    # 查找折扣标签
                    discount_tag = item.find('div', class_='c-save-tag')
                    if discount_tag:
                        tag_text = discount_tag.get_text(strip=True)
                        # 提取折扣百分比
                        pct_match = re.search(r'(\d+)%', tag_text)
                        if pct_match:
                            discounts.append({
                                'raw': tag_text,
                                'percentage': pct_match.group(1),
                                'context': f'{sku_name} {tag_text}',
                                'product_name': sku_name,
                                'sku_name': sku_name
                            })
                    
                    # 检查是否有原价/现价对比可计算折扣
                    orig_elem = item.find('div', class_='discount-del')
                    price_elem = item.find('div', class_='discount-price')
                    if orig_elem and price_elem:
                        orig_match = re.search(r'[\d,]+\.?\d*', orig_elem.get_text())
                        price_match = re.search(r'[\d,]+\.?\d*', price_elem.get_text())
                        if orig_match and price_match:
                            try:
                                orig = float(orig_match.group().replace(',', ''))
                                price = float(price_match.group().replace(',', ''))
                                if orig > price:
                                    pct = round((1 - price / orig) * 100)
                                    discounts.append({
                                        'raw': f'{pct}% off',
                                        'percentage': str(pct),
                                        'context': f'{sku_name} ${price} (was ${orig})',
                                        'product_name': sku_name,
                                        'sku_name': sku_name
                                    })
                            except:
                                pass
                                
            elif 'ldshop.gg' in url:
                # LDShop: 从文本上下文中提取折扣与商品关联
                # LDShop的折扣通常在商品卡片中
                for card in soup.select('[class*="product"], [class*="item"]'):
                    # 查找商品名称
                    name = ''
                    for sel in ['[class*="name"]', '[class*="title"]', 'h3', 'h4']:
                        elem = card.select_one(sel)
                        if elem:
                            name = elem.get_text(strip=True)
                            break
                    
                    # 查找折扣标签
                    for tag_sel in ['[class*="off"]', '[class*="discount"]', '[class*="tag"]']:
                        tag_elem = card.select_one(tag_sel)
                        if tag_elem:
                            tag_text = tag_elem.get_text(strip=True)
                            pct_match = re.search(r'(\d+)%', tag_text, re.IGNORECASE)
                            if pct_match and name:
                                discounts.append({
                                    'raw': tag_text,
                                    'percentage': pct_match.group(1),
                                    'context': f'{name} {tag_text}',
                                    'product_name': name,
                                    'sku_name': name
                                })
                                break
        except Exception as e:
            logger.debug(f"HTML折扣提取失败: {e}")
        
        return discounts
    
    def _extract_product_name_from_context(self, context: str) -> str:
        """
        从折扣上下文中提取商品名称
        """
        # 常见模式：商品名称在折扣前面
        # 例如："Genshin Impact 30%off" 或 "60 Genesis Crystals - 15% off"
        
        # 尝试匹配游戏名称
        game_keywords = {
            'genshin impact': '原神',
            'genshinimpact': '原神',
            'honkai: star rail': '崩坏星穹铁道',
            'honkai star rail': '崩坏星穹铁道',
            'zenless zone zero': '绝区零',
            'wuthering waves': '鸣潮',
            'pubg mobile': 'PUBG',
            'mobile legends': '无尽对决',
            'honor of kings': '王者荣耀',
            'delta force': '三角洲行动',
            'arena breakout': '暗区突围',
            'pokémon tcg pocket': 'Pokémon TCG Pocket',
            'persona5': 'Persona5',
            'persona 5': 'Persona5',
            'pokemon go': 'Pokémon GO',
            'hunterxhunter': 'Hunter x Hunter',
            'lost sword': 'Lost Sword',
            'arknights': 'Arknights',
            'arknights: endfield': 'Arknights: Endfield',
            'chaos zero nightmare': 'Chaos Zero Nightmare',
            'sd gundam': 'SD Gundam',
            'neverness to everness': 'Neverness to Everness',
            'brawl stars': 'Brawl Stars',
            'goddess of victory': 'Goddess of Victory: Nikke',
            'infinity nikki': 'Infinity Nikki',
            'afk journey': 'AFK Journey',
            'bigo live': 'Bigo Live',
            'likee': 'Likee',
            'mico': 'Mico',
            'chamet': 'Chamet',
            'yoho': 'Yoho',
            'yoyo': 'Yoyo',
            'fc 26 coins': 'FC 26 Coins',
            'fc 25 coins': 'FC 25 Coins',
            'efootball': 'eFootball',
            'ea sports fc': 'EA Sports FC',
            'mlb the show': 'MLB The Show',
            'dark and darker': 'Dark and Darker',
            'ragnarok': 'Ragnarok',
            'seven knights': 'Seven Knights',
            'etheria: restart': 'Etheria: Restart',
            'reverse: 1999': 'Reverse: 1999',
            'last war': 'Last War: Survival',
            '2xko': '2XKO',
            'rainbow six': 'Rainbow Six Mobile',
            'sega football': 'SEGA Football',
            'maplestory': 'MapleStory',
            'bleach': 'Bleach: Soul Resonance',
            'crystal of atlan': 'Crystal of Atlan',
            'blue protocol': 'Blue Protocol',
        }
        
        context_lower = context.lower()
        
        # 优先匹配游戏名称
        for keyword, name in game_keywords.items():
            if keyword in context_lower:
                return name
        
        # 尝试匹配SKU规格（如 "60 Genesis Crystals"）
        sku_patterns = [
            r'(\d+\+?\d*\s*(?:genesis crystals?|uc|diamonds?|gems?|coins?|tokens?|points?))',
            r'(\d+\+?\d*\s*(?:crystals?|pack|bundle))',
        ]
        for pattern in sku_patterns:
            match = re.search(pattern, context_lower, re.IGNORECASE)
            if match:
                return match.group(1).strip().title()
        
        return ''
        
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
    
    def extract_delivery_commitment(self, html: str, text: str, url: str) -> Dict[str, Any]:
        """
        提取交付时效承诺与异常声明
        
        Returns:
            {
                'commitments': [],  # 时效承诺列表
                'exceptions': [],   # 异常声明列表
                'sla_summary': '',  # SLA摘要
                'transparency_score': 0  # 透明度评分
            }
        """
        result = {
            'commitments': [],
            'exceptions': [],
            'sla_summary': '',
            'transparency_score': 0,
            'has_clear_sla': False
        }
        
        text_lower = text.lower()
        soup = BeautifulSoup(html, 'lxml')
        
        # 提取时效承诺
        commitments = self._extract_commitments(text_lower, soup)
        result['commitments'] = commitments
        
        # 提取异常声明
        exceptions = self._extract_delivery_exceptions(text_lower, soup)
        result['exceptions'] = exceptions
        
        # 生成SLA摘要
        result['sla_summary'] = self._generate_sla_summary(commitments, exceptions)
        
        # 计算透明度评分
        result['transparency_score'] = self._calculate_transparency_score(
            commitments, exceptions, text_lower
        )
        result['has_clear_sla'] = len(commitments) > 0
        
        return result
    
    def _extract_commitments(self, text: str, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """提取时效承诺"""
        commitments = []
        
        # 1. 从文本中提取时效承诺
        commitment_patterns = [
            r'delivery\s*(?:time|within)?[\s:]*(\d+)\s*(?:min|minutes?|hours?|hrs?)',
            r'arrive?\s*(?:within|in)?[\s:]*(\d+)\s*(?:min|minutes?|hours?|hrs?)',
            r'complete?\s*(?:within|in)?[\s:]*(\d+)\s*(?:min|minutes?|hours?|hrs?)',
            r'process\s*(?:within|in)?[\s:]*(\d+)\s*(?:min|minutes?|hours?|hrs?)',
            r'(\d+)\s*(?:min|minutes?|hours?|hrs?)\s*(?:delivery|arrival|completion)',
            r'instant\s*(?:delivery|top-up|recharge)',
            r'immediate\s*(?:delivery|top-up|recharge)',
            r'within\s*(\d+)\s*(?:min|minutes?|hours?|hrs?)',
            r'(\d+)[-\s]*(\d+)\s*(?:min|minutes?|hours?|hrs?)',
        ]
        
        for pattern in commitment_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                commitment_text = match.group(0)
                context = self._get_context(text, match.start(), 80)
                
                # 提取时间数值
                time_value = self._extract_time_value(commitment_text)
                
                commitments.append({
                    'type': 'time_commitment',
                    'raw': commitment_text,
                    'time_value': time_value,
                    'context': context,
                    'source': 'text'
                })
        
        # 2. 从HTML结构中提取（如专门的时效说明区块）
        try:
            # 查找可能包含时效信息的元素
            time_selectors = [
                '[class*="delivery"]',
                '[class*="shipping"]',
                '[class*="time"]',
                '[class*="eta"]',
            ]
            
            for selector in time_selectors:
                elements = soup.select(selector)
                for elem in elements:
                    elem_text = elem.get_text(strip=True).lower()
                    if any(kw in elem_text for kw in ['min', 'hour', 'instant', 'immediate']):
                        if len(elem_text) < 200:  # 过滤长文本
                            commitments.append({
                                'type': 'time_commitment',
                                'raw': elem_text[:100],
                                'time_value': self._extract_time_value(elem_text),
                                'context': elem_text[:150],
                                'source': 'html_structure'
                            })
        except Exception:
            pass
        
        # 去重
        seen = set()
        unique_commitments = []
        for c in commitments:
            key = c['raw'][:50]
            if key not in seen:
                seen.add(key)
                unique_commitments.append(c)
        
        return unique_commitments[:5]  # 最多返回5条
    
    def _extract_delivery_exceptions(self, text: str, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """提取交付异常声明"""
        exceptions = []
        
        # 异常模式
        exception_patterns = [
            r'delay[^.]{10,100}',
 r'maintenance[^.]{10,100}',
            r'(?:high|heavy)\s+demand[^.]{10,100}',
            r'(?:temporarily|temporarily)\s+unavailable[^.]{10,100}',
            r'may\s+take\s+longer[^.]{10,100}',
            r'exception[^.]{10,100}',
        ]
        
        for pattern in exception_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                exception_text = match.group(0).strip()
                if len(exception_text) > 10:
                    exceptions.append({
                        'type': 'exception_notice',
                        'raw': exception_text[:150],
                        'context': self._get_context(text, match.start(), 60),
                        'severity': self._classify_exception_severity(exception_text)
                    })
        
        # 从HTML结构中提取异常提示
        try:
            alert_selectors = [
                '[class*="alert"]',
                '[class*="warning"]',
                '[class*="notice"]',
                '[class*="exception"]',
            ]
            
            for selector in alert_selectors:
                elements = soup.select(selector)
                for elem in elements:
                    elem_text = elem.get_text(strip=True)
                    if any(kw in elem_text.lower() for kw in ['delay', 'maintenance', 'unavailable', 'longer']):
                        if len(elem_text) < 300:
                            exceptions.append({
                                'type': 'exception_notice',
                                'raw': elem_text[:150],
                                'context': '',
                                'severity': self._classify_exception_severity(elem_text),
                                'source': 'alert_element'
                            })
        except Exception:
            pass
        
        # 去重
        seen = set()
        unique_exceptions = []
        for e in exceptions:
            key = e['raw'][:50]
            if key not in seen:
                seen.add(key)
                unique_exceptions.append(e)
        
        return unique_exceptions[:3]  # 最多返回3条
    
    def _extract_time_value(self, text: str) -> Dict[str, Any]:
        """从文本中提取时间数值"""
        result = {'value': None, 'unit': None, 'is_instant': False}
        
        text_lower = text.lower()
        
        # 即时交付
        if any(kw in text_lower for kw in ['instant', 'immediate', 'now', 'real-time']):
            result['is_instant'] = True
            result['value'] = 0
            result['unit'] = 'instant'
            return result
        
        # 提取数值和单位
        time_match = re.search(r'(\d+)\s*(min|minute|minutes|hr|hour|hours|hrs?)', text_lower)
        if time_match:
            result['value'] = int(time_match.group(1))
            unit = time_match.group(2)
            if unit.startswith('min'):
                result['unit'] = 'minutes'
            elif unit.startswith('hr') or unit.startswith('hour'):
                result['unit'] = 'hours'
        
        # 提取范围（如 5-10 minutes）
        range_match = re.search(r'(\d+)\s*[-~to]+\s*(\d+)\s*(min|minute|minutes|hr|hour|hours)', text_lower)
        if range_match:
            result['value'] = int(range_match.group(1))
            result['value_max'] = int(range_match.group(2))
            result['unit'] = 'minutes' if range_match.group(3).startswith('min') else 'hours'
        
        return result
    
    def _classify_exception_severity(self, text: str) -> str:
        """分类异常严重程度"""
        text_lower = text.lower()
        
        if any(kw in text_lower for kw in ['unavailable', 'suspend', 'stop', 'closed']):
            return 'high'
        elif any(kw in text_lower for kw in ['delay', 'maintenance', 'busy', 'high demand']):
            return 'medium'
        return 'low'
    
    def _generate_sla_summary(self, commitments: List[Dict], exceptions: List[Dict]) -> str:
        """生成SLA摘要"""
        if not commitments:
            return '未找到明确的交付时效承诺'
        
        # 找出最快的承诺
        instant_count = sum(1 for c in commitments if c.get('time_value', {}).get('is_instant'))
        
        if instant_count > 0:
            summary = '承诺即时到账'
        else:
            # 找出最小时间
            min_time = None
            for c in commitments:
                time_val = c.get('time_value', {})
                if time_val.get('value') is not None:
                    minutes = time_val['value']
                    if time_val.get('unit') == 'hours':
                        minutes *= 60
                    if min_time is None or minutes < min_time:
                        min_time = minutes
            
            if min_time is not None:
                if min_time < 60:
                    summary = f'承诺{min_time}分钟内到账'
                else:
                    summary = f'承诺{min_time // 60}小时内到账'
            else:
                summary = '有交付时效承诺但无法提取具体时间'
        
        # 添加异常信息
        if exceptions:
            high_severity = [e for e in exceptions if e.get('severity') == 'high']
            if high_severity:
                summary += f'（注意：存在{len(high_severity)}个严重异常声明）'
        
        return summary
    
    def _calculate_transparency_score(self, commitments: List[Dict], 
                                       exceptions: List[Dict], text: str) -> int:
        """计算交付透明度评分 (0-100)"""
        score = 0
        
        # 有明确时效承诺 +30分
        if commitments:
            score += 30
            # 有具体时间数值 +10分
            if any(c.get('time_value', {}).get('value') is not None for c in commitments):
                score += 10
        
        # 有异常声明机制 +20分
        if exceptions:
            score += 20
        
        # 页面位置可见性（通过关键词判断）
        if any(kw in text for kw in ['delivery', 'shipping', 'time', 'arrival']):
            score += 20
        
        # 有服务等级说明 +20分
        if any(kw in text for kw in ['guarantee', 'promise', 'sla', 'service level']):
            score += 20
        
        return min(100, score)
        
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
            'genshinimpact': '原神',
            'pubg': 'PUBG',
            'pubg mobile': 'PUBG',
            'honkai star rail': '崩坏星穹铁道',
            'honkai-star-rail': '崩坏星穹铁道',
            'zenless zone zero': '绝区零',
            'zenless-zone-zero': '绝区零',
            'wuthering waves': '鸣潮',
            'wuthering-waves': '鸣潮',
            'mobile legends': '无尽对决',
            'mlbb': '无尽对决',
            'honor of kings': '王者荣耀',
            'honor-of-kings': '王者荣耀',
            'delta force': '三角洲行动',
            'delta-force': '三角洲行动',
            'arena breakout': '暗区突围',
            'arena-breakout': '暗区突围',
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
        
    def _extract_trustpilot_data(self, soup: BeautifulSoup, text: str, url: str) -> Dict[str, Any]:
        """
        从Trustpilot页面提取评价数据
        
        Args:
            soup: BeautifulSoup对象
            text: 页面纯文本
            url: 页面URL
            
        Returns:
            Trustpilot评价数据字典
        """
        data = {
            'url': url,
            'type': 'trustpilot_review',
            'rating': None,
            'review_count': None,
            'trust_score': None,
            'site_name': None,
            'rating_distribution': {},
        }
        
        try:
            # 提取站点名称
            if 'www.lootbar.gg' in url:
                data['site_name'] = 'LootBar'
            elif 'www.ldshop.gg' in url:
                data['site_name'] = 'LDShop'
            
            # 提取评分 - Trustpilot通常在标题或meta中显示 "X out of 5 stars"
            # 尝试从页面标题提取
            title_elem = soup.find('title')
            if title_elem:
                title_text = title_elem.get_text()
                # 匹配模式: "4.5 out of 5 stars" 或 "4.5 stars"
                rating_match = re.search(r'(\d+\.?\d*)\s*out of\s*5\s*stars?', title_text, re.IGNORECASE)
                if rating_match:
                    data['rating'] = float(rating_match.group(1))
                else:
                    # 尝试其他模式
                    rating_match = re.search(r'(\d+\.?\d*)\s*stars?', title_text, re.IGNORECASE)
                    if rating_match:
                        data['rating'] = float(rating_match.group(1))
            
            # 从页面内容中提取评分（备用方案）
            if data['rating'] is None:
                # Trustpilot评分通常在特定元素中
                rating_selectors = [
                    '[data-rating]',
                    '.star-rating',
                    '[class*="rating"]',
                    '[class*="score"]'
                ]
                for selector in rating_selectors:
                    elem = soup.select_one(selector)
                    if elem:
                        rating_text = elem.get_text() or elem.get('data-rating', '')
                        rating_match = re.search(r'(\d+\.?\d*)', rating_text)
                        if rating_match:
                            data['rating'] = float(rating_match.group(1))
                            break
            
            # 提取评价数量
            # Trustpilot格式: "1,234 Reviews" 或 "Based on 1,234 reviews"
            review_patterns = [
                r'Based on\s+([\d,]+)\s+reviews?',
                r'([\d,]+)\s+reviews?',
                r'total\s+([\d,]+)\s+reviews?',
            ]
            for pattern in review_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    count_str = match.group(1).replace(',', '')
                    data['review_count'] = int(count_str)
                    break
            
            # 提取Trust Score（信任分数）
            trust_score_patterns = [
                r'trustscore\s*(\d+\.?\d*)',
                r'trust score\s*(\d+\.?\d*)',
            ]
            for pattern in trust_score_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    data['trust_score'] = float(match.group(1))
                    break
            
            # 提取评分分布（各星级评价数量）
            # 查找包含星级分布的元素
            for star in [5, 4, 3, 2, 1]:
                star_patterns = [
                    rf'{star}\s*star[s]?\s*[:\-]?\s*([\d,]+)',
                    rf'{star}\s*[:\-]?\s*([\d,]+)',
                ]
                for pattern in star_patterns:
                    match = re.search(pattern, text, re.IGNORECASE)
                    if match and match.group(1):
                        count_str = match.group(1).replace(',', '')
                        if count_str:  # 确保不是空字符串
                            try:
                                data['rating_distribution'][f'{star}_star'] = int(count_str)
                            except ValueError:
                                pass
                        break
            
            logger.info(f"Trustpilot数据提取完成: {data['site_name']}, "
                       f"评分: {data['rating']}, 评价数: {data['review_count']}")
            
        except Exception as e:
            logger.warning(f"Trustpilot数据提取失败: {url}, {e}")
        
        return data
        
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

    # ================================================================
    # 新增：SKU级折扣标签提取
    # ================================================================

    def _extract_discount_tags(self, soup: BeautifulSoup, url: str) -> List[Dict[str, Any]]:
        """
        提取页面上SKU的折扣标签，包括：
        - 折扣百分比（如 -18% OFF）
        - 对应的SKU名称
        - 划线原价
        - 当前售价
        """
        tags = []
        try:
            if 'lootbar.gg' in url:
                tags = self._extract_lootbar_discount_tags(soup)
            elif 'ldshop.gg' in url:
                tags = self._extract_ldshop_discount_tags(soup)
        except Exception as e:
            logger.debug(f"折扣标签提取失败: {e}")
        return tags

    def _extract_lootbar_discount_tags(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """LootBar SKU级折扣标签"""
        tags = []
        items = soup.find_all('li', class_='topup-list-con-item')
        for item in items:
            try:
                name_elem = item.find('div', class_='topup-name')
                sku_name = name_elem.get_text(strip=True) if name_elem else ''

                # 折扣标签（如 -18% OFF）
                tag_text = ''
                for tag_cls in ['c-save-tag', 'discount-tag', 'off-tag']:
                    tag_elem = item.find(class_=lambda c: c and tag_cls in c)
                    if tag_elem:
                        tag_text = tag_elem.get_text(strip=True)
                        break

                # 划线原价
                original_price = ''
                orig_elem = item.find('div', class_=lambda c: c and 'discount-del' in (c or ''))
                if orig_elem:
                    m = re.search(r'[\d,]+\.?\d*', orig_elem.get_text())
                    original_price = m.group(0).replace(',', '') if m else ''

                # 售价
                sale_price = ''
                price_elem = item.find('div', class_=lambda c: c and 'discount-price' in (c or ''))
                if price_elem:
                    m = re.search(r'[\d,]+\.?\d*', price_elem.get_text())
                    sale_price = m.group(0).replace(',', '') if m else ''

                # 计算折扣百分比
                discount_pct = ''
                if original_price and sale_price:
                    try:
                        orig_f = float(original_price)
                        sale_f = float(sale_price)
                        if orig_f > 0 and sale_f < orig_f:
                            discount_pct = f"-{round((1 - sale_f / orig_f) * 100)}%"
                    except Exception:
                        pass

                if sku_name and (tag_text or discount_pct):
                    tags.append({
                        'sku_name': sku_name,
                        'discount_tag': tag_text or discount_pct,
                        'original_price': original_price,
                        'sale_price': sale_price,
                        'discount_pct': discount_pct
                    })
            except Exception:
                continue
        return tags

    def _extract_ldshop_discount_tags(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """LDShop SKU级折扣标签"""
        tags = []
        # LDShop使用 card-wrapper 作为商品卡片容器
        for card in soup.find_all('div', class_=lambda c: c and 'card-wrapper' in c):
            try:
                # 名称 - 在 line-clamp-2 类的 p 标签中
                name = ''
                name_elem = card.find('p', class_=lambda c: c and 'line-clamp-2' in c)
                if name_elem:
                    name = name_elem.get_text(strip=True)
                    
                # 如果没找到，尝试其他选择器
                if not name:
                    for sel in ['[class*="name"]', '[class*="title"]', 'h3', 'h4']:
                        elem = card.select_one(sel)
                        if elem:
                            name = elem.get_text(strip=True)
                            break
    
                # 折扣标签 - 在 c-#FD8E12 类的 span 中
                tag_text = ''
                discount_span = card.find('span', class_=lambda c: c and 'c-#FD8E12' in c and 'font-700' in c)
                if discount_span:
                    tag_text = discount_span.get_text(strip=True)
    
                # 计算折扣百分比
                orig_price = ''
                sale_price = ''
                    
                # 在 bottom-wrapper 内查找价格
                bottom_wrapper = card.find('div', class_=lambda c: c and 'bottom-wrapper' in c)
                if bottom_wrapper:
                    # 查找所有价格相关的 span
                    spans = bottom_wrapper.find_all('span')
                    for span in spans:
                        span_text = span.get_text(strip=True)
                        # 检查是否是划线价格（原价）
                        if 'line-through' in str(span.get('class', [])) or span_text.startswith('S$'):
                            m = re.search(r'[\$S\$]\s*([\d,]+\.?\d*)', span_text)
                            if m:
                                if 'line-through' in str(span.get('class', [])):
                                    orig_price = m.group(1).replace(',', '')
                                else:
                                    sale_price = m.group(1).replace(',', '')
                    
                # 如果没找到，尝试其他选择器
                if not orig_price:
                    for p_sel in ['[class*="original"]', '[class*="del"]', 's', 'del', '.line-through']:
                        e = card.select_one(p_sel)
                        if e:
                            m = re.search(r'[\d,]+\.?\d*', e.get_text())
                            orig_price = m.group(0).replace(',', '') if m else ''
                            break
                    
                if not sale_price:
                    for p_sel in ['[class*="current"]', '[class*="sale"]', '[class*="price"]']:
                        e = card.select_one(p_sel)
                        if e:
                            m = re.search(r'[\d,]+\.?\d*', e.get_text())
                            sale_price = m.group(0).replace(',', '') if m else ''
                            break
    
                if name and (tag_text or orig_price):
                    tags.append({
                        'sku_name': name,
                        'discount_tag': tag_text,
                        'original_price': orig_price,
                        'sale_price': sale_price,
                    })
            except Exception:
                continue
        return tags

    # ================================================================
    # 新增：支付渠道促销提取
    # ================================================================

    def _extract_payment_promos(self, soup: BeautifulSoup, text: str, url: str) -> List[str]:
        """
        提取页面底部或结购区的支付渠道促销信息。
        主要针对LDShop和其他站点。
        """
        promos = []
        try:
            # 支付促销关键词匹配（文本层）
            pay_promo_patterns = [
                r'(?:use|pay\s+with|via)\s+[\w\s]+(?:wallet|pay|card|payment)[^.\n]{0,60}(?:\d+%|\$\d+|free)',
                r'(?:extra|additional|bonus)\s+\d+%[^.\n]{0,60}(?:wallet|pay|deposit)',
                r'(?:waive|no|zero)\s+(?:fee|charge|commission)[^.\n]{0,60}',
                r'\d+%\s*(?:cashback|rebate|bonus)[^.\n]{0,60}',
                r'(?:save|get)\s+\d+%?[^.\n]{0,50}(?:when|if|for)[^.\n]{0,50}(?:pay|wallet|card)',
            ]
            text_lower = text.lower()
            for pat in pay_promo_patterns:
                for m in re.finditer(pat, text_lower):
                    snippet = m.group(0).strip()
                    if len(snippet) > 8:
                        promos.append(snippet)

            # HTML结构层：支付区域内的促销文字
            for sel in [
                '[class*="payment"] [class*="promo"]',
                '[class*="payment"] [class*="offer"]',
                '[class*="checkout"] [class*="promo"]',
                '[class*="pay-method"] p',
                '[class*="wallet"] [class*="bonus"]',
            ]:
                for elem in soup.select(sel):
                    t = elem.get_text(strip=True)
                    if t and len(t) > 6:
                        promos.append(t)

            # 去重并限制数量
            seen = set()
            unique = []
            for p in promos:
                key = p[:40]
                if key not in seen:
                    seen.add(key)
                    unique.append(p)
            promos = unique[:6]

        except Exception as e:
            logger.debug(f"支付促销提取失败: {e}")

        return promos

    # ================================================================
    # 新增：游戏列表页商品数量提取
    # ================================================================

    def extract_game_catalog_info(self, html: str, text: str, url: str) -> Dict[str, Any]:
        """
        从游戏列表页（catalog/all, /top-up/, /game/）提取商品数量信息
        
        Returns:
            {
                'total_items': 商品总数,
                'games_list': 游戏名称列表,
                'is_catalog_page': 是否为游戏列表页
            }
        """
        info = {
            'total_items': None,
            'games_list': [],
            'is_catalog_page': False
        }
        
        # 判断是否为游戏列表页
        catalog_patterns = [
            r'/catalog/all',
            r'/top-up/?$',
            r'/game/game-mobile/',
            r'/game/?$'
        ]
        
        is_catalog = any(re.search(pattern, url, re.IGNORECASE) for pattern in catalog_patterns)
        if not is_catalog:
            return info
        
        info['is_catalog_page'] = True
        
        # 提取商品总数 - 各平台特定模式
        if 'ldshop.gg' in url:
            # LDShop: "Found results:184"
            match = re.search(r'Found\s+results[:\s]*(\d+)', text, re.IGNORECASE)
            if match:
                info['total_items'] = int(match.group(1))
        
        elif 'lootbar.gg' in url:
            # LootBar: "Total 128 items"
            match = re.search(r'Total\s+(\d+)\s+items?', text, re.IGNORECASE)
            if match:
                info['total_items'] = int(match.group(1))
        
        elif 'topuplive.com' in url:
            # TOPUPlive: "Result found : 106"
            match = re.search(r'Result\s+found\s*[:\s]*(\d+)', text, re.IGNORECASE)
            if match:
                info['total_items'] = int(match.group(1))
        
        # 通用模式作为备选
        if info['total_items'] is None:
            generic_patterns = [
                r'found\s+results?[:\s]*(\d+)',
                r'total\s+(\d+)\s+items?',
                r'result\s+found\s*[:\s]*(\d+)',
                r'(\d+)\s+results?\s+found',
                r'showing\s+\d+[-\s]of\s+(\d+)',
                r'(\d+)\s+products?',
                r'(\d+)\s+games?'
            ]
            for pattern in generic_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    info['total_items'] = int(match.group(1))
                    break
        
        # 提取游戏列表
        info['games_list'] = self._extract_games_from_catalog(soup=BeautifulSoup(html, 'lxml'), text=text, url=url)
        
        return info
    
    def _extract_games_from_catalog(self, soup: BeautifulSoup, text: str, url: str) -> List[str]:
        """
        从游戏列表页提取所有游戏名称
        """
        games = set()
        
        # 游戏关键词映射（扩展版）
        game_keywords = {
            '原神': ['genshin impact', 'genshinimpact', '原神'],
            'PUBG': ['pubg', 'pubg mobile', '绝地求生'],
            '崩坏星穹铁道': ['honkai star rail', 'honkai-star-rail', '崩坏星穹铁道', '星穹铁道'],
            '绝区零': ['zenless zone zero', 'zenless-zone-zero', '绝区零', 'zzz'],
            '鸣潮': ['wuthering waves', 'wuthering-waves', '鸣潮'],
            '无尽对决': ['mobile legends', 'mlbb', 'mobile-legends', '无尽对决'],
            '王者荣耀': ['honor of kings', 'honor-of-kings', '王者荣耀', 'hok'],
            '三角洲行动': ['delta force', 'delta-force', '三角洲行动'],
            '暗区突围': ['arena breakout', 'arena-breakout', '暗区突围'],
            'Pokémon TCG Pocket': ['pokémon tcg pocket', 'pokemon tcg pocket', 'pokémon tcg', 'pokemon tcg'],
            'Persona5': ['persona 5', 'persona5', 'p5'],
            'Pokémon GO': ['pokemon go', 'pokémon go'],
            'Hunter x Hunter': ['hunter x hunter', 'hunterxhunter'],
            'Lost Sword': ['lost sword', 'lostsword'],
            'Arknights': ['arknights', '明日方舟'],
            'Arknights: Endfield': ['arknights endfield', 'arknights: endfield'],
            'Chaos Zero Nightmare': ['chaos zero nightmare', 'chaos zero'],
            'SD Gundam': ['sd gundam', 'sd 高达'],
            'Neverness to Everness': ['neverness to everness', 'nte'],
            'Brawl Stars': ['brawl stars', '荒野乱斗'],
            'Goddess of Victory: Nikke': ['goddess of victory', 'nikke', '胜利女神'],
            'Infinity Nikki': ['infinity nikki', '无限暖暖'],
            'AFK Journey': ['afk journey', '剑与远征'],
            'Bigo Live': ['bigo live', 'bigo'],
            'Likee': ['likee'],
            'Mico': ['mico'],
            'Chamet': ['chamet'],
            'Yoho': ['yoho'],
            'Yoyo': ['yoyo'],
            'FC 26 Coins': ['fc 26 coins', 'fc26', 'ea fc 26'],
            'FC 25 Coins': ['fc 25 coins', 'fc25', 'ea fc 25'],
            'eFootball': ['efootball', '实况足球'],
            'EA Sports FC': ['ea sports fc'],
            'MLB The Show': ['mlb the show'],
            'Dark and Darker': ['dark and darker'],
            'Ragnarok': ['ragnarok', '仙境传说'],
            'Seven Knights': ['seven knights'],
            'Etheria: Restart': ['etheria restart', 'etheria: restart'],
            'Reverse: 1999': ['reverse 1999', 'reverse: 1999', '重返未来'],
            'Last War: Survival': ['last war', 'last war survival', 'last war: survival'],
            '2XKO': ['2xko'],
            'Rainbow Six Mobile': ['rainbow six', 'rainbow six mobile'],
            'SEGA Football': ['sega football'],
            'MapleStory': ['maplestory', '冒险岛'],
            'Bleach: Soul Resonance': ['bleach', 'bleach soul resonance'],
            'Crystal of Atlan': ['crystal of atlan'],
            'Blue Protocol': ['blue protocol'],
        }
        
        text_lower = text.lower()
        
        # 从文本中匹配游戏
        for game_name, keywords in game_keywords.items():
            for keyword in keywords:
                if keyword.lower() in text_lower:
                    games.add(game_name)
                    break
        
        # 从HTML结构中提取（针对列表页）
        try:
            # 常见的游戏卡片选择器
            card_selectors = [
                '[class*="game-item"]',
                '[class*="product-item"]',
                '[class*="game-card"]',
                '[class*="topup-item"]',
                '.game-list > div',
                '.product-list > div',
                '[class*="catalog"] [class*="item"]',
                '[class*="grid"] > a',
            ]
            
            for selector in card_selectors:
                items = soup.select(selector)
                for item in items:
                    item_text = item.get_text(strip=True).lower()
                    for game_name, keywords in game_keywords.items():
                        for keyword in keywords:
                            if keyword.lower() in item_text:
                                games.add(game_name)
                                break
        except Exception:
            pass
        
        return sorted(list(games))
