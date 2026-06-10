"""
Selenium 故障注入期间功能测试
============================
在 ChaosMesh 注入故障时运行 Selenium 测试，验证：
1. 系统是否能优雅降级（核心功能可用）
2. 页面加载时间是否显著增加
3. 错误提示是否友好

与阶段二的 ChaosMesh 实验配合使用：
    1. 先注入故障: kubectl apply -f chaos-experiments/cpu-stress-frontend.yaml
    2. 运行本测试: pytest test_selenium_chaos.py -v
    3. 对比基线数据，分析故障影响

环境变量：
    FRONTEND_URL    前端地址
    TEST_BROWSER    测试浏览器（默认 chrome）
    CHAOS_TYPE      故障类型（cpu/memory/network/pod_kill）
"""

import time
import pytest
import json
import os
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.common.exceptions import TimeoutException
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.microsoft import EdgeChromiumDriverManager


class TestChaosResilience:
    """
    故障注入期间的前端功能与性能测试
    
    对比基线测试（test_selenium_performance.py）的数据，
    分析故障对前端用户体验的影响。
    """
    
    BASE_URL = os.environ.get('FRONTEND_URL', 'http://localhost:18080')
    BROWSER = os.environ.get('TEST_BROWSER', 'chrome').lower()
    CHAOS_TYPE = os.environ.get('CHAOS_TYPE', 'unknown')
    
    # 性能阈值（与基线对比）
    THRESHOLD_PAGE_LOAD = 5.0      # 页面加载超过 5 秒视为异常
    THRESHOLD_RESPONSE = 10.0      # 操作响应超过 10 秒视为异常
    
    performance_data = []
    
    @classmethod
    def setup_class(cls):
        """启动浏览器"""
        print(f"\n{'='*60}")
        print(f"[Chaos 测试启动]")
        print(f"  故障类型: {cls.CHAOS_TYPE}")
        print(f"  浏览器: {cls.BROWSER}")
        print(f"  目标地址: {cls.BASE_URL}")
        print(f"{'='*60}\n")
        
        if cls.BROWSER == 'chrome':
            options = webdriver.ChromeOptions()
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--window-size=1920,1080')
            options.page_load_strategy = 'eager'
            prefs = {
                "profile.managed_default_content_settings.images": 2,
                "profile.default_content_setting_values.stylesheets": 2
            }
            options.add_experimental_option("prefs", prefs)
            cls.driver = webdriver.Chrome(
                service=ChromeService(ChromeDriverManager().install()),
                options=options
            )
        elif cls.BROWSER == 'edge':
            options = webdriver.EdgeOptions()
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--window-size=1920,1080')
            options.page_load_strategy = 'eager'
            prefs = {
                "profile.managed_default_content_settings.images": 2,
                "profile.default_content_setting_values.stylesheets": 2
            }
            options.add_experimental_option("prefs", prefs)
            cls.driver = webdriver.Edge(
                service=EdgeService(EdgeChromiumDriverManager().install()),
                options=options
            )
        else:
            raise ValueError(f"不支持的浏览器: {cls.BROWSER}")
        
        cls.driver.implicitly_wait(10)
        cls.wait = WebDriverWait(cls.driver, 30)  # 故障期间等待时间更长
        cls.performance_data = []
    
    @classmethod
    def teardown_class(cls):
        """保存数据并关闭浏览器"""
        if cls.performance_data:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'selenium_chaos_{cls.CHAOS_TYPE}_{cls.BROWSER}_{timestamp}.json'
            filepath = os.path.join(os.path.dirname(__file__), filename)
            
            report = {
                'test_type': 'chaos_resilience',
                'chaos_type': cls.CHAOS_TYPE,
                'browser': cls.BROWSER,
                'frontend_url': cls.BASE_URL,
                'timestamp': datetime.now().isoformat(),
                'summary': cls._generate_summary(),
                'details': cls.performance_data
            }
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            print(f"\n[OK] Chaos 测试数据已保存: {filename}")
        
        cls.driver.quit()
        print("[OK] 浏览器已关闭")
    
    @classmethod
    def _generate_summary(cls):
        """生成测试摘要"""
        total = len(cls.performance_data)
        passed = sum(1 for m in cls.performance_data if m.get('status') == 'success')
        failed = total - passed
        
        slow_ops = [m for m in cls.performance_data 
                    if m.get('duration_ms', 0) > cls.THRESHOLD_RESPONSE * 1000]
        
        return {
            'total_tests': total,
            'passed': passed,
            'failed': failed,
            'pass_rate': f"{passed/total*100:.1f}%" if total > 0 else "N/A",
            'slow_operations': len(slow_ops),
            'slow_operations_list': [m['operation'] for m in slow_ops]
        }
    
    def _record(self, operation, duration, status='success', detail=''):
        """记录性能指标"""
        metric = {
            'chaos_type': self.CHAOS_TYPE,
            'browser': self.BROWSER,
            'operation': operation,
            'duration_ms': round(duration * 1000, 2),
            'status': status,
            'detail': detail,
            'timestamp': datetime.now().isoformat()
        }
        self.performance_data.append(metric)
        
        # 标记慢操作
        is_slow = duration > self.THRESHOLD_RESPONSE
        slow_tag = " [SLOW!]" if is_slow else ""
        print(f"  [{self.BROWSER}] {operation}: {metric['duration_ms']}ms - {status}{slow_tag}")
    
    # ============ 核心功能测试 ============
    
    def test_01_page_load_under_chaos(self):
        """故障期间首页加载测试"""
        print(f"\n[Chaos 测试 1] 首页加载（{self.CHAOS_TYPE}）")
        
        start = time.time()
        try:
            self.driver.get(self.BASE_URL)
            self.wait.until(EC.presence_of_all_elements_located((By.CLASS_NAME, "hot-product-card")))
            duration = time.time() - start
            
            products = self.driver.find_elements(By.CLASS_NAME, "hot-product-card")
            is_slow = duration > self.THRESHOLD_PAGE_LOAD
            
            self._record('chaos_首页加载', duration,
                         'success' if not is_slow else 'degraded',
                         f"找到 {len(products)} 个商品")
            
            assert len(products) > 0, "商品列表未加载"
            
        except TimeoutException:
            duration = time.time() - start
            self._record('chaos_首页加载', duration, 'failed', '加载超时')
            pytest.fail(f"首页加载超时（{duration:.1f}s），故障可能影响了前端服务")
    
    def test_02_product_browse_under_chaos(self):
        """故障期间商品浏览测试"""
        print(f"\n[Chaos 测试 2] 商品浏览（{self.CHAOS_TYPE}）")
        
        self.driver.get(self.BASE_URL)
        self.wait.until(EC.presence_of_all_elements_located((By.CLASS_NAME, "hot-product-card")))
        
        first_product = self.wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, ".hot-product-card a"))
        )
        
        start = time.time()
        try:
            first_product.click()
            self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, "product-price")))
            duration = time.time() - start
            
            price = self.driver.find_element(By.CLASS_NAME, "product-price").text
            self._record('chaos_商品浏览', duration, 'success', f"价格: {price}")
            
        except TimeoutException:
            duration = time.time() - start
            self._record('chaos_商品浏览', duration, 'failed', '页面加载超时')
            pytest.fail(f"商品详情页加载超时（{duration:.1f}s）")
    
    def test_03_add_to_cart_under_chaos(self):
        """故障期间添加购物车测试"""
        print(f"\n[Chaos 测试 3] 添加购物车（{self.CHAOS_TYPE}）")
        
        # 进入商品详情页
        self.driver.get(self.BASE_URL)
        self.wait.until(EC.presence_of_all_elements_located((By.CLASS_NAME, "hot-product-card")))
        
        first_product = self.wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, ".hot-product-card a"))
        )
        first_product.click()
        self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, "product-price")))
        
        add_button = self.wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button[type='submit']"))
        )
        
        start = time.time()
        try:
            add_button.click()
            self.wait.until(EC.url_contains("/cart"))
            duration = time.time() - start
            
            cart_items = self.driver.find_elements(By.CLASS_NAME, "cart-summary-item-row")
            self._record('chaos_添加购物车', duration, 'success',
                         f"购物车商品数: {len(cart_items)}")
            
            assert len(cart_items) > 0, "购物车为空"
            
        except TimeoutException:
            duration = time.time() - start
            self._record('chaos_添加购物车', duration, 'failed', '操作超时')
            pytest.fail(f"添加购物车超时（{duration:.1f}s）")
    
    def test_04_place_order_under_chaos(self):
        """故障期间下单测试 - 验证核心交易流程"""
        print(f"\n[Chaos 测试 4] 提交订单（{self.CHAOS_TYPE}）")
        
        # 准备购物车
        self.driver.get(self.BASE_URL)
        self.wait.until(EC.presence_of_all_elements_located((By.CLASS_NAME, "hot-product-card")))
        
        first_product = self.wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, ".hot-product-card a"))
        )
        first_product.click()
        self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, "product-price")))
        
        self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        self.wait.until(EC.url_contains("/cart"))
        
        # 填写表单并提交
        start = time.time()
        try:
            from selenium.webdriver.support.ui import Select
            
            self.driver.find_element(By.NAME, "email").clear()
            self.driver.find_element(By.NAME, "email").send_keys("test@example.com")
            self.driver.find_element(By.NAME, "street_address").clear()
            self.driver.find_element(By.NAME, "street_address").send_keys("1600 Amphitheatre Parkway")
            self.driver.find_element(By.NAME, "zip_code").clear()
            self.driver.find_element(By.NAME, "zip_code").send_keys("94043")
            self.driver.find_element(By.NAME, "city").clear()
            self.driver.find_element(By.NAME, "city").send_keys("Mountain View")
            self.driver.find_element(By.NAME, "state").clear()
            self.driver.find_element(By.NAME, "state").send_keys("CA")
            self.driver.find_element(By.NAME, "country").clear()
            self.driver.find_element(By.NAME, "country").send_keys("United States")
            self.driver.find_element(By.NAME, "credit_card_number").clear()
            self.driver.find_element(By.NAME, "credit_card_number").send_keys("4432801561520454")
            Select(self.driver.find_element(By.NAME, "credit_card_expiration_month")).select_by_value("12")
            Select(self.driver.find_element(By.NAME, "credit_card_expiration_year")).select_by_value("2027")
            self.driver.find_element(By.NAME, "credit_card_cvv").clear()
            self.driver.find_element(By.NAME, "credit_card_cvv").send_keys("672")
            
            self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
            self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "h3")))
            duration = time.time() - start
            
            confirmation = self.driver.find_element(By.TAG_NAME, "h3").text
            is_success = "complete" in confirmation.lower()
            
            self._record('chaos_提交订单', duration,
                         'success' if is_success else 'failed',
                         confirmation)
            
            assert is_success, f"订单提交失败: {confirmation}"
            
        except TimeoutException:
            duration = time.time() - start
            self._record('chaos_提交订单', duration, 'failed', '操作超时')
            pytest.fail(f"订单提交超时（{duration:.1f}s），故障可能影响了后端服务")
    
    def test_05_error_handling(self):
        """验证错误处理 - 页面是否显示友好错误信息"""
        print(f"\n[Chaos 测试 5] 错误处理检查（{self.CHAOS_TYPE}）")
        
        self.driver.get(self.BASE_URL)
        
        try:
            self.wait.until(EC.presence_of_all_elements_located((By.CLASS_NAME, "hot-product-card")))
            
            # 检查页面是否包含错误信息
            page_text = self.driver.find_element(By.TAG_NAME, "body").text
            error_keywords = ['error', 'fail', 'exception', 'timeout', 'unavailable']
            has_error = any(kw in page_text.lower() for kw in error_keywords)
            
            self._record('chaos_错误处理', 0,
                         'failed' if has_error else 'success',
                         '发现错误信息' if has_error else '页面正常')
            
        except TimeoutException:
            self._record('chaos_错误处理', 0, 'failed', '页面加载超时')
            pytest.fail("页面加载超时，系统可能已不可用")


if __name__ == "__main__":
    pytest.main([__file__, '-v'])
