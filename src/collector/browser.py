"""
浏览器封装模块 - 基于 Playwright
提供浏览器实例管理和页面操作功能
"""

import asyncio
import random
import logging
from typing import Optional, Dict, Any, List
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

logger = logging.getLogger(__name__)


class BrowserManager:
    """浏览器管理器"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.browser_config = config.get('browser', {})
        self.anti_detection = config.get('anti_detection', {})
        
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        
    async def start(self):
        """启动浏览器"""
        logger.info("启动浏览器...")
        self._playwright = await async_playwright().start()
        
        # 获取代理配置
        proxy_config = self.config.get('proxy', {})
        proxy_enabled = proxy_config.get('enabled', False)
        proxy_server = proxy_config.get('server')
        proxy_username = proxy_config.get('username')
        proxy_password = proxy_config.get('password')
        geo_target = proxy_config.get('geo_target', 'US')
        
        # 构建代理参数
        browser_proxy = None
        if proxy_enabled and proxy_server:
            browser_proxy = {
                'server': proxy_server,
            }
            if proxy_username:
                browser_proxy['username'] = proxy_username
            if proxy_password:
                browser_proxy['password'] = proxy_password
            logger.info(f"使用代理服务器: {proxy_server}, 目标地区: {geo_target}")
        
        # 启动浏览器
        launch_options = {
            'headless': self.browser_config.get('headless', True),
            'args': [
                '--disable-blink-features=AutomationControlled',
                '--disable-web-security',
                '--disable-features=IsolateOrigins,site-per-process',
            ]
        }
        if browser_proxy:
            launch_options['proxy'] = browser_proxy
            
        self._browser = await self._playwright.chromium.launch(**launch_options)
        
        # 根据目标地区设置 locale 和 timezone
        locale_map = {
            'US': ('en-US', 'America/New_York'),
            'SG': ('en-SG', 'Asia/Singapore'),
            'JP': ('ja-JP', 'Asia/Tokyo'),
            'KR': ('ko-KR', 'Asia/Seoul'),
            'ID': ('id-ID', 'Asia/Jakarta'),
            'GB': ('en-GB', 'Europe/London'),
            'DE': ('de-DE', 'Europe/Berlin'),
            'FR': ('fr-FR', 'Europe/Paris'),
            'AU': ('en-AU', 'Australia/Sydney'),
            'CA': ('en-CA', 'America/Toronto'),
        }
        locale, timezone = locale_map.get(geo_target, ('en-US', 'America/New_York'))
        
        # 创建上下文
        viewport = {
            'width': self.anti_detection.get('viewport_width', 1920),
            'height': self.anti_detection.get('viewport_height', 1080)
        }
        
        context_options = {
            'viewport': viewport,
            'user_agent': self.browser_config.get('user_agent'),
            'locale': locale,
            'timezone_id': timezone,
            'permissions': ['notifications'],
            'java_script_enabled': True,
            # 强制声明 Accept-Language 为英文，让服务端返回英文版本
            'extra_http_headers': {
                'Accept-Language': 'en-US,en;q=0.9',
            },
        }
        
        # 如果启用了代理，上下文也需要配置代理
        if browser_proxy:
            context_options['proxy'] = browser_proxy
        
        self._context = await self._browser.new_context(**context_options)
        
        logger.info(f"浏览器上下文配置 - Locale: {locale}, Timezone: {timezone}")
        
        # 注入反检测脚本
        await self._inject_anti_detection()
        
        logger.info("浏览器启动完成")
        
    async def _inject_anti_detection(self):
        """注入反检测脚本"""
        script = """
        () => {
            // 覆盖 navigator.webdriver
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            
            // 覆盖 permissions.query
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' 
                    ? Promise.resolve({ state: Notification.permission })
                    : originalQuery(parameters)
            );
            
            // 覆盖 plugins
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
            
            // 覆盖 languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en']
            });
            
            // 覆盖 chrome 对象
            if (window.chrome === undefined) {
                Object.defineProperty(window, 'chrome', {
                    get: () => ({
                        runtime: {},
                        loadTimes: () => ({}),
                        csi: () => ({}),
                        app: {}
                    })
                });
            }
            
            // 覆盖 Notification 权限
            if (window.Notification) {
                Object.defineProperty(Notification, 'permission', {
                    get: () => 'default'
                });
            }
            
            // 删除 webdriver 标志
            delete navigator.__proto__.webdriver;
        }
        """
        await self._context.add_init_script(script)
        
    async def new_page(self) -> Page:
        """创建新页面"""
        if not self._context:
            raise RuntimeError("浏览器未启动")
        return await self._context.new_page()
        
    async def close(self):
        """关闭浏览器"""
        logger.info("关闭浏览器...")
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        logger.info("浏览器已关闭")
        
    async def __aenter__(self):
        await self.start()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()


class PageOperator:
    """页面操作器"""
    
    def __init__(self, page: Page, config: Dict[str, Any]):
        self.page = page
        self.config = config
        self.crawler_config = config.get('crawler', {})
        self.anti_detection = config.get('anti_detection', {})
        
    async def goto(self, url: str, wait_for: Optional[str] = None, 
                   is_spa: bool = False, spa_wait_time: int = 3000) -> bool:
        """
        访问页面
        
        Args:
            url: 目标URL
            wait_for: 等待的选择器
            is_spa: 是否为单页应用（需要等待JS渲染）
            spa_wait_time: SPA页面额外等待时间（毫秒）
            
        Returns:
            是否成功
        """
        try:
            # 随机延迟
            if self.anti_detection.get('enabled', True):
                delay = random.randint(
                    self.anti_detection.get('random_delay_min', 1000),
                    self.anti_detection.get('random_delay_max', 3000)
                )
                await asyncio.sleep(delay / 1000)
            
            # 检测是否为SPA网站
            if is_spa or self._is_spa_url(url):
                return await self._goto_spa(url, wait_for, spa_wait_time)
            else:
                return await self._goto_standard(url, wait_for)
            
        except Exception as e:
            logger.error(f"访问页面失败: {url}, 错误: {e}")
            return False
    
    def _is_spa_url(self, url: str) -> bool:
        """检测URL是否为SPA网站"""
        spa_domains = ['lootbar.gg', 'ldshop.gg']
        return any(domain in url.lower() for domain in spa_domains)
    
    async def _goto_standard(self, url: str, wait_for: Optional[str] = None) -> bool:
        """标准页面加载（服务端渲染）"""
        response = await self.page.goto(
            url,
            wait_until='domcontentloaded',
            timeout=self.crawler_config.get('page_load_timeout', 30000)
        )
        
        if response and response.status >= 400:
            logger.warning(f"页面返回错误状态码: {response.status}, URL: {url}")
            return False
            
        # 等待指定元素
        if wait_for:
            await self.page.wait_for_selector(
                wait_for,
                timeout=self.crawler_config.get('wait_for_selector_timeout', 10000)
            )
        
        # 自动设置语言/货币为 English/USD
        await self._auto_set_language_currency(url)
            
        return True
    
    async def _goto_spa(self, url: str, wait_for: Optional[str] = None, 
                        spa_wait_time: int = 3000) -> bool:
        """SPA页面加载（等待JS渲染）"""
        logger.info(f"使用SPA模式加载: {url}")
        
        # 先加载基础页面
        response = await self.page.goto(
            url,
            wait_until='domcontentloaded',
            timeout=self.crawler_config.get('page_load_timeout', 30000)
        )
        
        if response and response.status >= 400:
            logger.warning(f"页面返回错误状态码: {response.status}, URL: {url}")
            return False
        
        # 等待网络空闲（SPA加载的关键指标）
        try:
            await self.page.wait_for_load_state('networkidle', timeout=15000)
            logger.debug(f"网络已空闲: {url}")
        except Exception:
            logger.debug(f"等待网络空闲超时，继续执行: {url}")
        
        # 额外等待JS渲染
        await asyncio.sleep(spa_wait_time / 1000)
        
        # 如果指定了等待元素，等待它出现
        if wait_for:
            try:
                await self.page.wait_for_selector(
                    wait_for,
                    timeout=self.crawler_config.get('wait_for_selector_timeout', 10000)
                )
            except Exception as e:
                logger.warning(f"等待元素超时: {wait_for}, URL: {url}, 错误: {e}")
                # 不返回False，因为SPA可能已经加载了内容只是没有这个特定元素
        
        # 对于LootBar，等待价格元素出现
        if 'lootbar.gg' in url and '/top-up/' in url:
            await self._wait_for_lootbar_content()
        
        # 自动设置语言/货币为 English/USD
        await self._auto_set_language_currency(url)
        
        return True
    
    async def _wait_for_lootbar_content(self):
        """等待LootBar页面内容加载"""
        # 尝试多种可能的价格选择器
        price_selectors = [
            '[class*="price"]',
            '[class*="amount"]',
            '.product-price',
            '.price-tag',
            '[data-testid*="price"]',
        ]
        
        for selector in price_selectors:
            try:
                await self.page.wait_for_selector(selector, timeout=2000)
                logger.debug(f"找到价格元素: {selector}")
                return
            except Exception:
                continue
        
        # 如果没有找到特定选择器，再等待一下确保JS渲染完成
        await asyncio.sleep(1)

    async def _auto_set_language_currency(self, url: str):
        """
        根据URL自动将页面语言/货币切换为 English / USD。
        在每次 goto 完成后调用，三站点各自处理。
        """
        try:
            if 'ldshop.gg' in url:
                await self._ldshop_set_usd()
            elif 'lootbar.gg' in url:
                await self._lootbar_set_usd()
        except Exception as e:
            logger.debug(f"自动设置语言/货币跳过: {url}, {e}")

    async def _ldshop_set_usd(self):
        """
        LDShop: 将导航栏 Currency 切换为 USD。
        LDShop 导航栏显示 'HKD | English'，点击后打开 Language and currency 弹窗，
        需要选择 Currency 下拉中的 USD，然后点击 Save。
        """
        try:
            # 等待页面完全渲染
            await asyncio.sleep(2)

            # 先检查是否已经是 USD
            page_text = await self.page.evaluate("() => document.body.innerText.slice(0, 300)")
            if 'USD' in page_text[:50] and 'HKD' not in page_text[:50]:
                logger.debug("LDShop 已是 USD，跳过切换")
                return

            # 使用 JavaScript 点击货币切换按钮（绕过遮罩层拦截）
            clicked = await self.page.evaluate('''
                () => {
                    const btn = document.querySelector('div[class*="h-24px"][class*="flex"][class*="items-center"]');
                    if (btn && btn.innerText.includes('HKD')) {
                        const clickEvent = new MouseEvent('click', {
                            bubbles: true,
                            cancelable: true,
                            view: window
                        });
                        btn.dispatchEvent(clickEvent);
                        return 'clicked';
                    }
                    return 'not found';
                }
            ''')

            if clicked != 'clicked':
                logger.debug("LDShop 货币切换按钮未找到或已是 USD")
                return

            logger.debug("LDShop 货币按钮已点击，等待弹窗打开")
            await asyncio.sleep(2)

            # 点击 Currency 下拉菜单（显示 "HK$ HKD"）
            currency_dropdown = await self.page.query_selector('text=HK$ HKD')
            if not currency_dropdown:
                logger.debug("LDShop Currency 下拉菜单未找到")
                return

            await currency_dropdown.click()
            logger.debug("LDShop Currency 下拉已点击")
            await asyncio.sleep(1)

            # 选择 USD 选项（显示 "$ USD"）
            usd_option = await self.page.query_selector('text=$ USD')
            if not usd_option:
                logger.debug("LDShop USD 选项未找到")
                return

            await usd_option.click()
            logger.debug("LDShop USD 选项已点击")
            await asyncio.sleep(1)

            # 点击 Save 按钮保存设置
            save_btn = await self.page.query_selector('button:has-text("Save")')
            if not save_btn:
                logger.debug("LDShop Save 按钮未找到")
                return

            await save_btn.click()
            logger.debug("LDShop Save 按钮已点击")
            await asyncio.sleep(3)  # 等待页面重新加载

            # 验证切换结果
            new_text = await self.page.evaluate("() => document.body.innerText.slice(0, 300)")
            if 'USD' in new_text[:50]:
                logger.info("LDShop 已切换为 USD")
            else:
                logger.debug("LDShop 切换 USD 可能未成功")

        except Exception as e:
            logger.debug(f"LDShop 切换 USD 失败: {e}")

    async def _lootbar_set_usd(self):
        """
        LootBar: 确认货币为 USD，通常代理生效后已自动是 USD。
        如果不是则尝试切换。
        """
        try:
            page_text = await self.page.evaluate("() => document.body.innerText.slice(0, 200)")
            if 'USD' in page_text:
                logger.debug("LootBar 已是 USD")
                return

            # 尝试找到货币切换按钮
            trigger_selectors = [
                "[class*='currency']",
                "[class*='locale']",
                "[class*='lang']",
                "header [class*='select']",
            ]
            for sel in trigger_selectors:
                try:
                    elem = await self.page.query_selector(sel)
                    if elem and await elem.is_visible():
                        text = (await elem.inner_text()).strip()
                        if text and 'USD' not in text:
                            await elem.click()
                            await asyncio.sleep(0.8)
                            usd = await self.page.query_selector(
                                "text=USD, li:has-text('USD'), [data-value='USD']"
                            )
                            if usd and await usd.is_visible():
                                await usd.click()
                                await asyncio.sleep(1)
                                logger.info("LootBar 已切换为 USD")
                                return
                except Exception:
                    continue
        except Exception as e:
            logger.debug(f"LootBar 检查 USD 失败: {e}")
            
    async def get_content(self) -> Dict[str, Any]:
        """
        获取页面内容
        
        Returns:
            包含HTML、文本、标题等信息的字典
        """
        try:
            html = await self.page.content()
            title = await self.page.title()
            
            # 获取可见文本
            text = await self.page.evaluate('''() => {
                return document.body.innerText;
            }''')
            
            # 获取元数据
            meta_description = await self.page.evaluate('''() => {
                const meta = document.querySelector('meta[name="description"]');
                return meta ? meta.content : '';
            }''')
            
            # 获取URL（可能有重定向）
            final_url = self.page.url
            
            return {
                'html': html,
                'text': text,
                'title': title,
                'meta_description': meta_description,
                'url': final_url,
                'success': True
            }
            
        except Exception as e:
            logger.error(f"获取页面内容失败: {e}")
            return {
                'html': '',
                'text': '',
                'title': '',
                'meta_description': '',
                'url': self.page.url,
                'success': False,
                'error': str(e)
            }
            
    async def screenshot(self, path: str):
        """截图"""
        await self.page.screenshot(path=path, full_page=True)
        
    async def close(self):
        """关闭页面"""
        await self.page.close()

    # ================================================================
    # 专项抓取方法：LootBar
    # ================================================================

    async def lootbar_handle_popup(self, close_selectors: List[str] = None) -> Optional[Dict[str, Any]]:
        """
        处理LootBar新人优惠弹窗。
        返回弹窗信息（折扣码、折扣力度），并自动关闭。
        """
        popup_info = None
        default_selectors = [
            "[class*='close']", "[class*='modal'] button",
            ".dialog-close", "[aria-label='close']", "[aria-label='Close']",
            "[class*='popup'] [class*='close']", "[class*='overlay'] button"
        ]
        selectors = close_selectors or default_selectors

        try:
            # 等待弹窗出现（2秒）
            await asyncio.sleep(2)

            # 尝试提取弹窗内容（折扣码和折扣力度）
            promo_code = None
            discount_text = None

            # 折扣码匹配
            code_selectors = [
                "[class*='promo'] [class*='code']",
                "[class*='coupon'] [class*='code']",
                "[class*='code'][class*='copy']",
                "input[readonly]",
            ]
            for sel in code_selectors:
                try:
                    elem = await self.page.query_selector(sel)
                    if elem:
                        promo_code = await elem.inner_text()
                        promo_code = promo_code.strip()
                        if promo_code:
                            break
                except Exception:
                    continue

            # 折扣力度匹配
            discount_selectors = [
                "[class*='popup'] [class*='discount']",
                "[class*='modal'] [class*='discount']",
                "[class*='popup'] [class*='off']",
                "[class*='modal'] [class*='save']",
            ]
            for sel in discount_selectors:
                try:
                    elem = await self.page.query_selector(sel)
                    if elem:
                        discount_text = await elem.inner_text()
                        discount_text = discount_text.strip()
                        if discount_text:
                            break
                except Exception:
                    continue

            if promo_code or discount_text:
                popup_info = {
                    'promo_code': promo_code,
                    'discount_text': discount_text
                }
                logger.info(f"LootBar弹窗信息: 折扣码={promo_code}, 折扣力度={discount_text}")

            # 关闭弹窗
            for sel in selectors:
                try:
                    btn = await self.page.query_selector(sel)
                    if btn and await btn.is_visible():
                        await btn.click()
                        logger.debug(f"LootBar弹窗已关闭: {sel}")
                        await asyncio.sleep(0.5)
                        break
                except Exception:
                    continue

        except Exception as e:
            logger.debug(f"LootBar弹窗处理跳过: {e}")

        return popup_info

    async def lootbar_extract_carousel(self, carousel_selector: str = None) -> List[Dict[str, str]]:
        """
        提取LootBar首页轮播图前3张的活动标题和副标题。
        """
        banners = []
        try:
            # 等待轮播图加载
            await asyncio.sleep(2)
            # 尝试滚动触发懒加载
            await self.page.evaluate("window.scrollTo(0, 200)")
            await asyncio.sleep(0.5)
            await self.page.evaluate("window.scrollTo(0, 0)")
            await asyncio.sleep(1)

            # LootBar轮播图可能的选择器（优先级从高到低）
            candidates = [
                ".swiper-slide:not(.swiper-slide-duplicate)",
                "[class*='banner'] [class*='item']",
                "[class*='carousel'] li",
                "[class*='slider'] [class*='item']",
                ".swiper-slide",
                "[class*='slide']",
            ]
            if carousel_selector:
                candidates.insert(0, carousel_selector)

            slides = []
            for sel in candidates:
                slides = await self.page.query_selector_all(sel)
                # 过滤掉不可见的幻灯片
                visible_slides = []
                for s in slides:
                    try:
                        if await s.is_visible():
                            visible_slides.append(s)
                    except Exception:
                        pass
                if len(visible_slides) >= 1:
                    slides = visible_slides
                    break

            for slide in slides[:3]:
                try:
                    # 获取整个幻灯片文本，然后解析标题/副标题
                    full_text = (await slide.inner_text()).strip()
                    lines = [l.strip() for l in full_text.split('\n') if l.strip() and len(l.strip()) > 2]

                    title = ''
                    subtitle = ''

                    # 优先从具名元素提取
                    for t_sel in ["h1", "h2", "h3", "[class*='title']", "[class*='heading']", "strong", "b"]:
                        t_elem = await slide.query_selector(t_sel)
                        if t_elem:
                            candidate = (await t_elem.inner_text()).strip()
                            if candidate and len(candidate) > 2:
                                title = candidate
                                break

                    # 副标题
                    for s_sel in ["[class*='sub']", "[class*='desc']", "[class*='text']", "p", "span"]:
                        s_elem = await slide.query_selector(s_sel)
                        if s_elem:
                            candidate = (await s_elem.inner_text()).strip()
                            if candidate and candidate != title and len(candidate) > 2:
                                subtitle = candidate
                                break

                    # 如果没找到具名元素，使用文本行
                    if not title and lines:
                        title = lines[0][:80]
                    if not subtitle and len(lines) > 1:
                        subtitle = lines[1][:80]

                    if title and len(title) > 2:
                        banners.append({'title': title[:80], 'subtitle': subtitle[:80]})
                except Exception:
                    continue

            logger.info(f"LootBar首页轮播图提取到 {len(banners)} 张")
        except Exception as e:
            logger.debug(f"LootBar轮播图提取失败: {e}")

        return banners

    async def lootbar_extract_trending(self, trending_selector: str = None,
                                       count: int = 5) -> List[str]:
        """
        提取LootBar首页热门充值游戏名称（前5款）。
        策略：定位"Hot-Selling"区块，提取其下游戏卡片名称。
        """
        trending = []
        try:
            # 先滚动到页面中部加载懒加载内容
            await self.page.evaluate("window.scrollTo(0, 600)")
            await asyncio.sleep(1.5)

            # 策略1：通过包含 "Hot" 或 "Trending" 文字的标题定位区块
            section_found = False
            section_headings = await self.page.query_selector_all(
                "h2, h3, [class*='section'] [class*='title'], [class*='module'] [class*='title']"
            )
            for heading in section_headings:
                try:
                    heading_text = (await heading.inner_text()).strip().lower()
                    if any(kw in heading_text for kw in ['hot', 'trending', 'popular', 'top-up', 'selling']):
                        # 找到热门区块标题，获取其父容器下的游戏项
                        parent = await heading.evaluate_handle(
                            "el => el.closest('[class*=\"section\"], [class*=\"module\"], [class*=\"block\"], section, div')"
                        )
                        if parent:
                            game_items = await parent.query_selector_all(
                                "[class*='game'] [class*='name'], [class*='item'] [class*='name'], "
                                "[class*='card'] [class*='name'], [class*='game-name'], "
                                "[class*='product'] h3, [class*='product'] h4, "
                                "[class*='item'] h3, [class*='item'] h4"
                            )
                            for gi in game_items[:count]:
                                name = (await gi.inner_text()).strip()
                                # 过滤导航文字（太短或含有特定导航词）
                                nav_words = ['popular games', 'more games', 'all', 'view more', 'see all']
                                if name and len(name) > 2 and not any(nw in name.lower() for nw in nav_words):
                                    trending.append(name)
                            if trending:
                                section_found = True
                                break
                except Exception:
                    continue

            # 策略2：如果策略1未找到，使用通用游戏卡片选择器
            if not section_found:
                candidates = [
                    trending_selector,
                    "[class*='hot-game'] [class*='name']",
                    "[class*='trending-game'] [class*='name']",
                    "[class*='game-card'] [class*='name']",
                    "[class*='top-game'] [class*='name']",
                ]
                for sel in candidates:
                    if not sel:
                        continue
                    items = await self.page.query_selector_all(sel)
                    if items:
                        for item in items[:count]:
                            try:
                                name = (await item.inner_text()).strip()
                                nav_words = ['popular games', 'more games', 'all', 'view more', 'see all']
                                if name and len(name) > 2 and not any(nw in name.lower() for nw in nav_words):
                                    trending.append(name)
                            except Exception:
                                continue
                        if trending:
                            break

            logger.info(f"LootBar热门游戏提取到 {len(trending)} 款")
        except Exception as e:
            logger.debug(f"LootBar热门游戏提取失败: {e}")

        return trending[:count]

    # ================================================================
    # 专项抓取方法：LDShop
    # ================================================================

    # 修改：移除了未使用的 ldshop_set_currency_usd 方法
    # 货币切换功能已由 _ldshop_set_usd 方法实现

    async def ldshop_extract_announcements(self, count: int = 2) -> List[str]:
        """
        提取LDShop首页公告/活动信息：
        包括顶部横幅文案、新人优惠、订阅优惠等。
        """
        announcements = []
        try:
            # 策略1：提取顶部全局横幅/公告条
            top_banner_selectors = [
                "[class*='announce']",
                "[class*='notice']",
                "[class*='alert']",
                "[class*='banner-top']",
                "[class*='top-bar']",
                "[class*='header-banner']",
                # 包含所有顶部横幅内容
                "header [class*='bar']",
                "header [class*='promo']",
            ]
            for sel in top_banner_selectors:
                try:
                    items = await self.page.query_selector_all(sel)
                    for item in items:
                        text = (await item.inner_text()).strip()
                        if text and len(text) > 5 and text not in announcements:
                            announcements.append(text[:150])
                except Exception:
                    continue

            # 策略2：如果顶部横幅未取到，滚动到中部并取活动标题
            if not announcements:
                await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight * 0.3)")
                await asyncio.sleep(1)

                mid_selectors = [
                    "[class*='promotion'] [class*='title']",
                    "[class*='activity'] [class*='title']",
                    "[class*='event'] [class*='title']",
                    "[class*='banner'] [class*='title']",
                    "section [class*='promo'] h2",
                    "section [class*='promo'] h3",
                ]
                for sel in mid_selectors:
                    try:
                        items = await self.page.query_selector_all(sel)
                        for item in items:
                            text = (await item.inner_text()).strip()
                            if text and len(text) > 5 and text not in announcements:
                                announcements.append(text[:150])
                    except Exception:
                        continue

            # 策略3：直接用 JavaScript 抓取页面内所有含有促销关键词的可见文字块
            if not announcements:
                promo_texts = await self.page.evaluate("""
                    () => {
                        const result = [];
                        const promoKw = ['% off', 'register', 'new member', 'discount', 'save', 'subscribe'];
                        // 遍历可能是公告条的元素（小层小块，不是大容器）
                        const allEls = document.querySelectorAll('p, span, div, li, a');
                        for (const el of allEls) {
                            const children = el.children.length;
                            if (children > 3) continue;  // 过滤容器元素
                            const t = el.innerText ? el.innerText.trim() : '';
                            const lower = t.toLowerCase();
                            if (t.length > 10 && t.length < 200 &&
                                promoKw.some(kw => lower.includes(kw))) {
                                const rect = el.getBoundingClientRect();
                                if (rect && rect.height > 0 && rect.height < 80 && rect.width > 100) {
                                    result.push(t);
                                }
                            }
                        }
                        return [...new Set(result)].slice(0, 4);
                    }
                """)
                if promo_texts:
                    announcements.extend(promo_texts)

            # 去重并限制数量
            unique = list(dict.fromkeys(announcements))
            announcements = unique[:count]
            logger.info(f"LDShop公告提取到 {len(announcements)} 条")
        except Exception as e:
            logger.debug(f"LDShop公告提取失败: {e}")

        return announcements

    async def ldshop_extract_payment_promos(self) -> List[str]:
        """
        提取LDShop页面中的支付渠道促销信息。
        策略：滚动到底部结购区 + JS文字扫描双重保障。
        """
        promos = []
        try:
            # 先滚动到页面底部附近
            await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight * 0.8)")
            await asyncio.sleep(1.5)

            # 策略1: CSS选择器匹配支付区域
            css_candidates = [
                "[class*='payment'] [class*='promo']",
                "[class*='payment'] [class*='offer']",
                "[class*='payment-method'] p",
                "[class*='checkout'] [class*='promo']",
                "[class*='pay'] [class*='discount']",
                "[class*='wallet'] [class*='bonus']",
                "[class*='pay-tip']",
                "[class*='payment-tip']",
                "[class*='pay-info']",
            ]
            for sel in css_candidates:
                try:
                    items = await self.page.query_selector_all(sel)
                    for item in items:
                        text = (await item.inner_text()).strip()
                        if text and len(text) > 5:
                            promos.append(text[:150])
                except Exception:
                    continue

            # 策略2：如果CSS选择器未命中，用JS扫描页面内含支付关键词的可见文字
            if not promos:
                pay_texts = await self.page.evaluate("""
                    () => {
                        const result = [];
                        const payKw = ['wallet', 'visa', 'mastercard', 'paypal',
                                       'alipay', 'wechat', 'gcash', 'grab', 'dana',
                                       'cashback', 'rebate', 'free fee', 'no fee',
                                       'waive', 'extra bonus'];
                        const allEls = document.querySelectorAll('p, span, li, div');
                        for (const el of allEls) {
                            const children = el.children.length;
                            if (children > 2) continue;
                            const t = el.innerText ? el.innerText.trim() : '';
                            const lower = t.toLowerCase();
                            if (t.length > 8 && t.length < 150 &&
                                payKw.some(kw => lower.includes(kw)) &&
                                (lower.includes('%') || lower.includes('free') ||
                                 lower.includes('bonus') || lower.includes('off'))) {
                                const rect = el.getBoundingClientRect();
                                if (rect && rect.height > 0 && rect.height < 80) {
                                    result.push(t);
                                }
                            }
                        }
                        return [...new Set(result)].slice(0, 6);
                    }
                """)
                if pay_texts:
                    promos.extend(pay_texts)

            # 去重并限制数量
            seen = set()
            unique = []
            for p in promos:
                key = p[:40]
                if key not in seen:
                    seen.add(key)
                    unique.append(p)
            promos = unique[:6]
            logger.info(f"LDShop支付促销提取到 {len(promos)} 条")
        except Exception as e:
            logger.debug(f"LDShop支付促销提取失败: {e}")

        return promos

    # ================================================================
    # 动态发现方法：首页热门商品区域
    # ================================================================

    async def discover_hot_products(self, site_name: str, base_url: str, 
                                    max_items: int = 10) -> List[Dict[str, str]]:
        """
        动态发现首页上的热门商品/推荐商品链接
        
        支持识别的区域类型：
        - 热门商品 (hot products)
        - 最近热卖 (recently hot)
        - 促销热卖 (promotional hot deals)
        - Trending Products
        - Best Sellers
        - Hot Deals
        - Popular Games
        - Recommended
        
        Args:
            site_name: 站点名称 (LootBar, LDShop)
            base_url: 站点基础URL
            max_items: 最大发现商品数量
            
        Returns:
            发现的商品列表，每项包含 name, url, source (发现来源区域)
        """
        discovered = []
        
        try:
            # 滚动页面以加载所有内容
            await self._scroll_to_load_content()
            
            # 根据站点选择特定的发现策略
            if 'lootbar.gg' in base_url:
                discovered = await self._discover_lootbar_hot_products(max_items)
            elif 'ldshop.gg' in base_url:
                discovered = await self._discover_ldshop_hot_products(max_items)
            else:
                # 通用发现策略
                discovered = await self._discover_generic_hot_products(max_items)
            
            # 将相对URL转换为绝对URL
            for item in discovered:
                if item.get('url') and not item['url'].startswith('http'):
                    item['url'] = self._make_absolute_url(base_url, item['url'])
            
            logger.info(f"[{site_name}] 动态发现 {len(discovered)} 个热门商品链接")
            
        except Exception as e:
            logger.warning(f"动态发现热门商品失败: {base_url}, 错误: {e}")
        
        return discovered
    
    async def _scroll_to_load_content(self):
        """滚动页面以加载懒加载内容"""
        try:
            # 分阶段滚动
            for scroll_pct in [0.3, 0.6, 0.9]:
                await self.page.evaluate(f"window.scrollTo(0, document.body.scrollHeight * {scroll_pct})")
                await asyncio.sleep(0.8)
            # 回到顶部
            await self.page.evaluate("window.scrollTo(0, 0)")
            await asyncio.sleep(0.5)
        except Exception:
            pass
    
    async def _discover_lootbar_hot_products(self, max_items: int) -> List[Dict[str, str]]:
        """发现LootBar首页热门商品"""
        products = []
        
        # 热门区域关键词（用于匹配区块标题）
        hot_section_keywords = [
            'hot', 'trending', 'popular', 'best seller', 'top up', 
            'recommended', 'featured', 'hot-selling'
        ]
        
        try:
            # 策略1: 通过区块标题定位热门区域
            sections = await self.page.query_selector_all(
                "h2, h3, [class*='section-title'], [class*='module-title'], [class*='block-title']"
            )
            
            for section in sections:
                try:
                    section_text = (await section.inner_text()).strip().lower()
                    
                    # 检查是否是热门区域
                    if any(kw in section_text for kw in hot_section_keywords):
                        # 找到该区块的父容器
                        parent = await section.evaluate_handle(
                            "el => el.closest('[class*=\"section\"], [class*=\"module\"], [class*=\"block\"], section, div')"
                        )
                        
                        if parent:
                            # 在该容器内查找商品链接
                            links = await parent.query_selector_all("a[href*='/top-up/'], a[href*='/game/']")
                            
                            for link in links[:max_items]:
                                try:
                                    href = await link.get_attribute('href')
                                    # 获取商品名称
                                    name = await self._extract_product_name_from_element(link)
                                    
                                    if href and name:
                                        products.append({
                                            'name': name,
                                            'url': href,
                                            'source': f"热门区域: {section_text[:30]}"
                                        })
                                except Exception:
                                    continue
                                    
                        if len(products) >= max_items:
                            break
                            
                except Exception:
                    continue
            
            # 策略2: 如果没有找到，使用通用游戏卡片选择器
            if not products:
                card_selectors = [
                    "[class*='game-card']",
                    "[class*='hot-game']",
                    "[class*='trending-game']",
                    "[class*='product-card']",
                    "a[href*='/top-up/']"
                ]
                
                for selector in card_selectors:
                    cards = await self.page.query_selector_all(selector)
                    for card in cards[:max_items]:
                        try:
                            href = await card.get_attribute('href')
                            name = await self._extract_product_name_from_element(card)
                            
                            if href and name:
                                products.append({
                                    'name': name,
                                    'url': href,
                                    'source': '游戏卡片区域'
                                })
                        except Exception:
                            continue
                    
                    if products:
                        break
                        
        except Exception as e:
            logger.debug(f"LootBar热门商品发现失败: {e}")
        
        # 去重
        return self._deduplicate_products(products[:max_items])
    
    async def _discover_ldshop_hot_products(self, max_items: int) -> List[Dict[str, str]]:
        """发现LDShop首页热门商品"""
        products = []
        
        hot_section_keywords = [
            'hot', 'trending', 'popular', 'best seller', 'featured',
            'recommended', 'promotion', 'sale', '热门', '推荐'
        ]
        
        try:
            # 策略1: 查找热门区域
            sections = await self.page.query_selector_all(
                "h2, h3, [class*='section-title'], [class*='heading']"
            )
            
            for section in sections:
                try:
                    section_text = (await section.inner_text()).strip().lower()
                    
                    if any(kw in section_text for kw in hot_section_keywords):
                        parent = await section.evaluate_handle(
                            "el => el.closest('[class*=\"section\"], [class*=\"module\"], [class*=\"block\"], section, div')"
                        )
                        
                        if parent:
                            links = await parent.query_selector_all(
                                "a[href*='/top-up/'], a[href*='/catalog/']"
                            )
                            
                            for link in links[:max_items]:
                                try:
                                    href = await link.get_attribute('href')
                                    name = await self._extract_product_name_from_element(link)
                                    
                                    if href and name:
                                        products.append({
                                            'name': name,
                                            'url': href,
                                            'source': f"热门区域: {section_text[:30]}"
                                        })
                                except Exception:
                                    continue
                                    
                        if len(products) >= max_items:
                            break
                            
                except Exception:
                    continue
            
            # 策略2: 查找商品卡片
            if not products:
                card_selectors = [
                    "[class*='product-item']",
                    "[class*='game-item']",
                    "[class*='hot-item']",
                    "a[href*='/top-up/']"
                ]
                
                for selector in card_selectors:
                    cards = await self.page.query_selector_all(selector)
                    for card in cards[:max_items]:
                        try:
                            href = await card.get_attribute('href')
                            name = await self._extract_product_name_from_element(card)
                            
                            if href and name:
                                products.append({
                                    'name': name,
                                    'url': href,
                                    'source': '商品卡片区域'
                                })
                        except Exception:
                            continue
                    
                    if products:
                        break
                        
        except Exception as e:
            logger.debug(f"LDShop热门商品发现失败: {e}")
        
        return self._deduplicate_products(products[:max_items])
    
    async def _discover_generic_hot_products(self, max_items: int) -> List[Dict[str, str]]:
        """通用热门商品发现策略"""
        products = []
        
        hot_keywords = [
            'hot', 'trending', 'popular', 'best', 'featured', 'recommended',
            'sale', 'promo', 'deal', '热门', '推荐', '热卖'
        ]
        
        try:
            # 使用JavaScript扫描页面结构
            result = await self.page.evaluate("""
                (keywords) => {
                    const products = [];
                    const seen = new Set();
                    
                    // 查找所有可能的商品链接
                    const links = document.querySelectorAll('a[href*="/product"], a[href*="/game"], a[href*="/top-up"]');
                    
                    links.forEach(link => {
                        const href = link.href;
                        if (seen.has(href)) return;
                        
                        // 获取商品名称
                        let name = '';
                        const nameEl = link.querySelector('h3, h4, [class*="name"], [class*="title"]');
                        if (nameEl) {
                            name = nameEl.innerText.trim();
                        } else {
                            name = link.innerText.trim().split('\\n')[0];
                        }
                        
                        // 检查是否在热门区域内
                        let source = '商品链接';
                        let parent = link.parentElement;
                        for (let i = 0; i < 5 && parent; i++) {
                            const text = parent.innerText.toLowerCase();
                            const hasKeyword = keywords.some(kw => text.includes(kw));
                            if (hasKeyword) {
                                const heading = parent.querySelector('h2, h3, h4');
                                if (heading) {
                                    source = '热门区域: ' + heading.innerText.trim().slice(0, 30);
                                }
                                break;
                            }
                            parent = parent.parentElement;
                        }
                        
                        if (name && href && !seen.has(href)) {
                            seen.add(href);
                            products.push({name, url: href, source});
                        }
                    });
                    
                    return products.slice(0, """ + str(max_items) + """);
                }
            """, hot_keywords)
            
            products = result if result else []
            
        except Exception as e:
            logger.debug(f"通用热门商品发现失败: {e}")
        
        return products
    
    async def _extract_product_name_from_element(self, element) -> str:
        """从元素中提取商品名称"""
        try:
            # 尝试多种选择器获取名称
            name_selectors = [
                "[class*='name']",
                "[class*='title']",
                "h3",
                "h4",
                ".product-name",
                ".game-name"
            ]
            
            for selector in name_selectors:
                try:
                    name_elem = await element.query_selector(selector)
                    if name_elem:
                        name = (await name_elem.inner_text()).strip()
                        if name and len(name) > 1:
                            return name
                except Exception:
                    continue
            
            # 回退：使用元素本身的文本
            text = (await element.inner_text()).strip()
            # 取第一行作为名称
            lines = [l.strip() for l in text.split('\\n') if l.strip()]
            if lines:
                return lines[0]
                
        except Exception:
            pass
        
        return ''
    
    def _deduplicate_products(self, products: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """去重商品列表"""
        seen = set()
        unique = []
        for p in products:
            key = p.get('url', '')
            if key and key not in seen:
                seen.add(key)
                unique.append(p)
        return unique
    
    def _make_absolute_url(self, base_url: str, href: str) -> str:
        """将相对URL转换为绝对URL"""
        if href.startswith('http'):
            return href
        elif href.startswith('/'):
            return f"{base_url.rstrip('/')}{href}"
        else:
            return f"{base_url.rstrip('/')}/{href}"


class Crawler:
    """爬虫主类"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.browser_manager: Optional[BrowserManager] = None
        
    async def __aenter__(self):
        self.browser_manager = BrowserManager(self.config)
        await self.browser_manager.start()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.browser_manager:
            await self.browser_manager.close()
            
    async def fetch_page(self, url: str, wait_for: Optional[str] = None,
                         is_spa: bool = False, spa_wait_time: int = 3000) -> Dict[str, Any]:
        """
        抓取单个页面
        
        Args:
            url: 目标URL
            wait_for: 等待的选择器
            is_spa: 是否为单页应用
            spa_wait_time: SPA页面额外等待时间
            
        Returns:
            页面内容字典
        """
        page = await self.browser_manager.new_page()
        operator = PageOperator(page, self.config)
        
        try:
            success = await operator.goto(url, wait_for, is_spa, spa_wait_time)
            if not success:
                return {
                    'url': url,
                    'success': False,
                    'error': '页面加载失败或返回错误状态码'
                }
                
            content = await operator.get_content()
            return content
            
        except Exception as e:
            logger.error(f"抓取页面失败: {url}, 错误: {e}")
            return {
                'url': url,
                'success': False,
                'error': str(e)
            }
            
        finally:
            await operator.close()
