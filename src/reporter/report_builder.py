"""
报告构建器
生成竞品策略变动日报
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


class ReportBuilder:
    """报告构建器"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.paths_config = config.get('paths', {})
        
    def build_report(self, date_str: str, crawl_results: List[Dict[str, Any]],
                     changes: List[Dict[str, Any]], tldr: List[Dict[str, Any]],
                     weak_signals: List[Dict[str, Any]], todos: List[str],
                     price_comparisons: List[Dict[str, Any]] = None,
                     stock_changes: List[Dict[str, Any]] = None,
                     rating_changes: List[Dict[str, Any]] = None,
                     new_games: List[Dict[str, Any]] = None,
                     price_trends: Dict[str, Any] = None,
                     promotion_analysis: Dict[str, Any] = None,
                     review_analysis: Dict[str, Any] = None,
                     checkout_analysis: Dict[str, Any] = None,
                     payment_analysis: Dict[str, Any] = None) -> str:
        """
        构建日报
        
        Args:
            date_str: 日期字符串
            crawl_results: 抓取结果
            changes: 变化列表
            tldr: 要点摘要
            weak_signals: 弱信号列表
            todos: 待办事项
            
        Returns:
            Markdown格式的报告
        """
        lines = []
        
        # 标题
        lines.append(f"# 竞品策略变动日报（{date_str}）")
        lines.append("")
        
        # TL;DR
        lines.append("## TL;DR（3-6条，按影响排序）")
        if tldr:
            for item in tldr:
                level = item.get('level', '中')
                site = item.get('site', '')
                desc = item.get('description', '')
                dims = ', '.join(item.get('dimensions', []))
                lines.append(f"- [{level}] {site} | {desc} ({dims})")
        else:
            lines.append("- 今日未发现显著策略变化")
        lines.append("")
        
        # 今日关键变化
        lines.append("## 1. 今日关键变化（按影响排序）")
        
        if changes:
            # 按影响级别分组
            high_changes = [c for c in changes if c.get('impact_level') == 'high']
            medium_changes = [c for c in changes if c.get('impact_level') == 'medium']
            low_changes = [c for c in changes if c.get('impact_level') == 'low']
            
            change_idx = 1
            
            # 高影响变化
            for change in high_changes:
                self._append_change_detail(lines, change_idx, change)
                change_idx += 1
                
            # 中影响变化
            for change in medium_changes:
                self._append_change_detail(lines, change_idx, change)
                change_idx += 1
                
            # 低影响变化
            for change in low_changes:
                self._append_change_detail(lines, change_idx, change)
                change_idx += 1
        else:
            lines.append("今日未发现关键变化。")
        lines.append("")
        
        # 新增维度：竞品间价格对比（P0）
        lines.append("## 2. 竞品间价格对比（P0）")
        if price_comparisons:
            for comp in price_comparisons:
                game = comp.get('game', '')
                cheapest_site = comp.get('cheapest_site', '')
                cheapest_price = comp.get('cheapest_price', '')
                expensive_site = comp.get('most_expensive_site', '')
                expensive_price = comp.get('most_expensive_price', '')
                diff_pct = comp.get('price_diff_pct', 0)
                lines.append(f"- **{game}**: {cheapest_site} ({cheapest_price}) 比 {expensive_site} ({expensive_price}) 低 **{diff_pct}%**")
        else:
            lines.append("- 今日价格数据不足，无法对比")
        lines.append("")
        
        # 新增：价格趋势分析
        lines.append("## 2.1 价格趋势分析（7日）")
        if price_trends and price_trends.get('game_trends'):
            # 竞争力评分概览
            lines.append("### 竞争力评分")
            for game_name, comp in price_trends.get('competitiveness', {}).items():
                score = comp.get('competitiveness_score', 0)
                rank = comp.get('topuplive_position', '-')
                gap_cheapest = comp.get('price_gap_to_cheapest', 0)
                
                score_emoji = "🟢" if score >= 80 else "🟡" if score >= 50 else "🔴"
                lines.append(f"- {score_emoji} **{game_name}**: 竞争力评分 {score}/100 | 排名 {rank}/3 | 与最低价差距 ${gap_cheapest}")
            
            lines.append("")
            
            # 价格趋势详情
            lines.append("### 各游戏价格趋势")
            for game_name, trend in price_trends.get('game_trends', {}).items():
                lines.append(f"**{game_name}**:")
                for site_name, site_data in trend.get('site_trends', {}).items():
                    direction = site_data.get('trend_direction', 'stable')
                    change_pct = site_data.get('price_change_pct', 0)
                    volatility = site_data.get('volatility', 0)
                    
                    direction_icon = "📈" if direction == 'up' else "📉" if direction == 'down' else "➡️"
                    lines.append(f"  - {site_name}: {direction_icon} {change_pct:+.1f}% (波动率: {volatility}%)")
            lines.append("")
            
            # 异常波动预警
            anomalies = price_trends.get('anomalies', [])
            if anomalies:
                lines.append("### ⚠️ 价格异常波动预警")
                for anomaly in anomalies[:5]:  # 最多显示5条
                    game = anomaly.get('game', '')
                    site = anomaly.get('site', '')
                    deviation = anomaly.get('deviation_pct', 0)
                    severity = anomaly.get('severity', 'medium')
                    icon = "🔴" if severity == 'high' else "🟡"
                    lines.append(f"- {icon} {game} | {site}: 偏离均值 {deviation:+.1f}%")
                lines.append("")
        else:
            lines.append("- 历史价格数据不足，无法分析趋势")
            lines.append("")
        
        # 新增维度：SKU变动监控（产品策略C + 定价策略A）
        lines.append("## 2.2 SKU变动监控（新增/下架/调价）")
        sku_changes = self._extract_sku_changes(changes)
        if sku_changes:
            # 新增SKU
            added_skus = [c for c in sku_changes if c['type'] == 'add']
            if added_skus:
                lines.append("### 新增SKU")
                for sku in added_skus[:10]:  # 最多显示10个
                    site = sku.get('site', '')
                    name = sku.get('sku_name', '')
                    price = sku.get('price', '')
                    currency = sku.get('currency', 'USD')
                    lines.append(f"- **{site}** | {name}: {currency}${price}")
                lines.append("")
            
            # 移除SKU
            removed_skus = [c for c in sku_changes if c['type'] == 'remove']
            if removed_skus:
                lines.append("### 下架SKU")
                for sku in removed_skus[:10]:  # 最多显示10个
                    site = sku.get('site', '')
                    name = sku.get('sku_name', '')
                    price = sku.get('price', '')
                    currency = sku.get('currency', 'USD')
                    lines.append(f"- **{site}** | {name}: {currency}${price}")
                lines.append("")
            
            # 价格变动
            price_changes = [c for c in sku_changes if c['type'] == 'change']
            if price_changes:
                lines.append("### SKU价格变动")
                for sku in price_changes[:10]:  # 最多显示10个
                    site = sku.get('site', '')
                    name = sku.get('sku_name', '')
                    old_price = sku.get('old_price', '')
                    new_price = sku.get('new_price', '')
                    currency = sku.get('currency', 'USD')
                    change_pct = sku.get('change_pct', 0)
                    direction = "📈" if change_pct > 0 else "📉"
                    lines.append(f"- **{site}** | {name}: {currency}${old_price} → {currency}${new_price} ({direction} {change_pct:+.1f}%)")
                lines.append("")
        else:
            lines.append("- 今日无显著SKU变动")
            lines.append("")
        
        # 新增维度：促销策略分析（B维度）
        lines.append("## 2.3 促销策略分析（B维度）")
        if promotion_analysis and promotion_analysis.get('promotions_by_site'):
            summary = promotion_analysis.get('promotion_summary', {})
            
            # 促销汇总
            lines.append("### 促销汇总")
            lines.append(f"- 总促销数: {summary.get('total_promotions', 0)}")
            lines.append(f"- 平均折扣率: {summary.get('average_discount', 0)}%")
            
            if summary.get('most_active_site'):
                site, count = summary['most_active_site']
                lines.append(f"- 最活跃站点: {site} ({count}个促销)")
                
            if summary.get('biggest_discount'):
                bd = summary['biggest_discount']
                lines.append(f"- 最大折扣: {bd.get('site', '')} | {bd.get('game', '')} | {bd.get('actual_discount_pct', 0)}%")
            lines.append("")
            
            # 促销类型分布
            lines.append("### 促销类型分布")
            for promo_type, count in summary.get('promotions_by_type', {}).items():
                type_name = self._get_promotion_type_name(promo_type)
                lines.append(f"- {type_name}: {count}个")
            lines.append("")
            
            # 各站点促销详情
            lines.append("### 各站点促销详情")
            for site_name, promotions in promotion_analysis.get('promotions_by_site', {}).items():
                lines.append(f"**{site_name}**:")
                for promo in promotions[:5]:  # 最多显示5个
                    game = promo.get('game', '')
                    type_name = promo.get('type_name', '')
                    discount = promo.get('actual_discount_pct', 0)
                    text = promo.get('raw_text', '')[:50]
                    lines.append(f"  - {game}: {type_name} {discount}% | {text}")
            lines.append("")
            
            # 竞争洞察
            insights = promotion_analysis.get('competitive_insights', [])
            if insights:
                lines.append("### 促销竞争洞察")
                for insight in insights:
                    lines.append(f"- {insight.get('description', '')}")
                lines.append("")
        else:
            lines.append("- 今日未检测到显著促销活动")
            lines.append("")
        
        # 新增维度：支付方式监控（新增）
        lines.append("## 2.4 支付方式监控")
        if payment_analysis and payment_analysis.get('payment_coverage'):
            coverage = payment_analysis.get('payment_coverage', {})
            
            # 支付覆盖概览
            lines.append("### 支付方式覆盖概览")
            for site_name, data in coverage.items():
                lines.append(f"- **{site_name}**: {data.get('total_methods', 0)} 种支付方式")
                for cat_name, methods in data.get('by_category', {}).items():
                    if methods:
                        lines.append(f"  - {cat_name}: {', '.join(methods[:3])}")
            lines.append("")
            
            # 支付变化
            changes = payment_analysis.get('payment_changes', [])
            if changes:
                lines.append("### 支付方式变化")
                for change in changes[:5]:
                    icon = '✅' if change.get('change_type') == 'added' else '❌'
                    lines.append(f"- {icon} {change.get('description', '')}")
                lines.append("")
            
            # 竞争差距
            gaps = payment_analysis.get('competitive_gaps', [])
            if gaps:
                lines.append("### 支付覆盖差距")
                for gap in gaps[:3]:
                    lines.append(f"- {gap.get('description', '')}")
                lines.append("")
        else:
            lines.append("- 今日未检测到支付方式数据")
            lines.append("")
        
        # 新增维度：结算链路摩擦分析（新增）
        lines.append("## 2.5 结算链路摩擦分析")
        if checkout_analysis and checkout_analysis.get('site_analysis'):
            comparison = checkout_analysis.get('comparison', {})
            site_analysis = checkout_analysis.get('site_analysis', {})
            
            # 摩擦分数对比
            lines.append("### 结算体验对比")
            if comparison.get('best_practice_site'):
                lines.append(f"- 最佳实践: **{comparison['best_practice_site']}** (摩擦分数: {comparison.get('best_friction_score')})")
            
            for site_name, analyses in site_analysis.items():
                if analyses:
                    avg_score = sum(a.get('friction_score', 0) for a in analyses) / len(analyses)
                    level = analyses[0].get('friction_level', 'unknown')
                    level_icon = "🟢" if level == 'low' else "🟡" if level == 'medium' else "🔴"
                    lines.append(f"- {level_icon} **{site_name}**: 摩擦分数 {avg_score:.0f}/100 ({level})")
                    
                    # 显示关键发现
                    for analysis in analyses[:1]:  # 只显示第一个页面的分析
                        if analysis.get('requires_login') and not analysis.get('guest_checkout_available'):
                            lines.append(f"  - ⚠️ 强制登录，不支持游客下单")
                        if analysis.get('payment_method_count', 0) > 0:
                            lines.append(f"  - 支持 {analysis.get('payment_method_count')} 种支付方式")
            lines.append("")
            
            # 优化建议
            if comparison.get('action_recommendation'):
                lines.append("### 优化建议")
                lines.append(f"- {comparison['action_recommendation']}")
                lines.append("")
        else:
            lines.append("- 今日未检测到结算流程数据")
            lines.append("")
        
        # 新增维度：库存状态变化（P1）
        lines.append("## 3. 库存状态监控（P1）")
        if stock_changes:
            for sc in stock_changes:
                site = sc.get('site', '')
                game = sc.get('game', '')
                status = sc.get('status', '')
                lines.append(f"- {site} | {game}: {status}")
        else:
            lines.append("- 今日无显著库存状态变化")
        lines.append("")
        
        # 新增维度：评价评分变化（P1）
        lines.append("## 4. 评价评分监控（P1）")
        
        # 基础评分变化
        if rating_changes:
            for rc in rating_changes:
                site = rc.get('site', '')
                game = rc.get('game', '')
                rating = rc.get('rating', '')
                review_count = rc.get('review_count', '')
                change = rc.get('change', '')
                lines.append(f"- {site} | {game}: 评分 {rating} | 评价数 {review_count} ({change})")
        else:
            lines.append("- 今日无显著评分变化")
        lines.append("")
        
        # 新增：交付时效承诺监控
        lines.append("### 交付时效承诺监控")
        delivery_commitments_found = False
        for result in crawl_results:
            site_name = result.get('site_name', '')
            
            # 跳过第三方评价平台
            if site_name.lower() in ['trustpilot']:
                continue
                
            for page in result.get('pages', []):
                if not page.get('success'):
                    continue
                snapshot_path = page.get('snapshot_path', '')
                if snapshot_path:
                    try:
                        import json
                        meta_path = f"{snapshot_path}.json"
                        with open(meta_path, 'r', encoding='utf-8') as f:
                            meta = json.load(f)
                        
                        # 尝试从解析数据中获取交付承诺
                        parsed_path = snapshot_path.replace('/snapshots/', '/parsed/') + '.json'
                        if os.path.exists(parsed_path):
                            with open(parsed_path, 'r', encoding='utf-8') as f:
                                parsed_data = json.load(f)
                            
                            delivery_commitment = parsed_data.get('delivery_commitment', {})
                            if delivery_commitment.get('has_clear_sla'):
                                delivery_commitments_found = True
                                sla_summary = delivery_commitment.get('sla_summary', '')
                                transparency = delivery_commitment.get('transparency_score', 0)
                                icon = "🟢" if transparency >= 70 else "🟡" if transparency >= 40 else "🔴"
                                lines.append(f"- {icon} **{site_name}**: {sla_summary} (透明度: {transparency}/100)")
                                
                                # 显示异常声明
                                exceptions = delivery_commitment.get('exceptions', [])
                                if exceptions:
                                    for exc in exceptions[:2]:
                                        lines.append(f"  - ⚠️ 异常声明: {exc.get('raw', '')[:60]}")
                                break
                    except Exception:
                        continue
        
        if not delivery_commitments_found:
            lines.append("- 今日未检测到明确的交付时效承诺")
        lines.append("")
        
        # 新增：用户反馈深度分析
        if review_analysis:
            lines.append("### 用户反馈深度分析")
            
            # 情感汇总
            sentiment = review_analysis.get('sentiment_summary', {})
            if sentiment:
                lines.append("**情感分布**:")
                dist = sentiment.get('sentiment_distribution', {})
                total = sentiment.get('total_reviews', 0)
                avg_rating = sentiment.get('average_rating', 0)
                lines.append(f"- 总评价数: {total} | 平均评分: {avg_rating}")
                lines.append(f"- 正面: {dist.get('positive', 0)} | 负面: {dist.get('negative', 0)} | 中性: {dist.get('neutral', 0)}")
                lines.append("")
                
                # 各站点评分对比
                lines.append("**各站点评分对比**:")
                for site, rating in sentiment.get('rating_by_site', {}).items():
                    lines.append(f"- {site}: {rating}")
                lines.append("")
                
            # 关键词分析
            keyword_analysis = review_analysis.get('keyword_analysis', {})
            if keyword_analysis:
                lines.append("**高频关键词**:")
                for kw in keyword_analysis.get('top_keywords', [])[:5]:
                    lines.append(f"- {kw['word']}: {kw['count']}次")
                lines.append("")
                
                lines.append("**反馈类别分布**:")
                for category, counts in keyword_analysis.get('category_distribution', {}).items():
                    cat_name = self._get_category_name(category)
                    pos = counts.get('positive', 0)
                    neg = counts.get('negative', 0)
                    lines.append(f"- {cat_name}: 正面{pos} | 负面{neg}")
                lines.append("")
                
            # 趋势问题
            trending_issues = review_analysis.get('trending_issues', [])
            if trending_issues:
                lines.append("**⚠️ 趋势性问题**:")
                for issue in trending_issues:
                    game = issue.get('game', '')
                    issue_name = issue.get('issue_name', '')
                    count = issue.get('mention_count', 0)
                    severity = issue.get('severity', 'medium')
                    icon = "🔴" if severity == 'high' else "🟡"
                    lines.append(f"- {icon} {game}: {issue_name} (提及{count}次)")
                lines.append("")
        
        # 新增维度：新增游戏监控（C维度-产品策略）
        lines.append("## 5. 新增游戏监控（产品策略C）")
        if new_games:
            for ng in new_games:
                site = ng.get('site_name', '')
                game = ng.get('game', '')
                lines.append(f"- **{site}** 新增游戏: **{game}**")
        else:
            lines.append("- 今日无新增游戏")
        lines.append("")
        
        # 国家 & 游戏聚焦检查
        lines.append('## 6. 国家 & 游戏聚焦检查（只写“有变化/有信号”的项）')
                
        # 6.1 国家
        lines.append("### 6.1 国家（美国/英国/德国/法国/日本/韩国/新加坡/马来西亚/澳大利亚/加拿大）")
        country_changes = self._extract_country_focus(changes)
        if country_changes:
            for cc in country_changes:
                lines.append(f"- {cc}")
        else:
            lines.append("- 无显著国家相关变化")
        lines.append("")
                
        # 6.2 游戏
        lines.append("### 6.2 游戏（原神/PUBG/崩坏星穹铁道/绝区零/鸣潮/无尽对决/王者荣耀/三角洲行动/暗区突围）")
        game_changes = self._extract_game_focus(changes)
        if game_changes:
            for gc in game_changes:
                lines.append(f"- {gc}")
        else:
            lines.append("- 无显著游戏相关变化")
        lines.append("")
        
        # 6.3 站点专项监控（LootBar / LDShop当日首页动态 + 支付促销）
        lines.append("### 6.3 站点专项监控")
        specialist_sections = self._build_specialist_sections(crawl_results)
        if specialist_sections:
            lines.extend(specialist_sections)
        else:
            lines.append("- 本日无新增专项监控信息")
        lines.append("")
        
        # 弱信号
        lines.append("## 7. 弱信号（需要继续观察）")
        if weak_signals:
            for signal in weak_signals:
                lines.append(f"- {signal.get('description', '')}")
        else:
            lines.append("- 无")
        lines.append("")
        
        # 我方今日待办
        lines.append("## 8. 我方今日待办（把建议动作抽成清单）")
        if todos:
            for todo in todos:
                lines.append(f"- [ ] {todo}")
        else:
            lines.append("- [ ] 持续监控竞品动态")
        lines.append("")
        
        # 抓取与对比日志
        lines.append("## 9. 抓取与对比日志")
        
        total_pages = sum(r.get('success_count', 0) + r.get('fail_count', 0) for r in crawl_results)
        success_pages = sum(r.get('success_count', 0) for r in crawl_results)
        
        lines.append(f"- 成功抓取：{success_pages} 页；有效变化：{len(changes)} 条")
        lines.append("")
        
        # 失败页面
        lines.append("### 失败页面：")
        has_failures = False
        for result in crawl_results:
            site_name = result.get('site_name', '')
            for page in result.get('pages', []):
                if not page.get('success'):
                    has_failures = True
                    url = page.get('url', '')
                    error = page.get('error', '未知错误')
                    lines.append(f"- {site_name} | {url} | {error}")
                    
        if not has_failures:
            lines.append("- 无")
        lines.append("")
        
        # 页脚
        lines.append("---")
        lines.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')} CST")
        
        return '\n'.join(lines)
        
    def _append_change_detail(self, lines: List[str], idx: int, change: Dict[str, Any]):
        """添加变化详情"""
        site = change.get('site_name', '')
        desc = change.get('description', '未知变化')
        dims = change.get('dimensions', [])
        
        lines.append(f"### 1.{idx} {site}｜{desc[:50]}")
        lines.append("")
        lines.append(f"- 变化：{desc}")
        lines.append(f"- 证据：URL：{change.get('url', '')}；摘录：\"{change.get('context', '')[:100]}\"")
        lines.append(f"- 归类：{'/'.join(dims)}")
        
        # 根据维度生成基础分析
        purpose, impact, actions = self._generate_analysis(change)
        
        lines.append("- 可能目的（推测需标注）：")
        for p in purpose:
            lines.append(f"  - {p}")
        
        lines.append("- 对我方影响：")
        for i in impact:
            lines.append(f"  - {i}")
        
        lines.append("- 建议动作（可选）：")
        for a in actions:
            lines.append(f"  - {a}")
        lines.append("")
        
    def _generate_analysis(self, change: Dict[str, Any]) -> tuple:
        """根据变化类型生成基础分析模板"""
        dims = change.get('dimensions', [])
        site = change.get('site_name', '')
        desc = change.get('description', '').lower()
        structured = change.get('structured_changes', [])
        
        purpose = []
        impact = []
        actions = []
        
        # A维度 - 定价策略
        if 'A' in dims:
            if '价格' in desc or 'price' in desc:
                purpose.append(f"【推测】{site} 调整定价以提升竞争力或利润率")
                impact.append(f"若我方价格高于 {site}，可能流失价格敏感用户")
                actions.append(f"对比 {site} 与我方同产品价格，评估是否需要调价")
            if '折扣' in desc or 'discount' in desc:
                purpose.append(f"【推测】{site} 通过促销活动吸引新用户或提升转化")
                impact.append(f"促销活动可能分流我方潜在用户")
                actions.append(f"监测 {site} 促销持续时间和效果")
        
        # B维度 - 促销策略
        if 'B' in dims:
            purpose.append(f"【推测】{site} 通过优惠活动刺激消费")
            impact.append(f"促销力度若大于我方，可能影响用户选择")
            actions.append(f"评估是否跟进类似促销策略")
        
        # C维度 - 产品策略
        if 'C' in dims:
            if any(k in desc for k in ['新增', '添加', '上线']):
                purpose.append(f"【推测】{site} 扩展产品线覆盖更多用户需求")
                impact.append(f"若该游戏/产品受欢迎，我方可能失去先发优势")
                actions.append(f"评估该游戏/产品的市场需求，考虑是否上线")
            elif any(k in desc for k in ['移除', '删除', '下线']):
                purpose.append(f"【推测】{site} 下线表现不佳或合规风险产品")
                impact.append(f"若我方仍有该产品，可能获得差异化优势")
                actions.append(f"了解下线原因，检查我方产品是否存在类似风险")
            else:
                purpose.append(f"【推测】{site} 优化产品展示或结构调整")
                impact.append(f"产品体验优化可能提升 {site} 转化率")
                actions.append(f"对比 {site} 产品页与我方差异")
        
        # D维度 - 支付策略
        if 'D' in dims:
            if any(k in desc for k in ['新增', '添加']):
                purpose.append(f"【推测】{site} 扩展支付方式以降低用户支付门槛")
                impact.append(f"支付方式更丰富可能提升 {site} 支付成功率")
                actions.append(f"检查我方是否支持该支付方式")
            elif any(k in desc for k in ['移除', '删除']):
                purpose.append(f"【推测】{site} 下线某支付方式（可能因合规或成本）")
                impact.append(f"若该支付方式在我方仍可用，可能成为我方优势")
                actions.append(f"了解下线原因，评估我方该支付方式风险")
        
        # E维度 - 履约与信任
        if 'E' in dims:
            if '时效' in desc or 'delivery' in desc:
                purpose.append(f"【推测】{site} 调整交付承诺以平衡体验与成本")
                impact.append(f"若 {site} 时效优于我方，可能影响用户选择")
                actions.append(f"对比 {site} 与我方实际到账时效")
            if any(k in desc for k in ['退款', 'refund', 'kyc', '实名']):
                purpose.append(f"【推测】{site} 调整政策以应对合规要求或降低风险")
                impact.append(f"政策变化可能影响用户体验和转化率")
                actions.append(f"了解政策变化细节，检查我方政策是否需要调整")
        
        # F维度 - 增长渠道
        if 'F' in dims:
            purpose.append(f"【推测】{site} 优化增长策略以获取更多流量/用户")
            impact.append(f"增长策略优化可能提升 {site} 市场份额")
            actions.append(f"研究 {site} 增长策略，考虑是否借鉴")
        
        # G维度 - SEO/内容
        if 'G' in dims:
            if '标题' in desc:
                purpose.append(f"【推测】{site} 优化SEO或调整品牌定位")
                impact.append(f"标题优化可能影响搜索排名和品牌认知")
                actions.append(f"分析新标题的关键词策略")
            else:
                purpose.append(f"【推测】{site} 更新内容以提升SEO或用户体验")
                impact.append(f"内容更新可能影响搜索排名和用户留存")
                actions.append(f"检查 {site} 内容变化的具体方向")
        
        # H维度 - 体验与转化
        if 'H' in dims and not any(d in ['A', 'B', 'C', 'D', 'E', 'F', 'G'] for d in dims):
            purpose.append(f"【推测】{site} 优化页面体验以提升转化率")
            impact.append(f"体验优化可能提升 {site} 的用户留存和转化")
            actions.append(f"体验 {site} 新页面，对比我方流程")
        
        # 如果没有生成任何分析，提供默认模板
        if not purpose:
            purpose.append("【推测】需进一步分析变化意图")
        if not impact:
            impact.append("【待评估】需结合具体变化内容评估影响")
        if not actions:
            actions.append("【待确认】建议人工深入分析后制定动作")
        
        return purpose, impact, actions
        
    def _extract_country_focus(self, changes: List[Dict[str, Any]]) -> List[str]:
        """提取国家相关变化"""
        country_changes = []
        target_countries = ['美国', '英国', '德国', '法国', '日本', '韩国', 
                          '新加坡', '马来西亚', '澳大利亚', '加拿大']
        
        for change in changes:
            desc = change.get('description', '')
            for country in target_countries:
                if country in desc:
                    country_changes.append(f"{country}：{desc[:80]}")
                    break
                    
        return country_changes
        
    def _extract_game_focus(self, changes: List[Dict[str, Any]]) -> List[str]:
        """提取游戏相关变化"""
        game_changes = []
        target_games = ['原神', 'PUBG', '崩坏星穹铁道', '绝区零', '鸣潮', 
                       '无尽对决', '王者荣耀', '三角洲行动', '暗区突围']
        
        for change in changes:
            desc = change.get('description', '')
            for game in target_games:
                if game in desc:
                    game_changes.append(f"{game}：{desc[:80]}")
                    break
                    
        return game_changes
        
    def _build_specialist_sections(self, crawl_results: List[Dict[str, Any]]) -> List[str]:
        """
        构建站点专项监控章节：
        - LootBar首页：弹窗促销码 / 轮播图 / 热门游戏
        - LDShop首页：公告 Banner
        - LDShop产品页：支付渠道促销
        """
        lines = []

        for site_result in (crawl_results or []):
            site_name = site_result.get('site_name', '')

            for page in site_result.get('pages', []):
                sd = page.get('specialist_data', {})
                if not sd:
                    continue
                url = page.get('url', '')
                page_type = page.get('type', '')

                # ---- LootBar首页 ----
                if 'lootbar.gg' in url and page_type == 'homepage':
                    lines.append(f"\n**LootBar 首页动态**")

                    # 弹窗促销码
                    popup = sd.get('popup')
                    if popup:
                        code = popup.get('promo_code', '')
                        disc = popup.get('discount_text', '')
                        lines.append(f"- 弹窗促销: 折扣码 `{code}` | 力度: {disc}")

                    # 轮播图活动
                    banners = sd.get('carousel_banners', [])
                    if banners:
                        lines.append(f"- 首页轮播图（前{len(banners)}张）:")
                        for b in banners:
                            title = b.get('title', '')
                            sub = b.get('subtitle', '')
                            lines.append(f"  - {title}" + (f" — {sub}" if sub else ''))

                    # 热门游戏
                    trending = sd.get('trending_games', [])
                    if trending:
                        lines.append(f"- 主推游戏 TOP{len(trending)}: {' / '.join(trending)}")

                # ---- LDShop首页 ----
                elif 'ldshop.gg' in url and page_type == 'homepage':
                    announcements = sd.get('announcements', [])
                    if announcements:
                        lines.append(f"\n**LDShop 首页公告**")
                        seen_ann = set()
                        for ann in announcements:
                            # 清理换行，取第一行作为主文案
                            clean = ann.split('\n')[0].strip()
                            if clean and clean not in seen_ann:
                                seen_ann.add(clean)
                                lines.append(f"- {clean[:120]}")

                # ---- LDShop产品页 ----
                elif 'ldshop.gg' in url and page_type == 'product':
                    pay_promos = sd.get('payment_promos', [])
                    if pay_promos:
                        game = page.get('game', url)
                        lines.append(f"\n**LDShop {game} 支付促销**")
                        for p in pay_promos:
                            lines.append(f"- {p[:120]}")

        return lines

    def _extract_sku_changes(self, changes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        从变化列表中提取SKU级别的变动
        
        Returns:
            SKU变动列表，包含类型(add/remove/change)和详细信息
        """
        sku_changes = []
        
        for change in changes:
            structured_changes = change.get('structured_changes', [])
            site_name = change.get('site_name', '')
            
            for sc in structured_changes:
                field = sc.get('field', '')
                
                # SKU新增
                if field == 'sku' and sc.get('type') == 'add':
                    value = sc.get('value', {})
                    sku_changes.append({
                        'type': 'add',
                        'site': site_name,
                        'sku_name': value.get('sku_name', ''),
                        'price': value.get('price', ''),
                        'currency': value.get('currency', 'USD'),
                        'sku_id': value.get('sku_id', '')
                    })
                
                # SKU移除
                elif field == 'sku' and sc.get('type') == 'remove':
                    value = sc.get('value', {})
                    sku_changes.append({
                        'type': 'remove',
                        'site': site_name,
                        'sku_name': value.get('sku_name', ''),
                        'price': value.get('price', ''),
                        'currency': value.get('currency', 'USD'),
                        'sku_id': value.get('sku_id', '')
                    })
                
                # SKU价格变动
                elif field == 'sku_price' and sc.get('type') == 'change':
                    value = sc.get('value', {})
                    old_value = sc.get('old_value', {})
                    sku_changes.append({
                        'type': 'change',
                        'site': site_name,
                        'sku_name': value.get('sku_name', ''),
                        'price': value.get('price', ''),
                        'old_price': old_value.get('price', ''),
                        'currency': value.get('currency', 'USD'),
                        'change_pct': sc.get('change_pct', 0),
                        'sku_id': value.get('sku_id', '')
                    })
        
        return sku_changes
        
    def save_report(self, report: str, date_str: str) -> str:
        """保存报告到文件"""
        report_dir = self.paths_config.get('report_output', './reports')
        os.makedirs(report_dir, exist_ok=True)
        
        filename = f"competitor_report_{date_str}.md"
        filepath = os.path.join(report_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(report)
            
        logger.info(f"报告已保存: {filepath}")
        return filepath
        
    def extract_todos(self, changes: List[Dict[str, Any]]) -> List[str]:
        """从变化中提取待办事项"""
        todos = []
        
        # 根据变化类型生成建议动作
        for change in changes:
            dims = change.get('dimensions', [])
            site = change.get('site_name', '')
            
            if 'A' in dims:  # 定价
                todos.append(f"监测 {site} 价格变化持续性")
            if 'B' in dims:  # 促销
                todos.append(f"评估是否跟进 {site} 促销活动")
            if 'D' in dims:  # 支付
                todos.append(f"检查我方支付渠道对比 {site}")
            if 'E' in dims:  # 履约
                todos.append(f"评估 {site} 服务承诺变化")
                
        # 去重
        return list(set(todos))
        
    def identify_weak_signals(self, crawl_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """识别弱信号"""
        signals = []
        
        for result in crawl_results:
            site = result.get('site_name', '')
            
            # 标题变化
            for page in result.get('pages', []):
                if page.get('title_changed'):
                    signals.append({
                        'site': site,
                        'type': 'title_change',
                        'description': f"{site} {page.get('type', '')} 页面标题变化"
                    })
                    
        return signals
        
    def _get_promotion_type_name(self, promo_type: str) -> str:
        """获取促销类型中文名"""
        type_names = {
            'first_order': '首单优惠',
            'percentage_discount': '百分比折扣',
            'fixed_amount': '固定金额减免',
            'bundle': '捆绑销售',
            'flash_sale': '限时抢购',
            'buy_x_get_y': '买赠活动',
            'coupon': '优惠券',
            'cashback': '返现/返利',
            'loyalty': '会员/忠诚计划',
            'other': '其他促销'
        }
        return type_names.get(promo_type, promo_type)
        
    def _get_category_name(self, category: str) -> str:
        """获取反馈类别中文名"""
        category_names = {
            'delivery': '发货/到账速度',
            'price': '价格/性价比',
            'service': '客服服务',
            'trust': '信任/安全',
            'experience': '购买体验'
        }
        return category_names.get(category, category)
