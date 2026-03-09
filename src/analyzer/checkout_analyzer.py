"""
结算链路摩擦分析模块
模拟用户下单流程，检测转化路径中的摩擦点
"""

import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class CheckoutStep:
    """结算步骤"""
    name: str
    required: bool
    has_input: bool
    description: str = ""


@dataclass
class CheckoutFriction:
    """结算摩擦点"""
    total_steps: int
    required_login: bool
    guest_checkout_available: bool
    required_fields: List[str] = field(default_factory=list)
    payment_options: List[str] = field(default_factory=list)
    error_messages: List[str] = field(default_factory=list)
    steps_detail: List[CheckoutStep] = field(default_factory=list)
    friction_score: int = 0  # 0-100，分数越高摩擦越大
    recommendations: List[str] = field(default_factory=list)


class CheckoutAnalyzer:
    """结算链路分析器"""
    
    # 结算相关关键词
    CHECKOUT_KEYWORDS = {
        'cart': ['cart', 'basket', 'bag', '购物车'],
        'login': ['login', 'sign in', 'register', 'sign up', '登录', '注册'],
        'shipping': ['shipping', 'delivery address', '收货地址'],
        'payment': ['payment', 'checkout', 'billing', '支付', '结算'],
        'review': ['review order', 'order summary', '确认订单'],
        'confirmation': ['confirmation', 'thank you', '订单成功']
    }
    
    # 表单字段关键词
    FORM_FIELD_KEYWORDS = {
        'email': ['email', 'e-mail', '邮箱'],
        'phone': ['phone', 'mobile', 'tel', '电话', '手机'],
        'password': ['password', '密码'],
        'name': ['name', '姓名'],
        'address': ['address', 'street', '地址'],
        'country': ['country', '国家'],
        'city': ['city', '城市'],
        'postcode': ['postcode', 'zip', '邮编'],
    }
    
    # 支付方式关键词
    PAYMENT_METHODS = [
        'credit card', 'visa', 'mastercard', 'amex',
        'paypal', 'alipay', 'wechat pay', 'unionpay',
        'bank transfer', 'crypto', 'bitcoin',
        'paysafecard', 'sofort', 'ideal', 'giropay',
        'gcash', 'grabpay', 'dana', 'ovo'
    ]
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        
    def analyze(self, html: str, text: str, url: str) -> Dict[str, Any]:
        """
        分析结算链路摩擦
        
        Args:
            html: 页面HTML
            text: 页面纯文本
            url: 页面URL
            
        Returns:
            结算摩擦分析结果
        """
        text_lower = text.lower()
        
        # 检测当前页面类型
        page_type = self._detect_page_type(text_lower)
        
        # 分析结算步骤
        steps = self._analyze_checkout_steps(text_lower)
        
        # 检测是否强制登录
        requires_login = self._detect_required_login(text_lower, html.lower())
        guest_available = self._detect_guest_checkout(text_lower)
        
        # 提取必填字段
        required_fields = self._extract_required_fields(text_lower, html.lower())
        
        # 提取支付方式
        payment_methods = self._extract_payment_methods(text_lower)
        
        # 提取错误提示
        error_messages = self._extract_error_messages(text_lower)
        
        # 计算摩擦分数
        friction_score = self._calculate_friction_score(
            len(steps), requires_login, guest_available, 
            len(required_fields), len(error_messages)
        )
        
        # 生成优化建议
        recommendations = self._generate_recommendations(
            requires_login, guest_available, required_fields, 
            steps, friction_score
        )
        
        return {
            'url': url,
            'page_type': page_type,
            'total_steps': len(steps),
            'requires_login': requires_login,
            'guest_checkout_available': guest_available,
            'required_fields': required_fields,
            'payment_methods': payment_methods,
            'payment_method_count': len(payment_methods),
            'error_messages': error_messages,
            'steps_detail': [self._step_to_dict(s) for s in steps],
            'friction_score': friction_score,
            'friction_level': self._get_friction_level(friction_score),
            'recommendations': recommendations,
            'has_checkout_flow': len(steps) > 0 or 'checkout' in text_lower
        }
    
    def _detect_page_type(self, text: str) -> str:
        """检测页面类型"""
        if any(k in text for k in self.CHECKOUT_KEYWORDS['cart']):
            return 'cart'
        elif any(k in text for k in self.CHECKOUT_KEYWORDS['payment']):
            return 'checkout'
        elif any(k in text for k in self.CHECKOUT_KEYWORDS['confirmation']):
            return 'confirmation'
        elif any(k in text for k in self.CHECKOUT_KEYWORDS['login']):
            return 'login'
        return 'other'
    
    def _analyze_checkout_steps(self, text: str) -> List[CheckoutStep]:
        """分析结算步骤"""
        steps = []
        
        # 检测购物车步骤
        if any(k in text for k in self.CHECKOUT_KEYWORDS['cart']):
            steps.append(CheckoutStep(
                name='购物车',
                required=True,
                has_input=True,
                description='查看商品清单'
            ))
        
        # 检测登录/注册步骤
        if any(k in text for k in self.CHECKOUT_KEYWORDS['login']):
            steps.append(CheckoutStep(
                name='登录/注册',
                required=True,
                has_input=True,
                description='账户验证'
            ))
        
        # 检测配送信息步骤
        if any(k in text for k in self.CHECKOUT_KEYWORDS['shipping']):
            steps.append(CheckoutStep(
                name='配送信息',
                required=True,
                has_input=True,
                description='填写收货地址'
            ))
        
        # 检测支付步骤
        if any(k in text for k in self.CHECKOUT_KEYWORDS['payment']):
            steps.append(CheckoutStep(
                name='支付',
                required=True,
                has_input=True,
                description='选择支付方式'
            ))
        
        # 检测订单确认步骤
        if any(k in text for k in self.CHECKOUT_KEYWORDS['review']):
            steps.append(CheckoutStep(
                name='订单确认',
                required=True,
                has_input=False,
                description='确认订单详情'
            ))
        
        return steps
    
    def _detect_required_login(self, text: str, html: str) -> bool:
        """检测是否强制要求登录"""
        login_required_indicators = [
            'please login', 'login required', 'sign in to continue',
            'must be logged in', 'login to purchase',
            '请先登录', '需要登录', '登录后购买'
        ]
        
        for indicator in login_required_indicators:
            if indicator in text:
                return True
        
        # 检查是否有登录表单但没有游客选项
        has_login_form = 'password' in text and ('login' in text or 'sign in' in text)
        has_guest_option = any(k in text for k in ['guest', 'continue as guest', '游客'])
        
        return has_login_form and not has_guest_option
    
    def _detect_guest_checkout(self, text: str) -> bool:
        """检测是否支持游客下单"""
        guest_keywords = [
            'guest checkout', 'continue as guest', 'checkout as guest',
            'without account', 'no account needed',
            '游客购买', '无需注册', '免登录购买'
        ]
        
        return any(kw in text for kw in guest_keywords)
    
    def _extract_required_fields(self, text: str, html: str) -> List[str]:
        """提取必填字段"""
        required_fields = []
        
        for field_type, keywords in self.FORM_FIELD_KEYWORDS.items():
            for keyword in keywords:
                if keyword in text:
                    # 检查是否标记为必填
                    required_indicators = [
                        f'{keyword}*', f'{keyword} *',
                        f'required', '必填', '必需'
                    ]
                    if any(ind in html for ind in required_indicators):
                        required_fields.append(field_type)
                        break
        
        return list(set(required_fields))
    
    def _extract_payment_methods(self, text: str) -> List[str]:
        """提取支持的支付方式"""
        found_methods = []
        text_lower = text.lower()
        
        for method in self.PAYMENT_METHODS:
            if method.lower() in text_lower:
                found_methods.append(method)
        
        return found_methods
    
    def _extract_error_messages(self, text: str) -> List[str]:
        """提取错误提示信息"""
        error_patterns = [
            r'error[\s:]*([^\.\n]{10,100})',
            r'invalid[\s:]*([^\.\n]{10,100})',
            r'please enter[\s:]+([^\.\n]{5,50})',
            r'required[\s:]*([^\.\n]{10,100})',
        ]
        
        import re
        errors = []
        for pattern in error_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                error_text = match.group(1).strip()
                if error_text and len(error_text) > 5:
                    errors.append(error_text[:100])
        
        return errors[:5]  # 最多返回5条
    
    def _calculate_friction_score(self, steps_count: int, requires_login: bool,
                                   guest_available: bool, fields_count: int,
                                   error_count: int) -> int:
        """计算摩擦分数 (0-100)"""
        score = 0
        
        # 步骤数评分 (每步+10分，最多40分)
        score += min(steps_count * 10, 40)
        
        # 强制登录 (+20分)
        if requires_login:
            score += 20
        
        # 不支持游客 (-10分，即降低摩擦)
        if guest_available:
            score -= 10
        
        # 必填字段数 (每个+5分，最多25分)
        score += min(fields_count * 5, 25)
        
        # 错误提示数 (每个+3分，最多15分)
        score += min(error_count * 3, 15)
        
        return max(0, min(100, score))
    
    def _get_friction_level(self, score: int) -> str:
        """获取摩擦等级"""
        if score >= 70:
            return 'high'
        elif score >= 40:
            return 'medium'
        return 'low'
    
    def _generate_recommendations(self, requires_login: bool, guest_available: bool,
                                   required_fields: List[str], steps: List[CheckoutStep],
                                   friction_score: int) -> List[str]:
        """生成优化建议"""
        recommendations = []
        
        if requires_login and not guest_available:
            recommendations.append('【高优先级】增加游客下单(Guest Checkout)功能，可降低转化门槛')
        
        if len(required_fields) > 4:
            recommendations.append(f'【中优先级】当前有{len(required_fields)}个必填字段，建议精简至核心3-4个')
        
        if len(steps) > 4:
            recommendations.append(f'【中优先级】结算流程有{len(steps)}步，建议优化为3-4步以内')
        
        if friction_score >= 70:
            recommendations.append('【紧急】结算摩擦分数过高，建议立即优化转化路径')
        elif friction_score >= 40:
            recommendations.append('【建议】结算体验有优化空间，可参考竞品简化流程')
        
        if 'phone' in required_fields and 'email' in required_fields:
            recommendations.append('【建议】手机号和邮箱二选一即可，减少用户输入负担')
        
        return recommendations
    
    def _step_to_dict(self, step: CheckoutStep) -> Dict[str, Any]:
        """转换步骤为字典"""
        return {
            'name': step.name,
            'required': step.required,
            'has_input': step.has_input,
            'description': step.description
        }
    
    def compare_checkout_flows(self, site_results: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
        """
        对比多个站点的结算流程
        
        Args:
            site_results: {site_name: [checkout_analysis_result]}
            
        Returns:
            对比分析结果
        """
        if not site_results:
            return {}
        
        # 计算每个站点的平均摩擦分数
        site_scores = {}
        for site_name, analyses in site_results.items():
            if analyses:
                avg_score = sum(a.get('friction_score', 0) for a in analyses) / len(analyses)
                site_scores[site_name] = avg_score
        
        if not site_scores:
            return {}
        
        # 找出最优站点
        best_site = min(site_scores.items(), key=lambda x: x[1])
        worst_site = max(site_scores.items(), key=lambda x: x[1])
        
        comparison = {
            'sites_compared': list(site_results.keys()),
            'best_practice_site': best_site[0],
            'best_friction_score': best_site[1],
            'worst_friction_site': worst_site[0],
            'worst_friction_score': worst_site[1],
            'comparison_details': []
        }
        
        # 生成详细对比
        for site_name, analyses in site_results.items():
            if analyses:
                avg_score = sum(a.get('friction_score', 0) for a in analyses) / len(analyses)
                first_analysis = analyses[0]
                comparison['comparison_details'].append({
                    'site': site_name,
                    'friction_score': avg_score,
                    'friction_level': first_analysis.get('friction_level'),
                    'steps': first_analysis.get('total_steps'),
                    'requires_login': first_analysis.get('requires_login'),
                    'guest_available': first_analysis.get('guest_checkout_available'),
                    'payment_methods': first_analysis.get('payment_method_count')
                })
        
        # 生成行动建议
        if best_site[0] != worst_site[0]:
            score_diff = worst_site[1] - best_site[1]
            comparison['action_recommendation'] = (
                f'{worst_site[0]} 的结算摩擦比 {best_site[0]} 高 {score_diff:.0f} 分，'
                f'建议参考 {best_site[0]} 的流程进行优化'
            )
        
        return comparison
