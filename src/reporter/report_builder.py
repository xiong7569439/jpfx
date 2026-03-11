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
        构建日报（优化版：总-分结构，表格化展示）
        """
        lines = []
        
        # 标题
        lines.append(f"# 竞品策略变动日报（{date_str}）")
        lines.append("")
        
        # ========== 第一部分：核心洞察（总） ==========
        lines.append("## 核心洞察")
        lines.append("")
        
        # TL;DR - 精简版，去掉维度标签
        if tldr:
            for item in tldr[:6]:  # 最多6条
                level = item.get('level', '中')
                site = item.get('site', '')
                desc = item.get('description', '')
                # 截断过长的描述
                if len(desc) > 80:
                    desc = desc[:77] + "..."
                lines.append(f"- **[{level}]** {site}｜{desc}")
        else:
            lines.append("- 今日未发现显著策略变化")
        lines.append("")
        
        # 快速数据看板
        lines.append("### 今日数据概览")
        lines.append("")
        
        # 统计关键指标
        total_changes = len(changes) if changes else 0
        high_impact = len([c for c in (changes or []) if c.get('impact_level') == 'high'])
        price_changes = len([c for c in (changes or []) if 'A' in c.get('dimensions', [])])
        promo_changes = len([c for c in (changes or []) if 'B' in c.get('dimensions', [])])
        
        lines.append(f"| 指标 | 数值 |")
        lines.append(f"|------|------|")
        lines.append(f"| 总变化数 | {total_changes} |")
        lines.append(f"| 高影响变化 | {high_impact} |")
        lines.append(f"| 价格/定价相关 | {price_changes} |")
        lines.append(f"| 促销相关 | {promo_changes} |")
        if new_games:
            lines.append(f"| 新增游戏 | {len(new_games)} |")
        lines.append("")
        
        # ========== 第二部分：详细变化（分） ==========
        if changes:
            lines.append("## 详细变化分析")
            lines.append("")
            
            # 合并相同URL的变化，避免重复
            merged_changes = self._merge_changes_by_url(changes)
            
            # 按影响级别分组展示
            high_changes = [c for c in merged_changes if c.get('impact_level') == 'high']
            medium_changes = [c for c in merged_changes if c.get('impact_level') == 'medium']
            low_changes = [c for c in merged_changes if c.get('impact_level') == 'low']
            
            change_idx = 1
            
            if high_changes:
                lines.append(f"### 高影响变化 ({len(high_changes)}条)")
                lines.append("")
                for change in high_changes:
                    self._append_change_detail_compact(lines, change_idx, change)
                    change_idx += 1
            
            if medium_changes:
                lines.append(f"### 中影响变化 ({len(medium_changes)}条)")
                lines.append("")
                for change in medium_changes:
                    self._append_change_detail_compact(lines, change_idx, change)
                    change_idx += 1
                    
            # 低影响变化折叠展示
            if low_changes:
                lines.append(f"<details>")
                lines.append(f"<summary>低影响变化 ({len(low_changes)}条) - 点击展开</summary>")
                lines.append("")
                for change in low_changes:
                    self._append_change_detail_compact(lines, change_idx, change)
                    change_idx += 1
                lines.append(f"</details>")
                lines.append("")
        else:
            lines.append("今日未发现关键变化。")
            lines.append("")
        
        # ========== 第三部分：10个核心数据看板 ==========
        lines.append("## 10个核心数据看板")
        lines.append("")
        lines.append("*聚焦：发现差距 & 马上提效*")
        lines.append("")
        
        # A. 商品与价格（最能快速拉开差距）
        lines.append("### A. 商品与价格 💰")
        lines.append("")
        
        # A1. Top SKU同款价格差（Price Gap）
        if price_comparisons:
            lines.append("**A1. Top SKU同款价格差**")
            lines.append("")
            lines.append(f"| SKU | 最低价站点 | 到手价 | 最高价站点 | 到手价 | 价差 | 动作建议 |")
            lines.append(f"|-----|-----------|--------|-----------|--------|------|----------|")
            for comp in price_comparisons[:10]:  # 最多10条
                game = comp.get('game', '')[:20]
                cheapest_site = comp.get('cheapest_site', '')
                cheapest_price = comp.get('cheapest_price', '')
                expensive_site = comp.get('most_expensive_site', '')
                expensive_price = comp.get('most_expensive_price', '')
                diff_pct = comp.get('price_diff_pct', 0)
                # 动作建议
                if diff_pct >= 1.5:
                    action = "⚠️ 评估降价/改返利"
                elif diff_pct >= 0.5:
                    action = "📊 持续监测"
                else:
                    action = "✅ 价格正常"
                lines.append(f"| {game} | {cheapest_site} | {cheapest_price} | {expensive_site} | {expensive_price} | {diff_pct}% | {action} |")
            lines.append("")
        
        # A2. 同款库存/可售状态（Availability）
        sku_changes = self._extract_sku_changes(changes)
        availability_changes = [s for s in sku_changes if s['type'] in ['add', 'remove']]
        if availability_changes:
            lines.append("**A2. SKU库存/可售状态变化**")
            lines.append("")
            lines.append(f"| 站点 | SKU | 变动 | 动作建议 |")
            lines.append(f"|------|-----|------|----------|")
            for sku in availability_changes[:8]:
                site = sku.get('site', '')
                name = sku.get('sku_name', '')[:25]
                change_type = "🔴 下架" if sku['type'] == 'remove' else "🟢 新增"
                action = "排查供应链" if sku['type'] == 'remove' else "关注竞品策略"
                lines.append(f"| {site} | {name} | {change_type} | {action} |")
            lines.append("")
        
        # A3. 价格结构变化（Pricing Event）
        price_structure_changes = [s for s in sku_changes if s['type'] == 'change' and abs(s.get('change_pct', 0)) >= 3]
        if price_structure_changes:
            lines.append("**A3. 价格结构变化（批量调价≥3%）**")
            lines.append("")
            lines.append(f"| 站点 | SKU | 原价 | 现价 | 幅度 | 可能原因 |")
            lines.append(f"|------|-----|------|------|------|----------|")
            for sku in price_structure_changes[:8]:
                site = sku.get('site', '')
                name = sku.get('sku_name', '')[:20]
                old_p = f"{sku.get('currency', 'USD')}${sku.get('old_price', '')}"
                new_p = f"{sku.get('currency', 'USD')}${sku.get('price', '')}"
                change_pct = sku.get('change_pct', 0)
                reason = "促销战" if change_pct < -5 else "成本变化" if change_pct < 0 else "提价"
                icon = "📉" if change_pct < 0 else "📈"
                lines.append(f"| {site} | {name} | {old_p} | {new_p} | {icon} {change_pct:+.1f}% | {reason} |")
            lines.append("")
        
        # B. 促销与转化驱动（最快能学、能抄、能超）
        lines.append("### B. 促销与转化驱动 🚀")
        lines.append("")
        
        # B4. 首页/品类页主促销位（Hero Promo）
        if promotion_analysis and promotion_analysis.get('promotions_by_site'):
            hero_promos = self._extract_hero_promos(promotion_analysis)
            if hero_promos:
                lines.append("**B4. 首页主促销位（Hero Promo）**")
                lines.append("")
                lines.append(f"| 站点 | 促销类型 | 折扣力度 | 限时 | 动作建议 |")
                lines.append(f"|------|----------|----------|------|----------|")
                for promo in hero_promos[:6]:
                    site = promo.get('site', '')
                    ptype = promo.get('type', '')
                    discount = promo.get('discount', '')
                    limited = "⏰ 是" if promo.get('is_limited') else "-"
                    action = promo.get('action_suggestion', '评估跟进')
                    lines.append(f"| {site} | {ptype} | {discount} | {limited} | {action} |")
                lines.append("")
        
        # B5. 优惠券体系可见性（Coupon UX）
        if promotion_analysis:
            coupon_analysis = promotion_analysis.get('coupon_analysis', {})
            if coupon_analysis:
                lines.append("**B5. 优惠券体系可见性**")
                lines.append("")
                lines.append(f"| 站点 | 券入口位置 | 领取步骤 | 自动应用 | 差距分析 |")
                lines.append(f"|------|-----------|----------|----------|----------|")
                for site, data in coupon_analysis.items():
                    entry = data.get('entry_point', '未知')
                    steps = data.get('steps', '-')
                    auto = "✅ 是" if data.get('auto_apply') else "❌ 否"
                    gap = data.get('gap_analysis', '-')
                    lines.append(f"| {site} | {entry} | {steps}步 | {auto} | {gap} |")
                lines.append("")
        
        # B6. 结算链路摩擦（Checkout Friction Index）
        if checkout_analysis and checkout_analysis.get('site_analysis'):
            comparison = checkout_analysis.get('comparison', {})
            site_analysis = checkout_analysis.get('site_analysis', {})
            lines.append("**B6. 结算链路摩擦指数**")
            lines.append("")
            lines.append(f"| 站点 | 步骤数 | 强制注册 | 摩擦分数 | 评级 | 优化建议 |")
            lines.append(f"|------|--------|----------|----------|------|----------|")
            for site_name, analyses in site_analysis.items():
                if analyses:
                    analysis = analyses[0]
                    steps = analysis.get('estimated_steps', '-')
                    login_req = "❌ 是" if analysis.get('requires_login') else "✅ 否"
                    guest = "✅ 支持" if analysis.get('guest_available') else "❌ 不支持"
                    score = analysis.get('friction_score', 0)
                    level = analysis.get('friction_level', 'unknown')
                    level_icon = "🟢" if level == 'low' else "🟡" if level == 'medium' else "🔴"
                    # 优化建议
                    recs = analysis.get('recommendations', [])
                    top_rec = recs[0] if recs else '-'
                    lines.append(f"| {site_name} | {steps} | {login_req} | {score:.0f}/100 | {level_icon} {level} | {top_rec[:20]}... |")
            if comparison.get('best_practice_site'):
                lines.append(f"\n💡 **最佳实践**: {comparison['best_practice_site']}（分数: {comparison.get('best_friction_score', 0):.0f}）")
            lines.append("")
        
        # C. 支付与履约（决定复购与售后成本）
        lines.append("### C. 支付与履约 💳")
        lines.append("")
        
        # C7. 支付方式覆盖与可用性（Payment Coverage & Uptime）
        if payment_analysis and payment_analysis.get('payment_coverage'):
            coverage = payment_analysis.get('payment_coverage', {})
            lines.append("**C7. 支付方式覆盖与可用性**")
            lines.append("")
            lines.append(f"| 站点 | 支付方式数 | 信用卡 | 数字钱包 | 本地支付 | 加密 | 动作建议 |")
            lines.append(f"|------|-----------|--------|----------|----------|------|----------|")
            for site_name, data in coverage.items():
                total = data.get('total_methods', 0)
                by_cat = data.get('by_category', {})
                cc = len(by_cat.get('credit_card', []))
                wallet = len(by_cat.get('digital_wallet', []))
                local = len(by_cat.get('local_payment', []))
                crypto = len(by_cat.get('crypto', []))
                # 动作建议
                if local >= 3:
                    action = "✅ 覆盖完善"
                elif local >= 1:
                    action = "📊 可补充"
                else:
                    action = "⚠️ 本地支付缺失"
                lines.append(f"| {site_name} | {total} | {cc} | {wallet} | {local} | {crypto} | {action} |")
            lines.append("")
            
            # 支付变化提醒
            pay_changes = payment_analysis.get('payment_changes', [])
            if pay_changes:
                lines.append("**支付变化提醒**: " + " | ".join([
                    f"{'🟢+' if c.get('change_type') == 'added' else '🔴-'} {c.get('description', '')}"
                    for c in pay_changes[:3]
                ]))
                lines.append("")
        
        # C8. 交付时效承诺（Delivery SLA）
        lines.append("**C8. 交付时效承诺透明度**")
        lines.append("")
        lines.append("*注：需人工抽检商品页/结算页是否写明交付时效承诺*")
        lines.append("")
        
        # C9. 退款/纠纷政策可达性（Refund Policy）
        lines.append("**C9. 退款政策可达性**")
        lines.append("")
        lines.append("*注：需人工检查退款条款是否容易找到、是否有自助入口*")
        lines.append("")
        
        # D. 需求侧信号（告诉你该把资源投哪里）
        lines.append("### D. 需求侧信号 📊")
        lines.append("")
        
        # D10. 竞品主推国家/品类变化
        lines.append("**D10. 竞品主推国家/品类变化**")
        lines.append("")
        if new_games:
            lines.append(f"🆕 **新增游戏**: {', '.join([g.get('name', '') for g in new_games[:5]])}")
        if weak_signals:
            focus_changes = [s for s in weak_signals if s.get('type') in ['title_change', 'content_change']]
            if focus_changes:
                lines.append(f"\n📍 **主推变化**:")
                for sig in focus_changes[:5]:
                    lines.append(f"- {sig.get('site', '')}: {sig.get('description', '')}")
        lines.append("")
        lines.append("*动作建议：竞品连续多天主推某国家/品类，评估是否跟进投放*")
        lines.append("")
        
        # ========== 第四部分：补充监控数据（折叠展示） ==========
        has_supplementary = stock_changes or rating_changes or new_games
        if has_supplementary:
            lines.append("<details>")
            lines.append("<summary>补充监控数据 - 点击展开</summary>")
            lines.append("")
            
            # 库存状态
            if stock_changes:
                lines.append("**库存状态变化**:")
                for sc in stock_changes:
                    site = sc.get('site', '')
                    game = sc.get('game', '')
                    status = sc.get('status', '')
                    lines.append(f"- {site} | {game}: {status}")
                lines.append("")
            
            # 评价评分
            if rating_changes:
                lines.append("**评价评分变化**:")
                for rc in rating_changes:
                    site = rc.get('site', '')
                    game = rc.get('game', '')
                    rating = rc.get('rating', '')
                    review_count = rc.get('review_count', '')
                    lines.append(f"- {site} | {game}: 评分 {rating} | 评价数 {review_count}")
                lines.append("")
            
            # 新增游戏
            if new_games:
                lines.append("**新增游戏**:")
                for ng in new_games:
                    site = ng.get('site_name', '')
                    game = ng.get('game', '')
                    lines.append(f"- **{site}**: {game}")
                lines.append("")
            
            lines.append("</details>")
            lines.append("")
        
        # ========== 第五部分：聚焦检查（精简） ==========
        # 只展示有变化的内容
        country_changes = self._extract_country_focus(changes)
        game_changes = self._extract_game_focus(changes)
        specialist_sections = self._build_specialist_sections(crawl_results)
                
        has_focus_changes = country_changes or game_changes or specialist_sections
        if has_focus_changes:
            lines.append("## 重点聚焦")
            lines.append("")
                    
            if country_changes:
                lines.append("**国家/地区**: " + " | ".join([c[:50] for c in country_changes[:3]]))
                lines.append("")
                    
            if game_changes:
                lines.append("**重点游戏**: " + " | ".join([g[:50] for g in game_changes[:3]]))
                lines.append("")
                    
            if specialist_sections:
                lines.extend(specialist_sections)
                lines.append("")
                
        # ========== 第六部分：弱信号（有则显示） ==========
        if weak_signals:
            lines.append("## 弱信号观察")
            lines.append("")
            for signal in weak_signals:
                lines.append(f"- {signal.get('description', '')}")
            lines.append("")
                
        # ========== 第七部分：待办清单 ==========
        lines.append("## 今日待办")
        lines.append("")
        if todos:
            # 去重并限制数量
            unique_todos = list(dict.fromkeys(todos))[:10]  # 最多10条，保持顺序
            for todo in unique_todos:
                lines.append(f"- [ ] {todo}")
        else:
            lines.append("- [ ] 持续监控竞品动态")
        lines.append("")
                
        # ========== 第八部分：技术日志（折叠） ==========
        lines.append("<details>")
        lines.append("<summary>抓取与对比日志 - 点击展开</summary>")
        lines.append("")
                
        total_pages = sum(r.get('success_count', 0) + r.get('fail_count', 0) for r in crawl_results)
        success_pages = sum(r.get('success_count', 0) for r in crawl_results)
                
        lines.append(f"- 成功抓取：{success_pages}/{total_pages} 页")
        lines.append(f"- 有效变化：{len(changes)} 条")
        lines.append("")
                
        # 失败页面
        failed_pages = []
        for result in crawl_results:
            site_name = result.get('site_name', '')
            for page in result.get('pages', []):
                if not page.get('success'):
                    url = page.get('url', '')
                    error = page.get('error', '未知错误')
                    failed_pages.append(f"- {site_name} | {url} | {error}")
                
        if failed_pages:
            lines.append("**失败页面**:")
            lines.extend(failed_pages[:10])  # 最多显示10条
            if len(failed_pages) > 10:
                lines.append(f"- ... 还有 {len(failed_pages) - 10} 个失败页面")
        else:
            lines.append("- 无失败页面")
                
        lines.append("")
        lines.append("</details>")
        lines.append("")
                
        # 页脚
        lines.append("---")
        lines.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')} CST")
                
        return '\n'.join(lines)
        
    def _merge_changes_by_url(self, changes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """合并相同URL的变化，避免重复"""
        url_map = {}
        
        for change in changes:
            url = change.get('url', '')
            if not url:
                continue
            
            # 使用URL作为key，合并相同页面的变化
            if url in url_map:
                # 合并描述
                existing = url_map[url]
                existing_desc = existing.get('description', '')
                new_desc = change.get('description', '')
                if new_desc and new_desc not in existing_desc:
                    existing['description'] = existing_desc + "; " + new_desc
                
                # 合并结构化变化
                existing_structured = existing.get('structured_changes', [])
                new_structured = change.get('structured_changes', [])
                existing['structured_changes'] = existing_structured + new_structured
                
                # 合并维度
                existing_dims = set(existing.get('dimensions', []))
                new_dims = set(change.get('dimensions', []))
                existing['dimensions'] = list(existing_dims | new_dims)
            else:
                url_map[url] = change.copy()
        
        return list(url_map.values())
    
    def _append_change_detail_compact(self, lines: List[str], idx: int, change: Dict[str, Any]):
        """添加精简版变化详情"""
        site = change.get('site_name', '')
        desc = change.get('description', '未知变化')
        dims = change.get('dimensions', [])
        url = change.get('url', '')
        context = change.get('context', '')[:80]
        
        # 主标题
        lines.append(f"**{idx}. {site}**｜{desc[:60]}")
        lines.append("")
        
        # 证据和归类（一行展示）
        dim_str = '/'.join(dims) if dims else '-'
        lines.append(f"📍 **证据**: [{url}]({url})｜**归类**: {dim_str}")
        if context:
            lines.append(f"📝 **摘录**: {context}")
        lines.append("")
        
        # 生成分析
        purpose, impact, actions = self._generate_analysis(change)
        
        # 只展示最重要的1-2条分析
        if purpose:
            lines.append(f"💡 **目的**: {purpose[0].replace('【推测】', '')}")
        if impact:
            lines.append(f"⚠️ **影响**: {impact[0].replace('【待评估】', '').replace('若', '')}")
        if actions:
            lines.append(f"✅ **建议**: {actions[0].replace('【待确认】', '')}")
        
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
        """构建站点专项监控章节（精简版）"""
        lines = []
        has_content = False

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
                    if not has_content:
                        lines.append("**站点动态**:")
                        has_content = True
                    
                    popup = sd.get('popup')
                    trending = sd.get('trending_games', [])
                    
                    if popup:
                        code = popup.get('promo_code', '')
                        disc = popup.get('discount_text', '')
                        lines.append(f"- **LootBar** 弹窗促销: `{code}` ({disc})")
                    
                    if trending:
                        lines.append(f"- **LootBar** 主推: {', '.join(trending[:3])}")

                # ---- LDShop首页 ----
                elif 'ldshop.gg' in url and page_type == 'homepage':
                    announcements = sd.get('announcements', [])
                    if announcements:
                        if not has_content:
                            lines.append("**站点动态**:")
                            has_content = True
                        
                        seen_ann = set()
                        for ann in announcements[:2]:  # 最多2条
                            clean = ann.split('\n')[0].strip()[:80]
                            if clean and clean not in seen_ann:
                                seen_ann.add(clean)
                                lines.append(f"- **LDShop** 公告: {clean}")

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
        
    def _extract_hero_promos(self, promotion_analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        提取首页主促销位（Hero Promo）信息
        
        Returns:
            Hero Promo列表，包含站点、类型、折扣力度、是否限时、动作建议
        """
        hero_promos = []
        
        promotions_by_site = promotion_analysis.get('promotions_by_site', {})
        
        for site_name, promos in promotions_by_site.items():
            for promo in promos:
                promo_type = promo.get('type', 'other')
                discount_pct = promo.get('actual_discount_pct', 0)
                
                # 判断是否高优先级促销
                is_hero = promo_type in ['first_order', 'flash_sale', 'percentage_discount']
                
                if is_hero:
                    # 确定促销类型名称
                    type_name = self._get_promotion_type_name(promo_type)
                    
                    # 折扣力度描述
                    if discount_pct > 0:
                        discount_desc = f"{discount_pct}%"
                    else:
                        discount_desc = promo.get('raw_text', '')[:20]
                    
                    # 判断是否限时
                    is_limited = any(kw in promo.get('raw_text', '').lower() 
                                   for kw in ['limited', 'flash', 'countdown', '限时', '秒杀'])
                    
                    # 动作建议
                    if promo_type == 'first_order':
                        action = "当天补齐新客优惠"
                    elif promo_type == 'flash_sale':
                        action = "评估限时促销跟进"
                    elif discount_pct > 20:
                        action = "关注大幅折扣影响"
                    else:
                        action = "持续监测"
                    
                    hero_promos.append({
                        'site': site_name,
                        'type': type_name,
                        'discount': discount_desc,
                        'is_limited': is_limited,
                        'action_suggestion': action,
                        'priority': 1 if promo_type == 'first_order' else 2
                    })
        
        # 按优先级排序
        hero_promos.sort(key=lambda x: x['priority'])
        return hero_promos
