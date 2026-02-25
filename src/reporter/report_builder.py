"""
报告构建器
生成竞品策略变动日报
"""

import os
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
                     new_games: List[Dict[str, Any]] = None) -> str:
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
        lines.append('## 6. 国家 & 游戏聚焦检查（只写"有变化/有信号"的项）')
        
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
        lines.append("### 6.2 游戏（原神/PUBG/崩坏星穹铁道/绝区零/鸣潮）")
        game_changes = self._extract_game_focus(changes)
        if game_changes:
            for gc in game_changes:
                lines.append(f"- {gc}")
        else:
            lines.append("- 无显著游戏相关变化")
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
        
        lines.append(f"### 1.{idx} {site}｜{desc[:50]}")
        lines.append("")
        lines.append(f"- 变化：{desc}")
        lines.append(f"- 证据：URL：{change.get('url', '')}；摘录：\"{change.get('context', '')[:100]}\"")
        
        dims = change.get('dimensions', [])
        lines.append(f"- 归类：{'/'.join(dims)}")
        
        lines.append("- 可能目的（推测需标注）：")
        lines.append("  - （需人工分析）")
        
        lines.append("- 对我方影响：")
        lines.append("  - （需人工分析）")
        
        lines.append("- 建议动作（可选）：")
        lines.append("  - （需人工分析）")
        lines.append("")
        
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
        target_games = ['原神', 'PUBG', '崩坏星穹铁道', '绝区零', '鸣潮']
        
        for change in changes:
            desc = change.get('description', '')
            for game in target_games:
                if game in desc:
                    game_changes.append(f"{game}：{desc[:80]}")
                    break
                    
        return game_changes
        
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
