import asyncio
from src.collector.browser import BrowserManager, PageOperator
from src.config_loader import get_config

async def test():
    config = get_config()
    async with BrowserManager(config) as bm:
        page = await bm.new_page()
        op = PageOperator(page, config)
        await op.goto('https://www.ldshop.gg')
        print('Page loaded')
        
        # Wait for page to fully render
        await asyncio.sleep(3)
        
        # Check initial state
        text = await page.evaluate('() => document.body.innerText.slice(0, 300)')
        print(f'Initial text: {text[:100]}')
        
        # Use JavaScript to click currency button directly
        clicked = await page.evaluate('''
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
        print(f'Currency button: {clicked}')
        
        if clicked == 'clicked':
            await asyncio.sleep(2)
            print('Dialog should be open now')
            
            # Click on the Currency dropdown (showing "HK$ HKD")
            currency_dropdown = await page.query_selector('text=HK$ HKD')
            if currency_dropdown:
                print('Found currency dropdown, clicking...')
                await currency_dropdown.click()
                await asyncio.sleep(1)
                
                # Look for USD option in the dropdown
                usd_option = await page.query_selector('text=$ USD')
                if usd_option:
                    print('Found USD option, clicking...')
                    await usd_option.click()
                    await asyncio.sleep(1)
                    
                    # Click Save button
                    save_btn = await page.query_selector('button:has-text("Save")')
                    if save_btn:
                        print('Found Save button, clicking...')
                        await save_btn.click()
                        await asyncio.sleep(3)
                        
                        # Check if switched
                        new_text = await page.evaluate('() => document.body.innerText.slice(0, 300)')
                        print(f'After switch: {new_text[:100]}')
                        if 'USD' in new_text[:50]:
                            print('SUCCESS: Switched to USD!')
                        else:
                            print('FAILED: Still showing HKD')
                    else:
                        print('Save button not found')
                else:
                    print('USD option not found')
                    await page.screenshot(path='ldshop_usd_not_found.png')
            else:
                print('Currency dropdown not found')
        else:
            print('Currency button not found')
        
        await page.close()

asyncio.run(test())
