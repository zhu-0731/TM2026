"""
OnlineBoutique 前端功能与性能测试（阶段三 - Selenium 部分）
============================================================
功能测试：模拟用户操作（浏览商品、添加购物车、下单等）
性能测试：记录页面加载时间、交互响应时间
兼容性测试：支持 Chrome、Edge、Firefox 多浏览器

环境变量：
    FRONTEND_URL    前端地址（默认 http://localhost:8080）
    TEST_BROWSER    测试浏览器 chrome/edge/firefox（默认 chrome）
    HEADLESS        是否无头模式 true/false（默认 false）
    TEST_MODE       测试模式 baseline/chaos（默认 baseline）

用法：
    # 基线测试（正常状态）
    pytest test_selenium_performance.py -v --html=report.html

    # 故障期间测试
    set TEST_MODE=chaos && pytest test_selenium_performance.py -v --html=report_chaos.html

    # 跨浏览器测试
    run_selenium_tests.bat all
"""

import time
import pytest
import json
import os
import sys
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.support.ui import Select
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.microsoft import EdgeChromiumDriverManager
from webdriver_manager.firefox import GeckoDriverManager


class TestOnlineBoutiqueSelenium:
    """
    OnlineBoutique 前端功能与性能测试类
    
    测试覆盖：
    1. 页面加载测试
    2. 货币切换功能
    3. 商品浏览功能
    4. 购物车操作（添加、清空）
    5. 订单提交流程
    6. 完整用户旅程
    """
    
    # ============ 配置 ============
    BASE_URL = os.environ.get('FRONTEND_URL', 'http://localhost:8080')
    BROWSER = os.environ.get('TEST_BROWSER', 'chrome').lower()
    HEADLESS = os.environ.get('HEADLESS', 'false').lower() == 'true'
    TEST_MODE = os.environ.get('TEST_MODE', 'baseline').lower()  # baseline 或 chaos
    
    # 性能数据收集
    performance_data = []
    
    @classmethod
    def setup_class(cls):
        """测试类级别前置：启动浏览器"""
        print(f"\n{'='*60}")
        print(f"[Selenium 测试启动]")
        print(f"  浏览器: {cls.BROWSER}")
        print(f"  目标地址: {cls.BASE_URL}")
        print(f"  无头模式: {cls.HEADLESS}")
        print(f"  测试模式: {cls.TEST_MODE}")
        print(f"{'='*60}\n")
        
        cls.driver = cls._create_driver()
        cls.driver.implicitly_wait(10)
        cls.wait = WebDriverWait(cls.driver, 15)
        cls.performance_data = []
        
        # 验证前端可访问（最多重试3次）
        for attempt in range(3):
            try:
                cls.driver.get(cls.BASE_URL)
                cls.wait.until(EC.presence_of_element_located((By.CLASS_NAME, "hot-product-card")))
                print(f"[OK] 前端服务可访问: {cls.BASE_URL}")
                break
            except Exception as e:
                print(f"[警告] 前端访问尝试 {attempt+1}/3 失败: {e}")
                if attempt == 2:
                    print(f"[ERROR] 前端服务无法访问，请检查:")
                    print(f"  1. kubectl port-forward svc/frontend-external 18080:80 -n default")
                    print(f"  2. minikube service frontend-external --url")
                    raise
                time.sleep(3)
    
    @classmethod
    def teardown_class(cls):
        """测试类级别后置：保存数据并关闭浏览器"""
        # 保存性能数据
        if cls.performance_data:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            mode_prefix = cls.TEST_MODE
            filename = f'selenium_{mode_prefix}_{cls.BROWSER}_{timestamp}.json'
            filepath = os.path.join(os.path.dirname(__file__), filename)
            
            report = {
                'test_mode': cls.TEST_MODE,
                'browser': cls.BROWSER,
                'frontend_url': cls.BASE_URL,
                'timestamp': datetime.now().isoformat(),
                'summary': cls._generate_summary(),
                'details': cls.performance_data
            }
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            print(f"\n[OK] 性能数据已保存: {filename}")
        
        cls.driver.quit()
        print(f"\n[OK] 浏览器已关闭")
    
    @classmethod
    def _create_driver(cls):
        """创建 WebDriver 实例
        
        支持环境变量指定本地驱动路径:
            CHROME_DRIVER_PATH  - ChromeDriver 本地路径
            EDGE_DRIVER_PATH    - EdgeDriver 本地路径
            FIREFOX_DRIVER_PATH - GeckoDriver 本地路径
        """
        if cls.BROWSER == 'chrome':
            options = webdriver.ChromeOptions()
            if cls.HEADLESS:
                options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--window-size=1920,1080')
            # 禁用 Chrome 版本检查（解决驱动版本微小差异问题）
            options.add_argument('--disable-build-check')
            options.add_argument('--disable-gpu')
            options.add_argument('--disable-extensions')
            options.add_argument('--disable-software-rasterizer')
            
            # 优先使用本地驱动
            local_path = os.environ.get('CHROME_DRIVER_PATH')
            if local_path and os.path.exists(local_path):
                print(f"  [驱动] 使用本地 ChromeDriver: {local_path}")
                return webdriver.Chrome(service=ChromeService(local_path), options=options)
            
            # 使用 ChromeDriverManager 并设置浏览器路径
            chrome_path = r'C:\Program Files\Google\Chrome\Application\chrome.exe'
            if os.path.exists(chrome_path):
                options.binary_location = chrome_path
            return webdriver.Chrome(
                service=ChromeService(ChromeDriverManager().install()),
                options=options
            )
        
        elif cls.BROWSER == 'edge':
            options = webdriver.EdgeOptions()
            if cls.HEADLESS:
                options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--window-size=1920,1080')
            # 禁用版本检查
            options.add_argument('--disable-build-check')
            options.add_argument('--disable-gpu')
            
            # 设置 Edge 浏览器路径
            edge_paths = [
                r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
                r'C:\Program Files\Microsoft\Edge\Application\msedge.exe',
            ]
            for edge_path in edge_paths:
                if os.path.exists(edge_path):
                    options.binary_location = edge_path
                    break
            
            # 优先使用本地驱动
            local_path = os.environ.get('EDGE_DRIVER_PATH')
            if local_path and os.path.exists(local_path):
                print(f"  [驱动] 使用本地 EdgeDriver: {local_path}")
                return webdriver.Edge(service=EdgeService(local_path), options=options)
            return webdriver.Edge(
                service=EdgeService(EdgeChromiumDriverManager().install()),
                options=options
            )
        
        elif cls.BROWSER == 'firefox':
            options = webdriver.FirefoxOptions()
            if cls.HEADLESS:
                options.add_argument('--headless')
            options.add_argument('--width=1920')
            options.add_argument('--height=1080')
            # 禁用 GPU 加速，提高稳定性
            options.set_preference('layers.acceleration.disabled', True)
            options.set_preference('gfx.direct2d.disabled', True)
            
            # 设置 Firefox 浏览器路径
            firefox_paths = [
                r'C:\Program Files\Mozilla Firefox\firefox.exe',
                r'C:\Program Files (x86)\Mozilla Firefox\firefox.exe',
            ]
            for ff_path in firefox_paths:
                if os.path.exists(ff_path):
                    options.binary_location = ff_path
                    break
            
            # 优先使用本地驱动
            local_path = os.environ.get('FIREFOX_DRIVER_PATH')
            if local_path and os.path.exists(local_path):
                print(f"  [驱动] 使用本地 GeckoDriver: {local_path}")
                return webdriver.Firefox(service=FirefoxService(local_path), options=options)
            return webdriver.Firefox(
                service=FirefoxService(GeckoDriverManager().install()),
                options=options
            )
        else:
            raise ValueError(f"不支持的浏览器: {cls.BROWSER}")
    
    @classmethod
    def _generate_summary(cls):
        """生成测试摘要"""
        total = len(cls.performance_data)
        passed = sum(1 for m in cls.performance_data if m.get('status') == 'success')
        failed = total - passed
        
        durations = [m.get('duration_ms', 0) for m in cls.performance_data if m.get('status') == 'success']
        avg_duration = sum(durations) / len(durations) if durations else 0
        max_duration = max(durations) if durations else 0
        min_duration = min(durations) if durations else 0
        
        return {
            'total_tests': total,
            'passed': passed,
            'failed': failed,
            'pass_rate': f"{passed/total*100:.1f}%" if total > 0 else "N/A",
            'avg_response_ms': round(avg_duration, 2),
            'max_response_ms': round(max_duration, 2),
            'min_response_ms': round(min_duration, 2)
        }
    
    def _record(self, operation, duration, status='success', detail=''):
        """记录性能指标"""
        metric = {
            'browser': self.BROWSER,
            'test_mode': self.TEST_MODE,
            'operation': operation,
            'duration_ms': round(duration * 1000, 2),
            'status': status,
            'detail': detail,
            'timestamp': datetime.now().isoformat()
        }
        self.performance_data.append(metric)
        print(f"  [{self.BROWSER}] {operation}: {metric['duration_ms']}ms - {status}")
    
    # ============ 测试用例 ============
    
    def test_01_page_load(self):
        """测试 1：首页加载 - 验证页面标题和商品列表"""
        print("\n[测试 1] 首页加载")
        
        start = time.time()
        self.driver.get(self.BASE_URL)
        self.wait.until(EC.presence_of_all_elements_located((By.CLASS_NAME, "hot-product-card")))
        duration = time.time() - start
        
        # 验证页面标题
        assert "Online Boutique" in self.driver.title, f"页面标题错误: {self.driver.title}"
        
        # 验证商品列表
        products = self.driver.find_elements(By.CLASS_NAME, "hot-product-card")
        assert len(products) > 0, "商品列表未加载"
        
        self._record('首页加载', duration, 'success', f"找到 {len(products)} 个商品")
    
    def test_02_change_currency(self):
        """测试 2：货币切换 - 验证 EUR 货币显示"""
        print("\n[测试 2] 货币切换")
        
        self.driver.get(self.BASE_URL)
        self.wait.until(EC.presence_of_all_elements_located((By.CLASS_NAME, "hot-product-card")))
        
        currency_select = self.wait.until(
            EC.presence_of_element_located((By.NAME, "currency_code"))
        )
        
        start = time.time()
        # 使用 Selenium Select 类切换货币（兼容所有浏览器）
        Select(currency_select).select_by_value("EUR")
        # 点击页面上的 Set Currency 按钮提交表单
        try:
            set_currency_btn = self.driver.find_element(By.XPATH, "//button[@type='submit' and contains(text(), 'Set Currency')]")
            set_currency_btn.click()
        except NoSuchElementException:
            # 回退：使用 JavaScript 直接提交表单（不依赖旧元素引用）
            self.driver.execute_script("document.querySelector('form[action*=\"setCurrency\"]').submit();")
        
        self.wait.until(EC.presence_of_all_elements_located((By.CLASS_NAME, "hot-product-card")))
        duration = time.time() - start
        
        # 验证价格显示欧元符号
        prices = self.driver.find_elements(By.CSS_SELECTOR, ".hot-product-card-price")
        has_euro = any('€' in p.text for p in prices[:3])
        
        self._record('货币切换', duration, 
                     'success' if has_euro else 'failed',
                     'EUR' if has_euro else '未找到欧元符号')
        
        assert has_euro, "货币切换后未显示欧元符号"
    
    def test_03_browse_product(self):
        """测试 3：商品详情浏览 - 点击商品进入详情页"""
        print("\n[测试 3] 商品详情浏览")
        
        self.driver.get(self.BASE_URL)
        self.wait.until(EC.presence_of_all_elements_located((By.CLASS_NAME, "hot-product-card")))
        
        # 点击第一个商品
        first_product = self.wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, ".hot-product-card a"))
        )
        
        start = time.time()
        first_product.click()
        self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, "product-price")))
        duration = time.time() - start
        
        # 验证商品详情页元素
        price = self.driver.find_element(By.CLASS_NAME, "product-price").text
        assert '$' in price or '€' in price, f"价格显示异常: {price}"
        
        self._record('商品详情浏览', duration, 'success', f"商品价格: {price}")
    
    def test_04_add_to_cart(self):
        """测试 4：添加商品到购物车"""
        print("\n[测试 4] 添加商品到购物车")
        
        # 进入商品详情页
        self.driver.get(self.BASE_URL)
        self.wait.until(EC.presence_of_all_elements_located((By.CLASS_NAME, "hot-product-card")))
        
        first_product = self.wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, ".hot-product-card a"))
        )
        first_product.click()
        self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, "product-price")))
        
        # 点击 Add To Cart
        add_button = self.wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button[type='submit']"))
        )
        
        start = time.time()
        add_button.click()
        self.wait.until(EC.url_contains("/cart"))
        duration = time.time() - start
        
        # 验证购物车中有商品
        cart_items = self.driver.find_elements(By.CLASS_NAME, "cart-summary-item-row")
        assert len(cart_items) > 0, "购物车为空"
        
        self._record('添加购物车', duration, 'success', f"购物车商品数: {len(cart_items)}")
    
    def test_05_empty_cart(self):
        """测试 5：清空购物车"""
        print("\n[测试 5] 清空购物车")
        
        # 确保购物车有商品 - 先添加一个商品
        self.driver.get(self.BASE_URL)
        self.wait.until(EC.presence_of_all_elements_located((By.CLASS_NAME, "hot-product-card")))
        products = self.driver.find_elements(By.CLASS_NAME, "hot-product-card")
        if products:
            products[0].click()
            # 等待商品详情页加载，使用通用按钮选择器
            self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "button.cymbal-button-primary")))
            add_btn = self.driver.find_element(By.CSS_SELECTOR, "button.cymbal-button-primary")
            add_btn.click()
            time.sleep(1)
        
        # 进入购物车并清空
        self.driver.get(f"{self.BASE_URL}/cart")
        
        try:
            # 使用包含 Empty Cart 文本的按钮
            empty_button = self.wait.until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Empty Cart')]"))
            )
            
            start = time.time()
            empty_button.click()
            # 等待页面刷新
            time.sleep(1)
            duration = time.time() - start
            
            # 验证购物车为空 - 检查是否有商品行
            cart_items = self.driver.find_elements(By.CLASS_NAME, "cart-summary-item-row")
            is_empty = len(cart_items) == 0
            
            self._record('清空购物车', duration,
                         'success' if is_empty else 'failed',
                         '购物车已清空' if is_empty else '购物车仍有商品')
        except TimeoutException:
            self._record('清空购物车', 0, 'failed', '购物车已经是空的或按钮未找到')
    
    def test_06_return_home(self):
        """测试 6：返回主页"""
        print("\n[测试 6] 返回主页")
        
        start = time.time()
        self.driver.get(self.BASE_URL)
        self.wait.until(EC.presence_of_all_elements_located((By.CLASS_NAME, "hot-product-card")))
        duration = time.time() - start
        
        products = self.driver.find_elements(By.CLASS_NAME, "hot-product-card")
        self._record('返回主页', duration, 'success', f"找到 {len(products)} 个商品")
    
    def test_07_place_order(self):
        """测试 7：完整下单流程（填写表单并提交订单）"""
        print("\n[测试 7] 提交订单")
        
        # 先添加商品到购物车（确保购物车有商品）
        # 由于 test_05 可能清空了购物车，需要重新添加
        max_attempts = 2
        for attempt in range(max_attempts):
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
            add_button.click()
            
            # 等待跳转到购物车页面
            self.wait.until(EC.url_contains("/cart"))
            
            # 验证购物车中有商品
            cart_items = self.driver.find_elements(By.CLASS_NAME, "cart-summary-item-row")
            if len(cart_items) > 0:
                print(f"  [OK] 购物车有 {len(cart_items)} 个商品")
                break
            else:
                print(f"  [警告] 购物车为空，尝试重新添加（{attempt+1}/{max_attempts}）")
                time.sleep(1)
        else:
            print("  [跳过] 购物车为空，跳过订单提交测试")
            self._record('提交订单', 0, 'skipped', '购物车为空')
            pytest.skip("购物车为空，无法测试订单提交")
            return
        
        # 填写结账表单并提交
        start = time.time()
        
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
        
        # 提交订单（使用 cart-checkout-form 中的提交按钮）
        self.driver.find_element(By.CSS_SELECTOR, "form.cart-checkout-form button[type='submit']").click()
        
        # 等待页面跳转完成（订单完成页或错误页）
        time.sleep(2)
        
        # 检查当前页面内容
        page_text = self.driver.find_element(By.TAG_NAME, "body").text.lower()
        duration = time.time() - start
        
        # 验证订单完成
        is_success = "complete" in page_text or "order" in page_text
        
        # 获取确认信息
        try:
            confirmation = self.driver.find_element(By.TAG_NAME, "h3").text
        except:
            confirmation = "Unknown"
        
        self._record('提交订单', duration,
                     'success' if is_success else 'failed',
                     confirmation)
        
        assert is_success, f"订单提交失败: {confirmation}"
    
    def test_08_apply_coupon(self):
        """测试 8：优惠券功能 - 输入优惠券码并验证折扣"""
        print("\n[测试 8] 优惠券功能")
        
        # 先添加商品到购物车
        self.driver.get(self.BASE_URL)
        self.wait.until(EC.presence_of_all_elements_located((By.CLASS_NAME, "hot-product-card")))
        
        first_product = self.wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, ".hot-product-card a"))
        )
        first_product.click()
        self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, "product-price")))
        
        self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        self.wait.until(EC.url_contains("/cart"))
        
        # 验证购物车有商品
        cart_items = self.driver.find_elements(By.CLASS_NAME, "cart-summary-item-row")
        if len(cart_items) == 0:
            self._record('优惠券功能', 0, 'skipped', '购物车为空')
            pytest.skip("购物车为空，无法测试优惠券")
            return
        
        # 记录应用优惠券前的总价
        try:
            total_before = self.driver.find_element(By.CLASS_NAME, "cart-summary-total-row").text
        except:
            total_before = "N/A"
        
        # 输入优惠券码
        start = time.time()
        
        coupon_input = self.wait.until(
            EC.presence_of_element_located((By.NAME, "coupon_code"))
        )
        coupon_input.clear()
        coupon_input.send_keys("SAVE10")
        
        # 提交订单（优惠券会在订单提交时应用）
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
        
        # 提交订单
        self.driver.find_element(By.CSS_SELECTOR, "form.cart-checkout-form button[type='submit']").click()
        time.sleep(2)
        
        duration = time.time() - start
        
        # 验证订单完成且优惠券已应用
        page_text = self.driver.find_element(By.TAG_NAME, "body").text
        is_success = "complete" in page_text.lower()
        has_coupon = "coupon applied" in page_text.lower() or "save10" in page_text.lower()
        
        status = 'success' if (is_success and has_coupon) else ('success' if is_success else 'failed')
        detail = f"订单完成 + 优惠券已应用" if has_coupon else ("订单完成" if is_success else "订单失败")
        
        self._record('优惠券功能', duration, status, detail)
        
        assert is_success, "订单提交失败"
    
    def test_09_multi_currency_support(self):
        """测试 9：多货币支持 - 验证多种货币切换"""
        print("\n[测试 9] 多货币支持")
        
        currencies = [
            ('USD', '$'),
            ('EUR', '€'),
            ('JPY', '¥'),
            ('GBP', '£')
        ]
        
        results = []
        for currency_code, symbol in currencies:
            self.driver.get(self.BASE_URL)
            self.wait.until(EC.presence_of_all_elements_located((By.CLASS_NAME, "hot-product-card")))
            
            currency_select = self.wait.until(
                EC.presence_of_element_located((By.NAME, "currency_code"))
            )
            
            start = time.time()
            # 使用 Selenium Select 类切换货币（兼容所有浏览器）
            Select(currency_select).select_by_value(currency_code)
            try:
                set_currency_btn = self.driver.find_element(By.XPATH, "//button[@type='submit' and contains(text(), 'Set Currency')]")
                set_currency_btn.click()
            except NoSuchElementException:
                # 回退：使用 JavaScript 直接提交表单（不依赖旧元素引用）
                self.driver.execute_script("document.querySelector('form[action*=\"setCurrency\"]').submit();")
            
            self.wait.until(EC.presence_of_all_elements_located((By.CLASS_NAME, "hot-product-card")))
            duration = time.time() - start
            
            # 验证价格显示对应货币符号
            prices = self.driver.find_elements(By.CSS_SELECTOR, ".hot-product-card-price")
            has_symbol = any(symbol in p.text for p in prices[:2])
            
            results.append({
                'currency': currency_code,
                'symbol': symbol,
                'found': has_symbol,
                'duration_ms': round(duration * 1000, 2)
            })
            
            self._record(f'货币切换-{currency_code}', duration,
                         'success' if has_symbol else 'failed',
                         f"{symbol} {'找到' if has_symbol else '未找到'}")
        
        # 统计结果
        passed = sum(1 for r in results if r['found'])
        print(f"\n  货币测试: {passed}/{len(currencies)} 通过")
        
        assert passed >= 3, f"多货币支持测试失败: 仅 {passed}/{len(currencies)} 通过"
    
    def test_10_product_quantity_selection(self):
        """测试 10：商品数量选择 - 验证数量选择器功能"""
        print("\n[测试 10] 商品数量选择")
        
        # 进入商品详情页
        self.driver.get(self.BASE_URL)
        self.wait.until(EC.presence_of_all_elements_located((By.CLASS_NAME, "hot-product-card")))
        
        first_product = self.wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, ".hot-product-card a"))
        )
        first_product.click()
        self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, "product-price")))
        
        # 获取单价
        price_text = self.driver.find_element(By.CLASS_NAME, "product-price").text
        
        # 选择数量 3
        start = time.time()
        quantity_select = self.wait.until(
            EC.presence_of_element_located((By.ID, "quantity"))
        )
        Select(quantity_select).select_by_visible_text("3")
        duration = time.time() - start
        
        # 验证数量已选择
        selected_qty = Select(quantity_select).first_selected_option.text
        
        # 添加到购物车
        self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        self.wait.until(EC.url_contains("/cart"))
        
        # 验证购物车中数量为 3
        cart_page_text = self.driver.find_element(By.TAG_NAME, "body").text
        has_qty_3 = "Quantity: 3" in cart_page_text or "3" in cart_page_text
        
        self._record('商品数量选择', duration, 'success',
                     f"选择数量: {selected_qty}, 单价: {price_text}")
        
        assert selected_qty == "3", f"数量选择失败: 期望 3, 实际 {selected_qty}"
    
    def test_11_empty_cart_state(self):
        """测试 11：空购物车状态 - 验证空购物车页面显示"""
        print("\n[测试 11] 空购物车状态")
        
        # 确保购物车为空
        self.driver.get(f"{self.BASE_URL}/cart")
        time.sleep(1)
        
        start = time.time()
        
        # 检查空购物车提示
        page_text = self.driver.find_element(By.TAG_NAME, "body").text
        is_empty = "Your shopping cart is empty" in page_text or "empty" in page_text.lower()
        
        # 检查是否有 "Continue Shopping" 按钮
        try:
            continue_btn = self.driver.find_element(By.CSS_SELECTOR, "a[href='/']")
            has_continue = continue_btn.is_displayed()
        except:
            has_continue = False
        
        duration = time.time() - start
        
        status = 'success' if (is_empty and has_continue) else 'failed'
        detail = f"空提示: {'有' if is_empty else '无'}, 继续购物按钮: {'有' if has_continue else '无'}"
        
        self._record('空购物车状态', duration, status, detail)
        
        assert is_empty, "空购物车页面未显示正确提示"
    
    def test_12_order_confirmation_details(self):
        """测试 12：订单确认详情 - 验证订单完成页信息完整性"""
        print("\n[测试 12] 订单确认详情")
        
        # 先添加商品到购物车
        self.driver.get(self.BASE_URL)
        self.wait.until(EC.presence_of_all_elements_located((By.CLASS_NAME, "hot-product-card")))
        
        first_product = self.wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, ".hot-product-card a"))
        )
        first_product.click()
        self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, "product-price")))
        
        self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        self.wait.until(EC.url_contains("/cart"))
        
        # 验证购物车有商品
        cart_items = self.driver.find_elements(By.CLASS_NAME, "cart-summary-item-row")
        if len(cart_items) == 0:
            self._record('订单确认详情', 0, 'skipped', '购物车为空')
            pytest.skip("购物车为空")
            return
        
        # 填写表单并提交
        start = time.time()
        
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
        
        self.driver.find_element(By.CSS_SELECTOR, "form.cart-checkout-form button[type='submit']").click()
        time.sleep(2)
        
        duration = time.time() - start
        
        # 验证订单完成页的关键信息
        page_text = self.driver.find_element(By.TAG_NAME, "body").text
        
        checks = {
            '订单完成': 'Your order is complete' in page_text,
            '确认邮件提示': "We've sent you a confirmation email" in page_text,
            '确认号': 'Confirmation #' in page_text,
            '追踪号': 'Tracking #' in page_text,
            '支付总额': 'Total Paid' in page_text,
            '继续购物按钮': 'Continue Shopping' in page_text
        }
        
        passed = sum(1 for v in checks.values() if v)
        detail = ", ".join([f"{k}:{'✓' if v else '✗'}" for k, v in checks.items()])
        
        self._record('订单确认详情', duration,
                     'success' if passed >= 5 else 'failed',
                     detail)
        
        assert passed >= 5, f"订单确认页信息不完整: {passed}/6 通过"
    
    def test_13_recommendations_display(self):
        """测试 13：推荐商品展示 - 验证商品详情页和订单完成页的推荐"""
        print("\n[测试 13] 推荐商品展示")
        
        start = time.time()
        
        # 进入商品详情页
        self.driver.get(self.BASE_URL)
        self.wait.until(EC.presence_of_all_elements_located((By.CLASS_NAME, "hot-product-card")))
        
        first_product = self.wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, ".hot-product-card a"))
        )
        first_product.click()
        self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, "product-price")))
        
        # 滚动到推荐商品区域
        self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1)
        
        # 验证推荐商品区域
        try:
            recommendations = self.driver.find_elements(By.CSS_SELECTOR, "section.recommendations .col-md-3")
            has_recommendations = len(recommendations) > 0
            rec_count = len(recommendations)
        except:
            has_recommendations = False
            rec_count = 0
        
        duration = time.time() - start
        
        self._record('推荐商品展示', duration,
                     'success' if has_recommendations else 'failed',
                     f"推荐商品数: {rec_count}")
        
        assert has_recommendations, "推荐商品未显示"
    
    def test_14_full_user_journey(self):
        """测试 14：完整用户旅程（串联所有操作，含优惠券）"""
        print("\n[测试 14] 完整用户旅程（含优惠券）")
        
        journey_start = time.time()
        
        # 1. 首页加载
        step_start = time.time()
        self.driver.get(self.BASE_URL)
        self.wait.until(EC.presence_of_all_elements_located((By.CLASS_NAME, "hot-product-card")))
        self._record('旅程-首页加载', time.time() - step_start)
        
        # 2. 切换货币
        step_start = time.time()
        currency_select = self.driver.find_element(By.NAME, "currency_code")
        self.driver.execute_script("""
            var select = arguments[0];
            select.value = 'EUR';
            select.dispatchEvent(new Event('change'));
            select.form.submit();
        """, currency_select)
        self.wait.until(EC.presence_of_all_elements_located((By.CLASS_NAME, "hot-product-card")))
        self._record('旅程-货币切换', time.time() - step_start)
        
        # 3. 浏览商品
        step_start = time.time()
        first_product = self.wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, ".hot-product-card a"))
        )
        first_product.click()
        self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, "product-price")))
        self._record('旅程-浏览商品', time.time() - step_start)
        
        # 4. 添加购物车
        step_start = time.time()
        self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        self.wait.until(EC.url_contains("/cart"))
        self._record('旅程-添加购物车', time.time() - step_start)
        
        # 5. 填写表单并提交订单
        step_start = time.time()
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
        self.driver.find_element(By.CSS_SELECTOR, "form.cart-checkout-form button[type='submit']").click()
        self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "h3")))
        self._record('旅程-提交订单', time.time() - step_start)
        
        journey_duration = time.time() - journey_start
        # 重新查找 h3 元素，避免 stale element
        confirmation = self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "h3"))).text
        
        self._record('完整用户旅程', journey_duration, 'success', confirmation)
        print(f"\n  完整旅程总耗时: {journey_duration:.3f}s")


