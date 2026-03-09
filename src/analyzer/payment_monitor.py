"""
支付方式监控模块
追踪竞品支付方式的新增、下架、促销变化
"""

import os
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from collections import defaultdict

logger = logging.getLogger(__name__)


class PaymentMonitor:
    """支付方式监控器"""
    
    # 支付方式分类
    PAYMENT_CATEGORIES = {
        'credit_card': {
            'name': '信用卡',
            'methods': ['visa', 'mastercard', 'amex', 'american express', 'discover', 'jcb']
        },
        'digital_wallet': {
            'name': '数字钱包',
            'methods': ['paypal', 'alipay', 'wechat pay', 'wechatpay', 'google pay', 'apple pay']
        },
        'bank_transfer': {
            'name': '银行转账',
            'methods': ['bank transfer', 'wire transfer', 'ach', 'sepa', 'local bank']
        },
        'crypto': {
            'name': '加密货币',
            'methods': ['bitcoin', 'ethereum', 'usdt', 'tether', 'crypto', 'cryptocurrency']
        },
        'local_payment': {
            'name': '本地支付',
            'methods': [
                'gcash', 'grabpay', 'dana', 'ovo', 'gopay', 'shopeepay',
                'paytm', 'phonepe', 'upi', 'kakao pay', 'line pay',
                'paysafecard', 'sofort', 'ideal', 'giropay', 'bancontact',
                'interac', 'pix', 'mercado pago', 'boleto'
            ]
        },
        'prepaid': {
            'name': '预付卡',
            'methods': ['paysafecard', 'gift card', 'prepaid card']
        }
    }
    
    # 支付相关关键词
    PAYMENT_KEYWORDS = {
        'available': ['available', 'accepted', 'supported', 'we accept', '支持'],
        'unavailable': ['unavailable', 'temporarily disabled', 'maintenance', '暂停', '维护'],
        'promo': ['cashback', 'rebate', 'bonus', 'discount', 'free fee', 'no fee', '返现', '优惠']
    }
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.paths_config = config.get('paths', {})
        
    def analyze(self, parsed_data: Dict[str, Any], date_str: str) -> Dict[str, Any]:
        """
        分析支付方式覆盖情况
        
        Args:
            parsed_data: 解析后的数据 {site_name: {page_type: data}}
            date_str: 日期字符串
            
        Returns:
            支付方式分析结果
        """
        results = {
            'date': date_str,
            'payment_coverage': {},
            'payment_changes': [],
            'regional_coverage': {},
            'promotional_payments': {},
            'competitive_gaps': []
        }
        
        # 分析每个站点的支付方式（排除Trustpilot）
        for site_name, pages in parsed_data.items():
            # 跳过第三方评价平台
            if site_name.lower() in ['trustpilot']:
                continue
            site_payments = self._analyze_site_payments(site_name, pages)
            results['payment_coverage'][site_name] = site_payments
        
        # 对比昨日数据检测变化
        results['payment_changes'] = self._detect_payment_changes(
            results['payment_coverage'], date_str
        )
        
        # 分析区域覆盖
        results['regional_coverage'] = self._analyze_regional_coverage(
            results['payment_coverage']
        )
        
        # 提取支付促销
        results['promotional_payments'] = self._extract_payment_promotions(
            parsed_data
        )
        
        # 识别竞争差距
        results['competitive_gaps'] = self._identify_competitive_gaps(
            results['payment_coverage']
        )
        
        return results
    
    def _analyze_site_payments(self, site_name: str, pages: Dict[str, Any]) -> Dict[str, Any]:
        """分析单个站点的支付方式"""
        all_payments = set()
        payment_by_category = defaultdict(list)
        payment_with_promo = []
        
        for page_key, data in pages.items():
            # 从支付方式字段提取
            payments = data.get('payments', [])
            all_payments.update(payments)
            
            # 从支付促销字段提取
            payment_promos = data.get('payment_promos', [])
            payment_with_promo.extend(payment_promos)
            
            # 从文本中提取更多支付方式
            text = str(data)
            text_lower = text.lower()
            
            for category, info in self.PAYMENT_CATEGORIES.items():
                for method in info['methods']:
                    if method in text_lower and method not in all_payments:
                        all_payments.add(method)
                        payment_by_category[category].append(method)
        
        # 分类整理
        categorized = {}
        for category, info in self.PAYMENT_CATEGORIES.items():
            found = [m for m in info['methods'] if any(m in p.lower() for p in all_payments)]
            if found:
                categorized[info['name']] = found
        
        return {
            'total_methods': len(all_payments),
            'methods': sorted(list(all_payments)),
            'by_category': dict(categorized),
            'promotional_count': len(payment_with_promo),
            'promotions': payment_with_promo[:5]  # 最多5条
        }
    
    def _detect_payment_changes(self, current_coverage: Dict[str, Any], 
                                 date_str: str) -> List[Dict[str, Any]]:
        """检测支付方式变化"""
        changes = []
        
        # 加载昨日数据
        yesterday_data = self._load_yesterday_payment_data(date_str)
        if not yesterday_data:
            return changes
        
        for site_name, current in current_coverage.items():
            yesterday = yesterday_data.get(site_name, {})
            
            current_methods = set(current.get('methods', []))
            yesterday_methods = set(yesterday.get('methods', []))
            
            # 新增支付方式
            added = current_methods - yesterday_methods
            for method in added:
                changes.append({
                    'site': site_name,
                    'change_type': 'added',
                    'payment_method': method,
                    'description': f'{site_name} 新增支付方式: {method}'
                })
            
            # 下架支付方式
            removed = yesterday_methods - current_methods
            for method in removed:
                changes.append({
                    'site': site_name,
                    'change_type': 'removed',
                    'payment_method': method,
                    'description': f'{site_name} 下架支付方式: {method}'
                })
        
        return changes
    
    def _analyze_regional_coverage(self, payment_coverage: Dict[str, Any]) -> Dict[str, Any]:
        """分析区域支付覆盖"""
        regional_mapping = {
            '东南亚': ['gcash', 'grabpay', 'dana', 'ovo', 'gopay', 'shopeepay'],
            '南亚': ['paytm', 'phonepe', 'upi'],
            '东亚': ['alipay', 'wechat pay', 'kakao pay', 'line pay'],
            '欧洲': ['sofort', 'ideal', 'giropay', 'bancontact', 'sepa'],
            '北美': ['interac'],
            '拉美': ['pix', 'mercado pago', 'boleto'],
        }
        
        regional_coverage = {}
        
        for region, methods in regional_mapping.items():
            coverage_by_site = {}
            for site_name, data in payment_coverage.items():
                site_methods = [m.lower() for m in data.get('methods', [])]
                covered = [m for m in methods if any(m in sm for sm in site_methods)]
                coverage_by_site[site_name] = {
                    'covered': covered,
                    'coverage_rate': len(covered) / len(methods) if methods else 0
                }
            
            regional_coverage[region] = coverage_by_site
        
        return regional_coverage
    
    def _extract_payment_promotions(self, parsed_data: Dict[str, Any]) -> Dict[str, List[str]]:
        """提取支付促销活动"""
        promos_by_site = {}
        
        for site_name, pages in parsed_data.items():
            promos = []
            for page_key, data in pages.items():
                payment_promos = data.get('payment_promos', [])
                promos.extend(payment_promos)
            
            if promos:
                promos_by_site[site_name] = promos[:5]
        
        return promos_by_site
    
    def _identify_competitive_gaps(self, payment_coverage: Dict[str, Any]) -> List[Dict[str, Any]]:
        """识别支付方式的竞争差距"""
        gaps = []
        
        # 获取所有站点
        sites = list(payment_coverage.keys())
        if len(sites) < 2:
            return gaps
        
        # 找出所有支付方式
        all_methods = set()
        for data in payment_coverage.values():
            all_methods.update(data.get('methods', []))
        
        # 检查每个支付方式的覆盖情况
        for method in all_methods:
            covered_sites = []
            for site_name, data in payment_coverage.items():
                site_methods = [m.lower() for m in data.get('methods', [])]
                if any(method.lower() in sm for sm in site_methods):
                    covered_sites.append(site_name)
            
            # 如果只有部分站点支持
            if 0 < len(covered_sites) < len(sites):
                missing_sites = [s for s in sites if s not in covered_sites]
                gaps.append({
                    'payment_method': method,
                    'covered_by': covered_sites,
                    'missing_in': missing_sites,
                    'description': f'{method}: {", ".join(covered_sites)} 已支持，'
                                   f'{", ".join(missing_sites)} 尚未支持'
                })
        
        return gaps
    
    def _load_yesterday_payment_data(self, date_str: str) -> Dict[str, Any]:
        """加载昨日的支付数据"""
        from datetime import datetime, timedelta
        
        try:
            current_date = datetime.strptime(date_str, '%Y-%m-%d')
            yesterday = current_date - timedelta(days=1)
            yesterday_str = yesterday.strftime('%Y-%m-%d')
            
            parsed_base = self.paths_config.get('parsed_base', './data/parsed')
            yesterday_dir = os.path.join(parsed_base, yesterday_str)
            
            if not os.path.exists(yesterday_dir):
                return {}
            
            # 加载昨日的解析数据
            yesterday_data = {}
            for site_name in os.listdir(yesterday_dir):
                site_dir = os.path.join(yesterday_dir, site_name)
                if not os.path.isdir(site_dir):
                    continue
                
                yesterday_data[site_name] = {'methods': []}
                for filename in os.listdir(site_dir):
                    if not filename.endswith('.json'):
                        continue
                    
                    filepath = os.path.join(site_dir, filename)
                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            yesterday_data[site_name]['methods'].extend(
                                data.get('payments', [])
                            )
                    except Exception:
                        continue
            
            return yesterday_data
            
        except Exception as e:
            logger.warning(f'加载昨日支付数据失败: {e}')
            return {}
    
    def export_to_csv(self, payment_results: Dict[str, Any], output_path: str) -> str:
        """导出支付数据到CSV"""
        import csv
        
        with open(output_path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            
            # 表头
            writer.writerow([
                '站点', '支付方式总数', '信用卡', '数字钱包', '银行转账', 
                '加密货币', '本地支付', '促销数量'
            ])
            
            # 数据
            for site_name, data in payment_results.get('payment_coverage', {}).items():
                by_category = data.get('by_category', {})
                writer.writerow([
                    site_name,
                    data.get('total_methods', 0),
                    ', '.join(by_category.get('信用卡', [])),
                    ', '.join(by_category.get('数字钱包', [])),
                    ', '.join(by_category.get('银行转账', [])),
                    ', '.join(by_category.get('加密货币', [])),
                    ', '.join(by_category.get('本地支付', [])),
                    data.get('promotional_count', 0)
                ])
        
        logger.info(f'支付数据已导出: {output_path}')
        return output_path
    
    def generate_payment_summary(self, payment_results: Dict[str, Any]) -> str:
        """生成支付方式摘要"""
        lines = []
        
        coverage = payment_results.get('payment_coverage', {})
        changes = payment_results.get('payment_changes', [])
        gaps = payment_results.get('competitive_gaps', [])
        
        # 支付方式覆盖概览
        lines.append('## 支付方式覆盖概览')
        for site_name, data in coverage.items():
            lines.append(f"- **{site_name}**: {data.get('total_methods', 0)} 种支付方式")
            for cat_name, methods in data.get('by_category', {}).items():
                lines.append(f"  - {cat_name}: {', '.join(methods[:3])}")
        
        # 支付方式变化
        if changes:
            lines.append('\n## 支付方式变化')
            for change in changes:
                icon = '✅' if change['change_type'] == 'added' else '❌'
                lines.append(f"- {icon} {change['description']}")
        
        # 竞争差距
        if gaps:
            lines.append('\n## 支付覆盖差距')
            for gap in gaps[:5]:  # 最多显示5条
                lines.append(f"- {gap['description']}")
        
        return '\n'.join(lines)
