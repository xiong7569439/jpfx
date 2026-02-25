"""
浏览器封装模块 - 基于 Playwright
提供浏览器实例管理和页面操作功能
"""

import asyncio
import random
import logging
from typing import Optional, Dict, Any
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
        
        # 启动浏览器
        self._browser = await self._playwright.chromium.launch(
            headless=self.browser_config.get('headless', True),
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-web-security',
                '--disable-features=IsolateOrigins,site-per-process',
            ]
        )
        
        # 创建上下文
        viewport = {
            'width': self.anti_detection.get('viewport_width', 1920),
            'height': self.anti_detection.get('viewport_height', 1080)
        }
        
        self._context = await self._browser.new_context(
            viewport=viewport,
            user_agent=self.browser_config.get('user_agent'),
            locale='en-US',
            timezone_id='America/New_York',
            permissions=['notifications'],
            java_script_enabled=True,
        )
        
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
        
    async def goto(self, url: str, wait_for: Optional[str] = None) -> bool:
        """
        访问页面
        
        Args:
            url: 目标URL
            wait_for: 等待的选择器
            
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
            
            # 访问页面
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
                
            return True
            
        except Exception as e:
            logger.error(f"访问页面失败: {url}, 错误: {e}")
            return False
            
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
            
    async def fetch_page(self, url: str, wait_for: Optional[str] = None) -> Dict[str, Any]:
        """
        抓取单个页面
        
        Args:
            url: 目标URL
            wait_for: 等待的选择器
            
        Returns:
            页面内容字典
        """
        page = await self.browser_manager.new_page()
        operator = PageOperator(page, self.config)
        
        try:
            success = await operator.goto(url, wait_for)
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
