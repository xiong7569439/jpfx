"""
差异分析引擎
对比今日与昨日快照，发现变化
"""

import os
import json
import difflib
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple, Set

from bs4 import BeautifulSoup

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
                    
                    # 读取HTML内容（用于结构化数据提取）
                    html_path = meta_path.replace('.json', '.html')
                    if os.path.exists(html_path):
                        with open(html_path, 'r', encoding='utf-8') as f:
                            meta['html'] = f.read()
                            
                    return meta
                except Exception as e:
                    logger.error(f"加载快照失败: {meta_path}, 错误: {e}")
                    
        return None
        
    def load_snapshot_data_by_identifier(self, site_name: str, page_type: str,
                                         date_str: str, identifier: str) -> Optional[Dict[str, Any]]:
        """
        根据页面标识符加载快照数据
        
        Args:
            site_name: 站点名称
            page_type: 页面类型
            date_str: 日期字符串
            identifier: 页面标识符（如URL路径）
        """
        snapshot_dir = os.path.join(
            self.paths_config.get('snapshot_base', './data/snapshots'),
            date_str,
            site_name
        )
        
        if not os.path.exists(snapshot_dir):
            return None
        
        # 如果没有标识符，使用原来的方法
        if not identifier:
            return self.load_snapshot_data(site_name, page_type, date_str)
        
        # 尝试找到匹配的文件
        for filename in os.listdir(snapshot_dir):
            if not filename.startswith(f"{page_type}_") or not filename.endswith('.json'):
                continue
                
            # 检查文件名是否包含标识符
            if identifier in filename:
                meta_path = os.path.join(snapshot_dir, filename)
                try:
                    with open(meta_path, 'r', encoding='utf-8') as f:
                        meta = json.load(f)
                        
                    # 读取文本内容
                    text_path = meta_path.replace('.json', '.txt')
                    if os.path.exists(text_path):
                        with open(text_path, 'r', encoding='utf-8') as f:
                            meta['text'] = f.read()
                    
                    # 读取HTML内容（用于结构化数据提取）
                    html_path = meta_path.replace('.json', '.html')
                    if os.path.exists(html_path):
                        with open(html_path, 'r', encoding='utf-8') as f:
                            meta['html'] = f.read()
                            
                    return meta
                except Exception as e:
                    logger.error(f"加载快照失败: {meta_path}, 错误: {e}")
                    
        # 如果没找到精确匹配，尝试模糊匹配
        return self.load_snapshot_data(site_name, page_type, date_str)
        
    # 噪音模式 - 需要过滤的无意义变化
    NOISE_PATTERNS = [
        r'\d{4}[-/]\d{1,2}[-/]\d{1,2}',  # 日期 2024-01-15
        r'\d{1,2}:\d{2}',  # 时间 14:30
        r'\d+\s*(minutes?|hours?|days?|weeks?|months?)\s*ago',  # 相对时间
        r'\d+\s*(views?|likes?|comments?|shares?)',  # 社交计数
        r'crawl_time',  # 抓取时间戳
        r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}',  # ISO时间戳
    ]
    
    # 评价数据模式 - 需要过滤的评价相关变化（因为现在从 Trustpilot 获取）
    # 注意：这些模式用于 _is_noise 方法过滤文本变化，但结构化数据中的评价变化需要单独处理
    REVIEW_PATTERNS = [
        r'\d+[\d,\s]*\s*reviews?',  # 评价数量，如 "531,430 reviews" 或 "40 570 reviews"
        r'reviews?\s*[:\-]?\s*\d+[\d,\s]*',  # 评价数量反向格式，如 "Reviews: 40,570" 或 "Reviews 40,570"
        r'\d+\.?\d*\s*stars?',  # 星级评分，如 "5.0 stars"
        r'\d+\.?\d*\s*out of\s*5',  # 评分格式
        r'rating[:\s]*\d+\.?\d*',  # rating: 4.5
        r'★+',  # 星级符号
    ]
    
    # 评价相关字段 - 在结构化数据对比中忽略
    REVIEW_FIELDS = {'rating', 'review_count', 'reviews', 'stars', 'score'}
    
    def _is_noise(self, content: str) -> bool:
        """判断内容是否为噪音"""
        import re
        content = content.strip()
        
        # 空内容
        if not content:
            return True
        
        # 太短的内容
        if len(content) < 5:
            return True
        
        # 匹配噪音模式
        for pattern in self.NOISE_PATTERNS:
            if re.search(pattern, content, re.IGNORECASE):
                return True
        
        # 匹配评价数据模式（因为现在从 Trustpilot 获取，忽略网站页面的评价变化）
        for pattern in self.REVIEW_PATTERNS:
            if re.search(pattern, content, re.IGNORECASE):
                return True
        
        return False
        
    def compare_text(self, old_text: str, new_text: str, url: str = '') -> List[Dict[str, Any]]:
        """
        对比文本差异
        
        Args:
            old_text: 旧文本
            new_text: 新文本
            url: 页面URL（用于判断页面类型）
            
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
                content = line[2:]
                if not self._is_noise(content):
                    changes.append({
                        'type': 'add',
                        'content': content
                    })
            elif line.startswith('- '):
                content = line[2:]
                if not self._is_noise(content):
                    changes.append({
                        'type': 'remove',
                        'content': content
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
        
        # 过滤评价相关字段的变化（因为现在只从 Trustpilot 获取评价数据）
        # 创建数据的副本，移除评价相关字段
        old_data_filtered = {k: v for k, v in old_data.items() if k not in self.REVIEW_FIELDS}
        new_data_filtered = {k: v for k, v in new_data.items() if k not in self.REVIEW_FIELDS}
        
        # 使用过滤后的数据进行后续对比
        old_data = old_data_filtered
        new_data = new_data_filtered
        
        # 优先使用SKU级别的价格对比（如果有sku_prices字段）
        old_sku_prices = old_data.get('sku_prices', [])
        new_sku_prices = new_data.get('sku_prices', [])
        
        if old_sku_prices and new_sku_prices:
            # 使用SKU级别的对比
            sku_differences = self._compare_sku_prices(old_sku_prices, new_sku_prices)
            differences.extend(sku_differences)
        else:
            # 回退到原有的价格对比逻辑，但改进价格变化检测
            old_prices_list = old_data.get('prices', [])
            new_prices_list = new_data.get('prices', [])
            
            # 获取SKU名称映射（从discounts上下文中提取价格与SKU的关联）
            sku_name_map = {}  # price_value -> sku_name
            price_context_map = {}  # price_value -> context (用于后续分析)
            
            for discount in new_data.get('discounts', []):
                context = discount.get('context', '')
                product_name = discount.get('product_name', '')
                if context:
                    # 从上下文中提取价格
                    import re
                    price_matches = re.findall(r'[\$\£\€]\s*(\d+\.?\d*)', context)
                    for price_val in price_matches:
                        price_context_map[price_val] = context
                        if product_name:
                            sku_name_map[price_val] = product_name
            
            # 尝试从上下文中提取更详细的SKU规格（如 "60 Genesis Crystals"）
            detailed_sku_map = {}  # price_value -> detailed_sku_name
            for price_val, context in price_context_map.items():
                # 尝试匹配SKU规格模式
                sku_patterns = [
                    r'(\d+\+?\d*\s*(?:Genesis Crystals?|UC|diamonds?|gems?|coins?|tokens?|points?|golds?))',
                    r'(\d+\+?\d*\s*(?:crystals?|pack|bundle|card))',
                    r'(\d+\s*[-+]\s*\d+\s*\w+)',
                ]
                for pattern in sku_patterns:
                    match = re.search(pattern, context, re.IGNORECASE)
                    if match:
                        detailed_sku = match.group(1).strip()
                        # 如果有产品名称，组合起来
                        if price_val in sku_name_map:
                            detailed_sku_map[price_val] = f"{sku_name_map[price_val]} {detailed_sku}"
                        else:
                            detailed_sku_map[price_val] = detailed_sku
                        break
            
            # 使用价格匹配算法检测变化（而非简单的新增/移除）
            matched_old = set()
            matched_new = set()
            
            # 1. 尝试匹配相似价格（变化幅度小于5%认为是同一产品的价格调整）
            for i, new_price in enumerate(new_prices_list):
                new_val = float(new_price['value'])
                for j, old_price in enumerate(old_prices_list):
                    if j in matched_old:
                        continue
                    old_val = float(old_price['value'])
                    
                    # 计算变化幅度
                    if old_val > 0:
                        change_pct = abs(new_val - old_val) / old_val
                        # 如果变化小于5%，认为是同一产品的价格调整
                        if change_pct < 0.05:
                            matched_old.add(j)
                            matched_new.add(i)
                            
                            if abs(new_val - old_val) > 0.01:  # 实际有变化
                                direction = "上涨" if new_val > old_val else "下调"
                                change_amount = abs(new_val - old_val)
                                change_pct = (change_amount / old_val) * 100
                                
                                # 优先使用详细的SKU名称
                                sku_name = detailed_sku_map.get(new_price['value'], '')
                                if not sku_name:
                                    sku_name = sku_name_map.get(new_price['value'], '')
                                
                                # 构建价格变动描述
                                if sku_name:
                                    description = f"{sku_name} 价格{direction}: {old_price['raw']} → {new_price['raw']} ({change_pct:+.1f}%)"
                                else:
                                    description = f"价格{direction}: {old_price['raw']} → {new_price['raw']} ({change_pct:+.1f}%)"
                                
                                differences.append({
                                    'field': 'price',
                                    'type': 'change',
                                    'value': new_price,
                                    'old_value': old_price,
                                    'description': description,
                                    'sku_name': sku_name
                                })
                            break
            
            # 2. 真正新增的价格（未匹配到任何旧价格）
            for i, price in enumerate(new_prices_list):
                if i not in matched_new:
                    # 优先使用详细的SKU名称
                    sku_name = detailed_sku_map.get(price['value'], '')
                    if not sku_name:
                        sku_name = sku_name_map.get(price['value'], '')
                    
                    if sku_name:
                        description = f"新增SKU {sku_name}: {price['raw']}"
                    else:
                        description = f"新增价格: {price['raw']}"
                    
                    differences.append({
                        'field': 'price',
                        'type': 'add',
                        'value': price,
                        'description': description,
                        'sku_name': sku_name
                    })
                    
            # 3. 真正移除的价格（未匹配到任何新价格）
            for j, price in enumerate(old_prices_list):
                if j not in matched_old:
                    # 尝试从旧数据的上下文中查找SKU名称
                    old_sku_name = ''
                    for discount in old_data.get('discounts', []):
                        context = discount.get('context', '')
                        product_name = discount.get('product_name', '')
                        if context and price['value'] in context:
                            old_sku_name = product_name
                            break
                    
                    if old_sku_name:
                        description = f"移除SKU {old_sku_name}: {price['raw']}"
                    else:
                        description = f"移除价格: {price['raw']}"
                    
                    differences.append({
                        'field': 'price',
                        'type': 'remove',
                        'value': price,
                        'description': description,
                        'sku_name': old_sku_name
                    })
                
        # 对比折扣（带SKU名称关联）
        old_discounts = {d.get('raw', ''): d for d in old_data.get('discounts', []) if d.get('raw')}
        new_discounts = {d.get('raw', ''): d for d in new_data.get('discounts', []) if d.get('raw')}
        
        added_discount_keys = set(new_discounts.keys()) - set(old_discounts.keys())
        for key in added_discount_keys:
            if key:
                discount_data = new_discounts[key]
                product_name = discount_data.get('product_name', '') or discount_data.get('sku_name', '')
                
                if product_name:
                    description = f"{product_name} 新增折扣: {key}"
                else:
                    description = f"新增折扣: {key}"
                
                differences.append({
                    'field': 'discount',
                    'type': 'add',
                    'value': discount_data,
                    'description': description
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
        old_delivery = set(d.get('raw', '') for d in old_data.get('delivery_time', []) if d.get('raw'))
        new_delivery = set(d.get('raw', '') for d in new_data.get('delivery_time', []) if d.get('raw'))
        
        added_delivery = new_delivery - old_delivery
        for d in added_delivery:
            if d:
                differences.append({
                    'field': 'delivery',
                    'type': 'add',
                    'value': d,
                    'description': f"新增时效承诺: {d}"
                })
            
        # 对比促销
        old_promos = set(p.get('raw', '') for p in old_data.get('promotions', []) if p.get('raw'))
        new_promos = set(p.get('raw', '') for p in new_data.get('promotions', []) if p.get('raw'))
        
        added_promos = new_promos - old_promos
        for p in added_promos:
            if p:
                differences.append({
                    'field': 'promotion',
                    'type': 'add',
                    'value': p,
                    'description': f"新增促销: {p}"
                })
        
        # 对比国家/地区支持
        old_countries = set(old_data.get('countries', []))
        new_countries = set(new_data.get('countries', []))
        
        added_countries = new_countries - old_countries
        for country in added_countries:
            differences.append({
                'field': 'country',
                'type': 'add',
                'value': country,
                'description': f"新增国家/地区支持: {country}"
            })
        
        removed_countries = old_countries - new_countries
        for country in removed_countries:
            differences.append({
                'field': 'country',
                'type': 'remove',
                'value': country,
                'description': f"移除国家/地区支持: {country}"
            })
        
        # 对比游戏支持
        old_games = set(old_data.get('games', []))
        new_games = set(new_data.get('games', []))
        
        added_games = new_games - old_games
        for game in added_games:
            differences.append({
                'field': 'game',
                'type': 'add',
                'value': game,
                'description': f"新增游戏支持: {game}"
            })
        
        removed_games = old_games - new_games
        for game in removed_games:
            differences.append({
                'field': 'game',
                'type': 'remove',
                'value': game,
                'description': f"移除游戏支持: {game}"
            })
            
        return differences
        
    def _compare_sku_prices(self, old_sku_prices: List[Dict], 
                           new_sku_prices: List[Dict]) -> List[Dict[str, Any]]:
        """
        对比SKU级别的价格变化
        
        Returns:
            SKU差异列表，包括：
            - 新增SKU
            - 移除SKU
            - SKU价格变化
        """
        differences = []
        
        # 构建SKU字典（以sku_id为键）
        old_skus = {s['sku_id']: s for s in old_sku_prices if s.get('sku_id')}
        new_skus = {s['sku_id']: s for s in new_sku_prices if s.get('sku_id')}
        
        # 1. 检测新增SKU
        for sku_id, sku in new_skus.items():
            if sku_id not in old_skus:
                differences.append({
                    'field': 'sku',
                    'type': 'add',
                    'value': sku,
                    'description': f"新增SKU: {sku['sku_name']} ({sku['currency']}{sku['price']})"
                })
        
        # 2. 检测移除SKU
        for sku_id, sku in old_skus.items():
            if sku_id not in new_skus:
                differences.append({
                    'field': 'sku',
                    'type': 'remove',
                    'value': sku,
                    'description': f"移除SKU: {sku['sku_name']} ({sku['currency']}{sku['price']})"
                })
        
        # 3. 检测价格变化
        for sku_id, new_sku in new_skus.items():
            if sku_id in old_skus:
                old_sku = old_skus[sku_id]
                old_price = float(old_sku['price'])
                new_price = float(new_sku['price'])
                
                if abs(old_price - new_price) > 0.01:  # 价格变化超过0.01才记录
                    change_pct = ((new_price - old_price) / old_price) * 100
                    direction = "上涨" if change_pct > 0 else "下降"
                    
                    differences.append({
                        'field': 'sku_price',
                        'type': 'change',
                        'value': new_sku,
                        'old_value': old_sku,
                        'description': f"SKU价格{direction}: {new_sku['sku_name']} {old_sku['currency']}{old_price} → {new_sku['currency']}{new_price} ({change_pct:+.1f}%)",
                        'change_pct': change_pct
                    })
        
        return differences
        
    def analyze_page_changes(self, site_name: str, page_type: str, 
                             today_str: str, page_identifier: str = None) -> Optional[Dict[str, Any]]:
        """
        分析单个页面的变化
        
        Args:
            site_name: 站点名称
            page_type: 页面类型
            today_str: 今日日期
            page_identifier: 页面唯一标识（如URL文件名部分），用于区分同类型的不同页面
        
        Returns:
            变化结果，如果无昨日数据返回None
        """
        yesterday_str = self.get_yesterday_date(today_str)
        
        # 加载昨日数据 - 使用页面标识符精确匹配
        old_data = self.load_snapshot_data_by_identifier(
            site_name, page_type, yesterday_str, page_identifier
        )
        if not old_data:
            logger.info(f"无昨日数据: {site_name}/{page_type}/{page_identifier}")
            return None
            
        # 加载今日数据
        new_data = self.load_snapshot_data_by_identifier(
            site_name, page_type, today_str, page_identifier
        )
        if not new_data:
            logger.warning(f"无今日数据: {site_name}/{page_type}/{page_identifier}")
            return None
            
        # 对比文本
        text_changes = self.compare_text(
            old_data.get('text', ''),
            new_data.get('text', ''),
            new_data.get('url', '')
        )
        
        # 加载并对比结构化数据
        from src.parser.data_extractor import DataExtractor
        extractor = DataExtractor()
        
        old_structured = extractor.extract(
            old_data.get('html', ''),
            old_data.get('text', ''),
            old_data.get('url', '')
        )
        new_structured = extractor.extract(
            new_data.get('html', ''),
            new_data.get('text', ''),
            new_data.get('url', '')
        )
        
        structured_changes = self.compare_structured_data(old_structured, new_structured)
        
        # 生成变化描述（整合文本和结构化变化）
        description = self._generate_change_description_v2(
            site_name, page_type, old_data, new_data, text_changes, structured_changes
        )
        
        # 获取变化上下文（整合文本和结构化变化）
        context = self._generate_change_context_v2(text_changes, structured_changes)
        
        # 判断是否有实质性变化
        has_changes = len(text_changes) > 0 or len(structured_changes) > 0
        
        return {
            'site_name': site_name,
            'page_type': page_type,
            'url': new_data.get('url', ''),
            'title_changed': old_data.get('title') != new_data.get('title'),
            'old_title': old_data.get('title', ''),
            'new_title': new_data.get('title', ''),
            'text_changes': text_changes,
            'structured_changes': structured_changes,
            'has_changes': has_changes,
            'description': description,
            'context': context
        }
        
    def _generate_change_description_v2(self, site_name: str, page_type: str,
                                         old_data: Dict[str, Any], new_data: Dict[str, Any],
                                         text_changes: List[Dict[str, Any]],
                                         structured_changes: List[Dict[str, Any]]) -> str:
        """生成变化描述（业务语言版）"""
        descriptions = []
        url = new_data.get('url', '')
        
        # 标题变化
        old_title = old_data.get('title', '')
        new_title = new_data.get('title', '')
        if old_title != new_title:
            descriptions.append(f"页面标题从 '{old_title[:40]}' 改为 '{new_title[:40]}' ({url})")
        
        # 优先使用结构化变化描述（更有业务价值）
        if structured_changes:
            for change in structured_changes[:3]:  # 最多取3个结构化变化
                desc = change.get('description', '')
                if desc:
                    descriptions.append(desc)
        
        # 文本变化（仅当没有结构化变化时，或作为补充）
        if text_changes and len(descriptions) < 3:
            add_contents = [c for c in text_changes if c['type'] == 'add' and len(c['content']) > 10]
            remove_contents = [c for c in text_changes if c['type'] == 'remove' and len(c['content']) > 10]
            
            # 分析内容特征，使用更准确的描述
            for change in add_contents[:1]:
                desc = self._analyze_content_change(change['content'], 'add')
                if desc:
                    descriptions.append(desc)
            
            for change in remove_contents[:1]:
                desc = self._analyze_content_change(change['content'], 'remove')
                if desc:
                    descriptions.append(desc)
        
        if descriptions:
            return "; ".join(descriptions)
        return "页面内容有调整"
        
    def _analyze_content_change(self, content: str, change_type: str) -> str:
        """分析内容变化特征，返回更准确的描述"""
        content_lower = content.lower()
        prefix = "新增" if change_type == 'add' else "移除"
        
        # 游戏相关
        game_keywords = ['genshin', 'honkai', 'star rail', 'zenless', 'wuthering', 'pubg']
        if any(k in content_lower for k in game_keywords):
            if 'self top-up' in content_lower or 'uid' in content_lower:
                return f"{prefix}充值方式: {content[:40]}"
            return f"{prefix}游戏产品: {content[:40]}"
        
        # 支付方式
        payment_keywords = ['paypal', 'visa', 'mastercard', 'credit card', 'alipay', 'wechat']
        if any(k in content_lower for k in payment_keywords):
            return f"{prefix}支付方式: {content[:40]}"
        
        # 价格/金额
        if '$' in content or '€' in content or '£' in content or 'usd' in content_lower:
            return f"{prefix}价格信息: {content[:40]}"
        
        # 优惠/折扣
        discount_keywords = ['off', 'discount', 'coupon', 'promo', 'sale', '%']
        if any(k in content_lower for k in discount_keywords):
            return f"{prefix}优惠信息: {content[:40]}"
        
        # 时效/配送
        delivery_keywords = ['delivery', 'within', 'minutes', 'hours', 'instant', 'fast']
        if any(k in content_lower for k in delivery_keywords):
            return f"{prefix}时效说明: {content[:40]}"
        
        # 评价/评论 - 不再报告，因为评价数据统一从 Trustpilot 获取
        review_keywords = ['review', 'rating', 'star', 'feedback', 'comment']
        if any(k in content_lower for k in review_keywords):
            return None  # 忽略评价数据变化
        
        # 客服/支持
        support_keywords = ['support', 'help', 'contact', 'service', 'faq']
        if any(k in content_lower for k in support_keywords):
            return f"{prefix}客服信息: {content[:40]}"
        
        # 国家/地区
        country_keywords = ['usa', 'uk', 'europe', 'asia', 'global', 'region', 'server']
        if any(k in content_lower for k in country_keywords):
            return f"{prefix}地区支持: {content[:40]}"
        
        # 库存状态
        stock_keywords = ['in stock', 'out of stock', 'available', 'sold out']
        if any(k in content_lower for k in stock_keywords):
            return f"{prefix}库存状态: {content[:40]}"
        
        # 活动/公告
        event_keywords = ['event', 'announcement', 'news', 'update', 'version']
        if any(k in content_lower for k in event_keywords):
            return f"{prefix}活动公告: {content[:40]}"
        
        # 页面元素（按钮、链接等）
        if len(content) < 30 and not any(c.isdigit() for c in content):
            return f"{prefix}导航元素: {content[:40]}"
        
        # 默认描述
        return f"{prefix}页面内容: {content[:40]}"
        
    def _generate_change_context_v2(self, text_changes: List[Dict[str, Any]],
                                     structured_changes: List[Dict[str, Any]]) -> str:
        """生成变化上下文摘录（整合结构化数据）"""
        contexts = []
        
        # 优先使用结构化变化作为上下文
        if structured_changes:
            for change in structured_changes[:3]:
                field = change.get('field', '')
                value = change.get('value', '')
                desc = change.get('description', '')
                
                if field == 'price' and isinstance(value, dict):
                    contexts.append(f"价格: {value.get('raw', '')}")
                elif field == 'discount':
                    contexts.append(f"折扣: {value}")
                elif field == 'payment':
                    contexts.append(f"支付: {value}")
                elif field == 'delivery':
                    contexts.append(f"时效: {value}")
                elif field == 'promotion':
                    contexts.append(f"促销: {value}")
                elif desc:
                    contexts.append(desc[:80])
        
        # 补充文本变化
        if len(contexts) < 3 and text_changes:
            for change in text_changes[:3 - len(contexts)]:
                content = change.get('content', '').strip()
                if content and len(content) > 10:
                    prefix = "+" if change['type'] == 'add' else "-"
                    contexts.append(f"{prefix} {content[:60]}")
        
        return " | ".join(contexts) if contexts else ""
        
    def analyze_new_games(self, crawl_results: List[Dict[str, Any]], 
                          today_str: str) -> List[Dict[str, Any]]:
        """
        分析各站点新增的游戏（基于游戏列表页商品数量变化）
        
        监控以下页面：
        - LDShop: /catalog/all (Found results:XXX) - 支持多页合并
        - LootBar: /top-up/ (Total XXX items)
        - TOPUPlive: 不监控
        
        Returns:
            新增游戏列表
        """
        new_games = []
        yesterday_str = self.get_yesterday_date(today_str)
        
        # 导入数据提取器
        from src.parser.data_extractor import DataExtractor
        extractor = DataExtractor()
        
        for site_result in crawl_results:
            site_name = site_result['site_name']
            
            # 跳过 TOPUPlive 的监控
            if site_name == 'TOPUPlive':
                continue
            
            # 收集今日所有游戏列表页数据（支持多页）
            today_catalog_pages = []
            for page in site_result.get('pages', []):
                if not page.get('success'):
                    continue
                url = page.get('url', '')
                # 判断是否为游戏列表页
                if self._is_game_catalog_page(url):
                    today_catalog_pages.append(page)
            
            if not today_catalog_pages:
                logger.debug(f"{site_name} 今日无游戏列表页数据")
                continue
            
            # 合并多页数据
            today_data = self._merge_catalog_pages_data(today_catalog_pages, extractor, site_name)
            
            if not today_data or today_data.get('total_items') is None:
                logger.debug(f"{site_name} 今日游戏列表页数据不完整")
                continue
            
            # 加载昨日的游戏列表页数据（同样合并多页）
            yesterday_data = self._load_yesterday_catalog_data_merged(
                site_name, yesterday_str, extractor
            )
            
            # 对比商品数量
            today_count = today_data.get('total_items', 0)
            yesterday_count = yesterday_data.get('total_items', 0) if yesterday_data else 0
            today_games = set(today_data.get('games_list', []))
            yesterday_games = set(yesterday_data.get('games_list', [])) if yesterday_data else set()
            
            logger.info(f"{site_name} 游戏列表页对比: 昨日 {yesterday_count} 个商品 / 今日 {today_count} 个商品")
            
            # 如果商品数量增加，找出新增的游戏
            if today_count > yesterday_count or today_games != yesterday_games:
                added_games = today_games - yesterday_games
                
                for game in added_games:
                    new_games.append({
                        'site_name': site_name,
                        'game': game,
                        'type': 'new_game',
                        'description': f'{site_name} 新增游戏: {game}',
                        'today_count': today_count,
                        'yesterday_count': yesterday_count,
                        'catalog_url': today_data.get('catalog_url', '')
                    })
                
                # 即使没有识别出具体游戏名称，但数量增加了，尝试从页面提取可能的新增商品
                if not added_games and today_count > yesterday_count:
                    # 尝试提取可能的新增商品名称
                    potential_new_items = self._extract_potential_new_items(
                        today_catalog_pages, yesterday_data, extractor, site_name
                    )
                    
                    if potential_new_items:
                        for item_name in potential_new_items[:5]:  # 最多显示5个
                            new_games.append({
                                'site_name': site_name,
                                'game': item_name,
                                'type': 'new_game_detected',
                                'description': f'{site_name} 新增游戏: {item_name}',
                                'today_count': today_count,
                                'yesterday_count': yesterday_count,
                                'catalog_url': today_data.get('catalog_url', '')
                            })
                    else:
                        # 实在无法识别，记录为"待确认的新增商品"
                        new_games.append({
                            'site_name': site_name,
                            'game': f'新增商品({today_count - yesterday_count}个)',
                            'type': 'new_game_detected',
                            'description': f'{site_name} 商品数量增加: {yesterday_count} → {today_count} 个（建议人工查看）',
                            'today_count': today_count,
                            'yesterday_count': yesterday_count,
                            'catalog_url': today_data.get('catalog_url', '')
                        })
        
        return new_games
    
    def _extract_potential_new_items(self, today_pages: List[Dict[str, Any]], 
                                       yesterday_data: Optional[Dict[str, Any]],
                                       extractor: Any, site_name: str) -> List[str]:
        """
        从今日页面提取可能的新增商品名称
        
        当预定义的游戏关键词无法匹配时，尝试从页面结构中提取商品名称
        """
        potential_items = []
        
        try:
            # 收集今日所有商品名称
            today_items = set()
            for page in today_pages:
                snapshot_path = page.get('snapshot_path', '')
                items = self._extract_item_names_from_snapshot(snapshot_path, site_name)
                today_items.update(items)
            
            # 收集昨日商品名称
            yesterday_items = set()
            if yesterday_data:
                # 从昨日的快照重新提取商品名称
                yesterday_str = self.get_yesterday_date(
                    datetime.now().strftime('%Y-%m-%d')
                )
                yesterday_pages = self._get_yesterday_catalog_pages(site_name, yesterday_str)
                for page in yesterday_pages:
                    snapshot_path = page.get('snapshot_path', '')
                    items = self._extract_item_names_from_snapshot(snapshot_path, site_name)
                    yesterday_items.update(items)
            
            # 找出今日有但昨日没有的商品
            new_items = today_items - yesterday_items
            
            # 过滤掉太短的名称和常见噪声词
            filtered_items = []
            noise_words = ['home', 'cart', 'login', 'register', 'search', 'menu', 'more', 'all', 'view']
            for item in new_items:
                if len(item) >= 3 and len(item) <= 100:
                    if not any(noise.lower() in item.lower() for noise in noise_words):
                        filtered_items.append(item)
            
            potential_items = sorted(filtered_items)
            
        except Exception as e:
            logger.debug(f"提取可能的新增商品失败: {e}")
        
        return potential_items
    
    def _extract_item_names_from_snapshot(self, snapshot_path: str, site_name: str) -> Set[str]:
        """从快照文件中提取商品名称"""
        items = set()
        
        try:
            html_path = f"{snapshot_path}.html"
            if not os.path.exists(html_path):
                return items
            
            with open(html_path, 'r', encoding='utf-8') as f:
                html = f.read()
            
            soup = BeautifulSoup(html, 'lxml')
            
            # 针对不同站点使用不同的选择器
            selectors = []
            if 'ldshop' in site_name.lower():
                selectors = [
                    '.product-item .product-name',
                    '.product-item h3',
                    '.product-item .name',
                    '[class*="product"] [class*="name"]',
                    '.game-item .game-name',
                ]
            elif 'lootbar' in site_name.lower():
                selectors = [
                    '.game-card .game-name',
                    '.game-item .name',
                    '[class*="game"] [class*="name"]',
                    '.product-card h3',
                    '.item-title',
                ]
            else:
                # 通用选择器
                selectors = [
                    '.product-item .name',
                    '.game-item .name',
                    '.product-card h3',
                    '.product-card h4',
                    '[class*="item"] [class*="name"]',
                    '[class*="card"] [class*="title"]',
                ]
            
            for selector in selectors:
                elements = soup.select(selector)
                for elem in elements:
                    text = elem.get_text(strip=True)
                    if text and len(text) >= 3:
                        items.add(text)
            
            # 如果从结构化选择器没提取到，尝试从链接文本提取
            if not items:
                links = soup.select('a[href*="game"], a[href*="product"]')
                for link in links:
                    text = link.get_text(strip=True)
                    # 过滤掉导航类文本
                    if text and len(text) >= 3 and len(text) <= 80:
                        if not any(nav in text.lower() for nav in ['home', 'cart', 'login', 'menu']):
                            items.add(text)
            
        except Exception as e:
            logger.debug(f"从快照提取商品名称失败: {e}")
        
        return items
    
    def _get_yesterday_catalog_pages(self, site_name: str, yesterday_str: str) -> List[Dict[str, Any]]:
        """获取昨日的游戏列表页快照信息"""
        pages = []
        
        try:
            snapshot_dir = os.path.join(
                self.paths_config.get('snapshot_base', './data/snapshots'),
                yesterday_str,
                site_name
            )
            
            if not os.path.exists(snapshot_dir):
                return pages
            
            for filename in os.listdir(snapshot_dir):
                if not filename.startswith('product_') or not filename.endswith('.json'):
                    continue
                
                if 'catalog' in filename or 'top-up' in filename:
                    meta_path = os.path.join(snapshot_dir, filename)
                    try:
                        with open(meta_path, 'r', encoding='utf-8') as f:
                            meta = json.load(f)
                        
                        url = meta.get('url', '')
                        if self._is_game_catalog_page(url):
                            pages.append({
                                'url': url,
                                'snapshot_path': meta_path.replace('.json', '')
                            })
                    except Exception:
                        continue
                        
        except Exception as e:
            logger.debug(f"获取昨日目录页失败: {e}")
        
        return pages
    
    def _merge_catalog_pages_data(self, pages: List[Dict[str, Any]], extractor: Any, 
                                   site_name: str) -> Optional[Dict[str, Any]]:
        """
        合并多页游戏列表页数据
        
        Args:
            pages: 游戏列表页数据列表
            extractor: 数据提取器
            site_name: 站点名称
            
        Returns:
            合并后的数据
        """
        if not pages:
            return None
        
        # 按页码排序（LDShop的翻页URL包含page=N）
        sorted_pages = sorted(pages, key=lambda p: self._extract_page_number(p.get('url', '')))
        
        merged_data = {
            'total_items': None,
            'games_list': [],
            'is_catalog_page': True,
            'catalog_url': sorted_pages[0].get('url', '') if sorted_pages else ''
        }
        
        all_games = set()
        
        for page in sorted_pages:
            url = page.get('url', '')
            snapshot_path = page.get('snapshot_path', '')
            page_data = self._load_catalog_data(snapshot_path, extractor, url)
            
            if page_data:
                # 使用第一页的商品总数（LDShop每页都显示总数）
                if merged_data['total_items'] is None and page_data.get('total_items'):
                    merged_data['total_items'] = page_data['total_items']
                
                # 合并游戏列表
                all_games.update(page_data.get('games_list', []))
        
        merged_data['games_list'] = sorted(list(all_games))
        return merged_data
    
    def _extract_page_number(self, url: str) -> int:
        """从URL中提取页码"""
        import re
        match = re.search(r'[?&]page=(\d+)', url)
        if match:
            return int(match.group(1))
        return 0
    
    def _load_yesterday_catalog_data_merged(self, site_name: str, yesterday_str: str, 
                                            extractor: Any) -> Optional[Dict[str, Any]]:
        """加载昨日的游戏列表页数据（合并多页）"""
        try:
            # 构建昨日快照目录路径
            snapshot_dir = os.path.join(
                self.paths_config.get('snapshot_base', './data/snapshots'),
                yesterday_str,
                site_name
            )
            
            if not os.path.exists(snapshot_dir):
                return None
            
            # 查找所有游戏列表页的快照
            catalog_pages = []
            for filename in os.listdir(snapshot_dir):
                if not filename.startswith('product_') or not filename.endswith('.json'):
                    continue
                
                # 检查是否为游戏列表页
                if 'catalog' in filename or 'top-up' in filename:
                    meta_path = os.path.join(snapshot_dir, filename)
                    try:
                        with open(meta_path, 'r', encoding='utf-8') as f:
                            meta = json.load(f)
                        
                        url = meta.get('url', '')
                        if self._is_game_catalog_page(url):
                            catalog_pages.append({
                                'url': url,
                                'snapshot_path': meta_path.replace('.json', '')
                            })
                    except Exception:
                        continue
            
            if not catalog_pages:
                return None
            
            # 合并多页数据
            return self._merge_catalog_pages_data(catalog_pages, extractor, site_name)
            
        except Exception as e:
            logger.error(f"加载昨日游戏列表页数据失败: {e}")
            return None
    
    def _is_game_catalog_page(self, url: str) -> bool:
        """判断URL是否为游戏列表页"""
        import re
        catalog_patterns = [
            r'/catalog/all',
            r'/top-up/?$',
            r'/game/game-mobile/',
            r'/game/?$'
        ]
        return any(re.search(pattern, url, re.IGNORECASE) for pattern in catalog_patterns)
    
    def _load_catalog_data(self, snapshot_path: str, extractor: Any, url: str) -> Optional[Dict[str, Any]]:
        """从快照加载游戏列表页数据"""
        try:
            html_path = f"{snapshot_path}.html"
            text_path = f"{snapshot_path}.txt"
            
            html = ''
            text = ''
            
            try:
                with open(html_path, 'r', encoding='utf-8') as f:
                    html = f.read()
            except FileNotFoundError:
                pass
            
            try:
                with open(text_path, 'r', encoding='utf-8') as f:
                    text = f.read()
            except FileNotFoundError:
                pass
            
            if not html and not text:
                return None
            
            return extractor.extract_game_catalog_info(html, text, url)
        except Exception as e:
            logger.error(f"加载游戏列表页数据失败: {e}")
            return None
    
    # 修改：移除了以下未使用的方法：
    # - _load_yesterday_catalog_data: 已被 _load_yesterday_catalog_data_merged 替代
    # - _extract_game_from_page: 从未被调用
    # - _extract_games_from_text: 从未被调用，游戏提取逻辑在 data_extractor.py 中实现

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
        seen_pages = set()  # 用于去重
        
        for site_result in crawl_results:
            site_name = site_result['site_name']
            
            for page in site_result.get('pages', []):
                if not page.get('success'):
                    continue
                    
                page_type = page['type']
                url = page.get('url', '')
                
                # 生成页面唯一标识
                page_key = f"{site_name}_{page_type}_{url}"
                if page_key in seen_pages:
                    continue
                seen_pages.add(page_key)
                
                # 从URL提取标识符（用于匹配快照文件）
                page_identifier = self._extract_identifier_from_url(url)
                
                # 分析变化
                change = self.analyze_page_changes(
                    site_name, page_type, today_str, page_identifier
                )
                if change and change.get('has_changes'):
                    all_changes.append(change)
                    
        return all_changes
        
    def _extract_identifier_from_url(self, url: str) -> str:
        """从URL提取页面标识符"""
        if not url:
            return ""
        
        # 移除协议和域名，保留路径
        import re
        # 移除 http:// 或 https://
        url = re.sub(r'^https?://', '', url)
        # 移除域名部分（取第一个/之后的内容）
        if '/' in url:
            path = url.split('/', 1)[1]
            # 清理特殊字符，用于匹配文件名
            path = re.sub(r'[^\w\-_.]', '_', path)
            return path
        return ""