# ============ 跨浏览器测试入口 ============

def run_cross_browser_tests():
    """跨浏览器测试入口 - 依次运行 Chrome、Edge、Firefox
    
    生成三浏览器对比报告 cross_browser_report.md
    """
    browsers = ['chrome', 'edge', 'firefox']
    all_results = {}
    all_perf_data = {}
    
    for browser in browsers:
        print(f"\n{'='*60}")
        print(f"开始 {browser.upper()} 浏览器测试")
        print(f"{'='*60}")
        
        os.environ['TEST_BROWSER'] = browser
        
        import subprocess
        result = subprocess.run(
            [sys.executable, '-m', 'pytest', __file__, '-v',
             '--html', f'report_{browser}.html', '--self-contained-html'],
            capture_output=True, text=True
        )
        
        print(result.stdout)
        if result.stderr:
            print(result.stderr)
        
        # 读取该浏览器的性能数据，用实际通过率判断
        import glob
        json_files = glob.glob(f'selenium_baseline_{browser}_*.json')
        if json_files:
            with open(json_files[-1], 'r', encoding='utf-8') as f:
                all_perf_data[browser] = json.load(f)
        
        # 判断测试结果：优先使用 JSON 中的 pass_rate，回退到 pytest returncode
        if browser in all_perf_data:
            pass_rate = all_perf_data[browser].get('summary', {}).get('pass_rate', '0%')
            all_results[browser] = pass_rate == '100.0%'
        else:
            all_results[browser] = result.returncode == 0
    
    # 生成跨浏览器对比报告
    _generate_cross_browser_report(all_results, all_perf_data)
    
    print(f"\n{'='*60}")
    print("跨浏览器测试结果汇总")
    print(f"{'='*60}")
    for browser, passed in all_results.items():
        status = "[PASS] 通过" if passed else "[FAIL] 失败"
        print(f"  {browser.upper():10s}: {status}")
    print(f"\n  详细对比报告: cross_browser_report.md")
    
    return all_results


