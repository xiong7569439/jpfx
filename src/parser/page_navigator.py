"""
页面导航器
自动发现关键页面URL
"""

import json
import logging
from typing import Dict, Any, List, Optional
from playwright.async_api import Page

logger = logging.getLogger(__name__)


class PageNavigator:
    """页面导航器 - 自动发现URL"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.target_games = config.get('target_games', [])
        self.target_countries = config.get('target_countries', [])
        
    async def discover_urls(self, page: Page, base_url: str) -> List[Dict[str, str]]:
        """
        发现站点关键URL
        
        Args:
            page: Playwright页面对象
            base_url: 站点基础URL
            
        Returns:
            页面URL列表
        """
        discovered = []
        
        # 1. 首页
        discovered.append({
            'type': 'homepage',
            'url': base_url,
            'description': '首页/主落地页'
        })
        
        # 2. 尝试搜索重点游戏
        for game in self.target_games:
            game_name = game['name']
            aliases = game.get('aliases', [])
            
            # 尝试站内搜索
            search_url = await self._try_search(page, base_url, game_name, aliases)
            if search_url:
                discovered.append({
                    'type': 'product',
                    'url': search_url,
                    'description': f'{game_name}产品页',
                    'game': game_name
                })
                
        # 3. 查找常见页面
        common_pages = await self._find_common_pages(page, base_url)
        discovered.extend(common_pages)
        
        return discovered
        
    async def _try_search(self, page: Page, base_url: str, 
                          game_name: str, aliases: List[str]) -> Optional[str]:
        """尝试搜索游戏"""
        try:
            # 访问首页
            await page.goto(base_url, wait_until='networkidle', timeout=30000)
            
            # 尝试找到搜索框
            search_selectors = [
                'input[type="search"]',
                'input[placeholder*="search" i]',
                'input[name*="search" i]',
                'input[name*="q" i]',
                '.search-input',
                '#search-input',
            ]
            
            search_input = None
            for selector in search_selectors:
                try:
                    search_input = await page.query_selector(selector)
                    if search_input:
                        break
                except:
                    continue
                    
            if search_input:
                # 尝试用别名搜索
                for alias in aliases[:2]:  # 只试前2个别名
                    try:
                        await search_input.fill(alias)
                        await search_input.press('Enter')
                        await page.wait_for_load_state('networkidle', timeout=10000)
                        
                        # 检查是否有搜索结果链接
                        links = await page.query_selector_all('a[href*="game"], a[href*="product"], a[href*="item"]')
                        if links:
                            href = await links[0].get_attribute('href')
                            if href:
                                return self._make_absolute_url(base_url, href)
                    except:
                        continue
                        
        except Exception as e:
            logger.warning(f"搜索游戏失败: {game_name}, 错误: {e}")
            
        return None
        
    async def _find_common_pages(self, page: Page, base_url: str) -> List[Dict[str, str]]:
        """查找常见页面（优惠、政策等）"""
        pages = []
        
        # 常见路径尝试
        common_paths = {
            'pricing': ['/pricing', '/prices', '/deals', '/promotions', '/offers', '/discounts'],
            'policy': ['/faq', '/help', '/support', '/refund', '/terms', '/privacy', '/kyc'],
            'affiliate': ['/affiliate', '/partner', '/referral', '/earn'],
            'blog': ['/blog', '/news', '/announcement'],
        }
        
        for page_type, paths in common_paths.items():
            for path in paths:
                url = f"{base_url.rstrip('/')}{path}"
                try:
                    response = await page.goto(url, wait_until='domcontentloaded', timeout=15000)
                    if response and response.status == 200:
                        pages.append({
                            'type': page_type,
                            'url': url,
                            'description': f'{page_type}页面'
                        })
                        break  # 找到该类型的第一个有效页面即可
                except:
                    continue
                    
        return pages
        
    def _make_absolute_url(self, base_url: str, href: str) -> str:
        """转换为绝对URL"""
        if href.startswith('http'):
            return href
        elif href.startswith('/'):
            return f"{base_url.rstrip('/')}{href}"
        else:
            return f"{base_url.rstrip('/')}/{href}"
            
    def save_manifest(self, site_name: str, urls: List[Dict[str, str]], 
                      manifest_path: str):
        """保存URL清单"""
        try:
            # 读取现有清单
            manifest = {}
            try:
                with open(manifest_path, 'r', encoding='utf-8') as f:
                    manifest = json.load(f)
            except FileNotFoundError:
                pass
                
            # 更新清单
            manifest[site_name] = urls
            
            # 保存
            with open(manifest_path, 'w', encoding='utf-8') as f:
                json.dump(manifest, f, ensure_ascii=False, indent=2)
                
            logger.info(f"URL清单已保存: {manifest_path}")
            
        except Exception as e:
            logger.error(f"保存URL清单失败: {e}")
            
    def load_manifest(self, manifest_path: str) -> Dict[str, List[Dict[str, str]]]:
        """加载URL清单"""
        try:
            with open(manifest_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.warning(f"URL清单不存在: {manifest_path}")
            return {}
        except Exception as e:
            logger.error(f"加载URL清单失败: {e}")
            return {}
