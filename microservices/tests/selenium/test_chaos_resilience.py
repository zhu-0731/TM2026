"""
故障注入期间的功能测试脚本
在 ChaosMesh 注入故障时运行 Selenium 测试，验证系统容错能力
"""

import time
import unittest
import os
import requests

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

from webdriver_manager.chrome import ChromeDriverManager


class ChaosResilienceTest(unittest.TestCase):
    """
    故障注入期间的功能测试
    在 ChaosMesh 注入故障时运行，验证：
    1. 系统是否能优雅降级
    2. 核心功能是否可用
    3. 错误提示是否友好
    """
    
    BASE_URL = os.environ.get('FRONTEND_URL', 'http://localhost:8080')
    CHAOS_DURATION = 180
    
    @classmethod
    def setUpClass(cls):
        options = webdriver.ChromeOptions()
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--window-size=1920,1080')
        
        cls.driver = webdriver.Chrome(
            service=ChromeService(ChromeDriverManager().install()),
            options=options
        )
        cls.driver.implicitly_wait(10)
        cls.wait = WebDriverWait(cls.driver, 15)
        cls.results = {'tests_passed': 0, 'tests_failed': 0, 'errors': []}
        
    @classmethod
    def tearDownClass(cls):
        cls.driver.quit()
        print(f"\n{'='*60}")
        print("故障注入期间测试结果汇总")
        print(f"{'='*60}")
        print(f"通过: {cls.results['tests_passed']}")
        print(f"失败: {cls.results['tests_failed']}")
        if cls.results['errors']:
            print(f"\n错误详情:")
            for error in cls.results['errors']:
                print(f"  - {error}")
        print(f"{'='*60}")
        
    def _record_result(self, test_name, passed, error_msg=None):
        if passed:
            self.results['tests_passed'] += 1
            print(f"  [通过] {test_name}")
        else:
            self.results['tests_failed'] += 1
            if error_msg:
                self.results['errors'].append(f"{test_name}: {error_msg}")
            print(f"  [失败] {test_name}")
            
    def test_01_homepage_availability_during_chaos(self):
        """测试故障期间首页可用性"""
        try:
            start_time = time.time()
            self.driver.get(self.BASE_URL)
            load_time = time.time() - start_time
            
            self.assertIn("Online Boutique", self.driver.title)
            products = self.driver.find_elements(By.CLASS_NAME, "card")
            
            if len(products) > 0:
                self._record_result('首页可用性', True)
                print(f"    加载时间: {load_time:.2f}s, 商品数: {len(products)}")
            else:
                error_msg = self.driver.find_elements(By.CSS_SELECTOR, ".alert, .error")
                if error_msg:
                    self._record_result('首页可用性(降级模式)', True)
                else:
                    self._record_result('首页可用性', False, "无商品且无错误提示")
        except (TimeoutException, WebDriverException) as e:
            self._record_result('首页可用性', False, str(e))
            
    def test_02_checkout_during_network_delay(self):
        """测试网络延迟期间下单功能"""
        try:
            self.driver.get(self.BASE_URL)
            first_product = self.wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, ".card a"))
            )
            first_product.click()
            
            add_button = self.wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button[type='submit']"))
            )
            add_button.click()
            
            try:
                self.wait.until(EC.url_contains("/cart"))
                cart_loaded = True
            except TimeoutException:
                cart_loaded = False
                
            if cart_loaded:
                place_order = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
                place_order.click()
                
                try:
                    self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "h3")))
                    confirmation = self.driver.find_element(By.TAG_NAME, "h3").text
                    
                    if "complete" in confirmation.lower():
                        self._record_result('延迟期间下单', True)
                        print("    订单成功提交")
                    else:
                        self._record_result('延迟期间下单', False, "未显示完成页面")
                except TimeoutException:
                    page_source = self.driver.page_source.lower()
                    if "timeout" in page_source or "error" in page_source:
                        self._record_result('延迟期间下单(超时处理)', True)
                        print("    系统正确处理了超时")
                    else:
                        self._record_result('延迟期间下单', False, "页面无响应")
            else:
                self._record_result('延迟期间购物车', False, "购物车加载超时")
        except Exception as e:
            self._record_result('延迟期间下单', False, str(e))
            
    def test_03_coupon_service_failure(self):
        """测试优惠券服务故障时的下单功能"""
        try:
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
            
            try:
                coupon_input = self.driver.find_element(By.ID, "coupon_code")
                coupon_input.send_keys("SAVE10")
            except Exception:
                pass
            
            place_order = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
            place_order.click()
            
            try:
                self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "h3")))
                confirmation = self.driver.find_element(By.TAG_NAME, "h3").text
                
                if "complete" in confirmation.lower():
                    self._record_result('优惠券服务故障期间下单', True)
                    print("    订单成功提交（优惠券服务故障时）")
                else:
                    self._record_result('优惠券服务故障期间下单', False, "未显示完成页面")
            except TimeoutException:
                self._record_result('优惠券服务故障期间下单', False, "页面加载超时")
        except Exception as e:
            self._record_result('优惠券服务故障期间下单', False, str(e))
            
    def test_04_api_health_check(self):
        """测试关键 API 健康状态"""
        apis = [
            ('/', '首页'),
            ('/product/0PUK6V6EV0', '商品详情'),
            ('/cart', '购物车'),
        ]
        
        for endpoint, name in apis:
            try:
                start_time = time.time()
                response = requests.get(f"{self.BASE_URL}{endpoint}", timeout=10)
                response_time = time.time() - start_time
                
                if response.status_code == 200:
                    self._record_result(f'API {name}', True)
                    print(f"    {name}: {response_time:.2f}s")
                elif response.status_code in [503, 502, 504]:
                    self._record_result(f'API {name}(服务不可用)', True)
                    print(f"    {name}: 服务不可用 (HTTP {response.status_code})")
                else:
                    self._record_result(f'API {name}', False, f"HTTP {response.status_code}")
            except requests.exceptions.Timeout:
                self._record_result(f'API {name}', False, "请求超时")
            except requests.exceptions.ConnectionError:
                self._record_result(f'API {name}', False, "连接错误")
            except Exception as e:
                self._record_result(f'API {name}', False, str(e))
                
    def test_05_graceful_degradation(self):
        """测试优雅降级"""
        try:
            self.driver.get(self.BASE_URL)
            self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "nav")))
            
            products = self.driver.find_elements(By.CLASS_NAME, "card")
            alerts = self.driver.find_elements(By.CSS_SELECTOR, ".alert-danger, .error-message")
            
            if len(products) > 0:
                if len(alerts) == 0:
                    self._record_result('优雅降级', True)
                    print(f"    完全正常: {len(products)} 个商品")
                else:
                    self._record_result('优雅降级(部分功能受限)', True)
                    print(f"    部分降级: {len(products)} 个商品, {len(alerts)} 个警告")
            else:
                self._record_result('优雅降级', False, "无商品显示")
        except Exception as e:
            self._record_result('优雅降级', False, str(e))


def run_chaos_test_suite(duration=180):
    """在故障注入期间持续运行测试"""
    print(f"\n{'='*60}")
    print(f"开始故障注入期间持续测试")
    print(f"持续时间: {duration} 秒")
    print(f"{'='*60}\n")
    
    start_time = time.time()
    iteration = 0
    
    while time.time() - start_time < duration:
        iteration += 1
        print(f"\n--- 第 {iteration} 轮测试 ---")
        
        loader = unittest.TestLoader()
        suite = loader.loadTestsFromTestCase(ChaosResilienceTest)
        
        runner = unittest.TextTestRunner(verbosity=1)
        result = runner.run(suite)
        
        time.sleep(30)
        
    print(f"\n{'='*60}")
    print(f"测试完成，共运行 {iteration} 轮")
    print(f"{'='*60}")


if __name__ == "__main__":
    if os.environ.get('CONTINUOUS', 'false').lower() == 'true':
        duration = int(os.environ.get('DURATION', '180'))
        run_chaos_test_suite(duration)
    else:
        unittest.main(verbosity=2)