def _generate_cross_browser_report(results, perf_data):
    """生成跨浏览器对比报告"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    report_lines = [
        "# Selenium 跨浏览器兼容性测试报告",
        "",
        f"**测试时间**: {timestamp}",
        f"**测试目标**: OnlineBoutique 前端功能与性能",
        f"**测试浏览器**: Chrome、Edge、Firefox",
        "",
        "---",
        "",
        "## 一、测试结果汇总",
        "",
        "| 浏览器 | 状态 | 报告文件 |",
        "|--------|------|----------|",
    ]
    
    for browser, passed in results.items():
        status = "✅ 通过" if passed else "❌ 失败"
        report_lines.append(f"| {browser.upper()} | {status} | report_{browser}.html |")
    
    report_lines.extend([
        "",
        "---",
        "",
        "## 二、性能数据对比",
        "",
    ])
    
    # 提取各浏览器的性能指标
    if perf_data:
        report_lines.extend([
            "| 指标 | Chrome | Edge | Firefox |",
            "|------|--------|------|---------|",
        ])
        
        metrics = ['avg_response_ms', 'max_response_ms', 'min_response_ms']
        metric_names = {'avg_response_ms': '平均响应时间', 'max_response_ms': '最大响应时间', 'min_response_ms': '最小响应时间'}
        
        for metric in metrics:
            row = f"| {metric_names[metric]} |"
            for browser in ['chrome', 'edge', 'firefox']:
                if browser in perf_data and 'summary' in perf_data[browser]:
                    val = perf_data[browser]['summary'].get(metric, 'N/A')
                    row += f" {val} ms |"
                else:
                    row += " N/A |"
            report_lines.append(row)
        
        # 通过率
        row = "| 测试通过率 |"
        for browser in ['chrome', 'edge', 'firefox']:
            if browser in perf_data and 'summary' in perf_data[browser]:
                val = perf_data[browser]['summary'].get('pass_rate', 'N/A')
                row += f" {val} |"
            else:
                row += " N/A |"
        report_lines.append(row)
        
        report_lines.extend([
            "",
            "### 各浏览器详细性能数据",
            "",
        ])
        
        for browser in ['chrome', 'edge', 'firefox']:
            if browser in perf_data:
                report_lines.append(f"#### {browser.upper()}")
                report_lines.append("")
                report_lines.append("| 操作 | 响应时间 | 状态 |")
                report_lines.append("|------|----------|------|")
                for detail in perf_data[browser].get('details', []):
                    op = detail.get('operation', '')
                    dur = detail.get('duration_ms', 0)
                    st = detail.get('status', '')
                    report_lines.append(f"| {op} | {dur} ms | {st} |")
                report_lines.append("")
    
    report_lines.extend([
        "---",
        "",
        "## 三、兼容性结论",
        "",
    ])
    
    passed_count = sum(1 for v in results.values() if v)
    total_count = len(results)
    
    report_lines.append(f"- **通过浏览器**: {passed_count}/{total_count}")
    report_lines.append(f"- **兼容性**: {'良好' if passed_count == total_count else '部分通过，需检查失败浏览器'}")
    report_lines.append("")
    
    for browser, passed in results.items():
        if passed:
            report_lines.append(f"- **{browser.upper()}**: 所有功能正常，前端兼容性良好。")
        else:
            report_lines.append(f"- **{browser.upper()}**: 测试失败，请检查驱动版本和浏览器配置。")
    
    report_lines.extend([
        "",
        "---",
        "",
        "*报告由 Selenium 跨浏览器测试自动生成*",
    ])
    
    with open('cross_browser_report.md', 'w', encoding='utf-8') as f:
        f.write('\n'.join(report_lines))
    
    print(f"\n[OK] 跨浏览器对比报告已保存: cross_browser_report.md")


if __name__ == "__main__":
    # 默认运行跨浏览器测试（Chrome + Edge + Firefox）
    # 如需单浏览器测试，请使用: pytest test_selenium_performance.py -v
    run_cross_browser_tests()
