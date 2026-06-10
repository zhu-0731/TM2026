"""
OnlineBoutique 增强功能测试脚本
支持多浏览器、性能指标收集、响应式布局测试
"""

import time
import unittest
import json
import os
from datetime import datetime

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.firefox import GeckoDriverManager
from webdriver_manager.microsoft import EdgeChromiumDriverManager


class OnlineBoutiqueAdvancedTest(unittest.TestCase):
    """OnlineBoutique 增强功能测试"""
    
    BROWSER = os.environ.get('TEST_BROWSER', 'chrome').lower()
    BASE_URL = os.environ.get('FRONTEND_URL', 'http://localhost:8080')
    HEADLESS = os.environ.get('HEADLESS', 'false').lower() == 'true'
    performance_data = []
    
    @classmethod
    def setUpClass(cls):
        print(f"\n启动浏览器: {cls.BROWSER}")
        print(f"目标地址: {cls.BASE_URL}")
        print(f"无头模式: {cls.HEADLESS}")
        
        if cls.BROWSER == 'chrome':
            options = webdriver.ChromeOptions()
            if cls.HEADLESS:
                options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--window-size=1920,1080')
            cls.driver = webdriver.Chrome(
                service=ChromeService(ChromeDriverManager().install()),
                options=options
            )
        elif cls.BROWSER == 'firefox':
            options = webdriver.FirefoxOptions()
            if cls.HEADLESS:
                options.add_argument('--headless')
            options.add_argument('--width=1920')
            options.add_argument('--height=1080')
            cls.driver = webdriver.Firefox(
                service=FirefoxService(GeckoDriverManager().install()),
                options=options
            )
        elif cls.BROWSER == 'edge':
            options = webdriver.EdgeOptions()
            if cls.HEADLESS:
                options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--window-size=1920,1080')
            cls.driver = webdriver.Edge(
                service=EdgeService(EdgeChromiumDriverManager().install()),
                options=options
            )
        else:
            raise ValueError(f"不支持的浏览器: {cls.BROWSER}")
        
        cls.driver.implicitly_wait(10)
        cls.wait = WebDriverWait(cls.driver, 15)
        cls.performance_data = []
        
    @classmethod
    def tearDownClass(cls):
        if cls.performance_data:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'performance_{cls.BROWSER}_{timestamp}.json'
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(cls.performance_data, f, indent=2, ensure_ascii=False)
            print(f"\n性能数据已保存到: {filename}")
        cls.driver.quit()
        
    def _record_metric(self, test_name, metric_name, value, unit=''):
        self.performance_data.append({
            'test_name': test_name,
            'metric_name': metric_name,
            'value': value,
            'unit': unit,
            'timestamp': datetime.now().isoformat(),
            'browser': self.BROWSER
        })
        
    def _get_page_load_metrics(self):
        if self.BROWSER != 'chrome':
            return {}
        try:
            timing = self.driver.execute_script(
                "return window.performance.getEntriesByType('navigation')[0];"
            )
            return timing if timing else {}
        except:
            return {}
    
    def test_01_homepage_load(self):
        start_time = time.time()
        self.driver.get(self.BASE_URL)
        load_time = time.time() - start_time
        
        self._record_metric('homepage_load', 'total_load_time', round(load_time, 3), 's')
        
        metrics = self._get_page_load_metrics()
        if metrics:
            for key, value in metrics.items():
                if isinstance(value, (int, float)) and value > 0:
                    self._record_metric('homepage_load', key, round(value, 3), 'ms')
        
        self.assertIn("Online Boutique", self.driver.title)
        products = self.driver.find_elements(By.CLASS_NAME, "card")
        self.assertGreater(len(products), 0)
        print(f"首页加载成功: {len(products)} 个商品, {load_time:.3f}s")
        
    def test_02_product_detail(self):
        self.driver.get(self.BASE_URL)
        first_product = self.wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, ".card a"))
        )
        first_product.click()
        
        self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "h2")))
        product_name = self.driver.find_element(By.TAG_NAME, "h2").text
        self.assertTrue(len(product_name) > 0)
        print(f"商品详情页: {product_name}")
        
    def test_03_add_to_cart(self):
        self.driver.get(self.BASE_URL)
        first_product = self.wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, ".card a"))
        )
        first_product.click()
        
        add_button = self.wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button[type='submit']"))
        )
        add_button.click()
        self.wait.until(EC.url_contains("/cart"))
        
        cart_items = self.driver.find_elements(By.CLASS_NAME, "cart-summary-item-row")
        self.assertGreater(len(cart_items), 0)
        print("添加购物车成功")
        
    def test_04_place_order(self):
        self.driver.get(self.BASE_URL)
        first_product = self.wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, ".card a"))
        )
        first_product.click()
        
        add_button = self.wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button[type='submit']"))
        )
        add_button.click()
        self.wait.until(EC.url_contains("/cart"))
        
        place_order = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
        place_order.click()
        
        self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "h3")))
        confirmation = self.driver.find_element(By.TAG_NAME, "h3").text
        self.assertIn("complete", confirmation.lower())
        print("下单成功")
        
    def test_05_page_load_performance(self):
        load_times = []
        for i in range(3):
            start_time = time.time()
            self.driver.get(self.BASE_URL)
            load_time = time.time() - start_time
            load_times.append(load_time)
            self._record_metric('page_load_time', f'load_{i+1}', round(load_time, 3), 's')
            time.sleep(1)
        
        avg_load_time = sum(load_times) / len(load_times)
        self._record_metric('page_load_time', 'average', round(avg_load_time, 3), 's')
        self.assertLess(avg_load_time, 5, f"平均加载时间应小于5秒，实际: {avg_load_time:.3f}s")
        print(f"平均加载时间: {avg_load_time:.3f}s (3次采样)")
        
    def test_06_responsive_layout(self):
        viewports = [
            (1920, 1080, "Desktop"),
            (1366, 768, "Laptop"),
            (768, 1024, "Tablet"),
            (375, 667, "Mobile")
        ]
        
        for width, height, device in viewports:
            self.driver.set_window_size(width, height)
            self.driver.get(self.BASE_URL)
            time.sleep(1)
            
            products = self.driver.find_elements(By.CLASS_NAME, "card")
            self.assertGreater(len(products), 0, f"{device} 视口下应显示商品")
            print(f"{device} ({width}x{height}) 响应式测试通过")
            
        self.driver.set_window_size(1920, 1080)


def run_cross_browser_tests():
    browsers = ['chrome', 'firefox', 'edge']
    results = {}
    
    for browser in browsers:
        print(f"\n{'='*60}")
        print(f"开始 {browser.upper()} 浏览器测试")
        print(f"{'='*60}")
        
        os.environ['TEST_BROWSER'] = browser
        
        loader = unittest.TestLoader()
        suite = loader.loadTestsFromTestCase(OnlineBoutiqueAdvancedTest)
        
        runner = unittest.TextTestRunner(verbosity=2)
        result = runner.run(suite)
        
        results[browser] = {
            'tests_run': result.testsRun,
            'failures': len(result.failures),
            'errors': len(result.errors),
            'success': result.wasSuccessful()
        }
    
    print(f"\n{'='*60}")
    print("跨浏览器测试结果汇总")
    print(f"{'='*60}")
    for browser, result in results.items():
        status = "通过" if result['success'] else "失败"
        print(f"{browser.upper()}: {status} (运行: {result['tests_run']}, 失败: {result['failures']}, 错误: {result['errors']})")
    
    return results


if __name__ == "__main__":
    if os.environ.get('CROSS_BROWSER', 'false').lower() == 'true':
        run_cross_browser_tests()
    else:
        unittest.main(verbosity=2)
