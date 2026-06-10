# 基于 Selenium 的微服务前端性能测试指南

## 4.1 实验概述

### 4.1.1 实验目的

本实验依托已部署在本地 Minikube 容器集群中的 Online Boutique 微服务应用，旨在模拟真实用户行为并评估微服务系统在不同负载和交互场景下的性能和稳定性。

实验使用 Selenium 工具模拟用户实际行为并收集各个操作的响应时间以及页面加载时间，最后用 pytest 工具生成 HTML 报告。

### 4.1.2 实验环境

| 组件 | 版本 | 说明 |
|-----|------|------|
| Python | 3.x | 测试脚本运行环境 |
| Selenium | 4.15+ | 浏览器自动化工具 |
| pytest | 7.4+ | 测试框架 |
| pytest-html | 4.1+ | HTML 报告生成 |
| Chrome/Edge/Firefox | 最新版 | 测试浏览器 |
| webdriver-manager | 4.0+ | WebDriver 自动管理 |

---

## 4.2 测试方案设计

### 4.2.1 用户行为模拟

实验模拟用户的完整购物流程，设计了以下交互操作：

| 序号 | 操作 | 说明 | Selenium 实现 |
|-----|------|------|--------------|
| 1 | 页面加载 | 访问首页 | `driver.get()` |
| 2 | 货币更改 | 切换货币类型 | `ActionChains.click()` |
| 3 | 加载商品 | 点击商品进入详情页 | `ActionChains.click()` |
| 4 | 添加商品到购物车 | 点击 Add to Cart | `ActionChains.click()` |
| 5 | 清空购物车 | 点击 Empty Cart | `ActionChains.click()` |
| 6 | 返回主页 | 点击 Logo/主页链接 | `ActionChains.click()` |
| 7 | 填写邮箱 | 输入邮箱地址 | `ActionChains.send_keys()` |
| 8 | 提交订单 | 点击 Place Order | `ActionChains.click()` |

### 4.2.2 ActionChains 操作链封装

每个操作使用 `selenium.webdriver.common.action_chains` 提供的 `ActionChains` 封装为操作链：

```python
from selenium.webdriver.common.action_chains import ActionChains

# 创建 ActionChains 对象
actions = ActionChains(driver)

# 封装操作链：悬停 -> 点击 -> 输入
actions.move_to_element(element) \
       .click() \
       .send_keys("test@example.com") \
       .perform()
```

### 4.2.3 性能指标采集

每个操作记录以下指标：

| 指标 | 单位 | 说明 |
|-----|------|------|
| 操作耗时 | 毫秒 (ms) | 从操作开始到完成的时间 |
| 页面加载时间 | 毫秒 (ms) | DNS查询、TCP连接、DOM处理、总加载 |
| 操作状态 | success/failed | 操作是否成功 |
| 详细描述 | 字符串 | 操作结果描述 |

---

## 4.3 测试执行步骤

### 4.3.1 环境准备

```bash
# 1. 进入测试目录
cd tests/selenium

# 2. 安装依赖
pip install -r requirements.txt

# 3. 确认前端服务可访问
# 浏览器访问: http://localhost:8080
```

### 4.3.2 单浏览器测试

```bash
# Chrome 浏览器测试
set TEST_BROWSER=chrome
pytest test_selenium_performance.py -v --html=report_chrome.html --self-contained-html

# Edge 浏览器测试
set TEST_BROWSER=edge
pytest test_selenium_performance.py -v --html=report_edge.html --self-contained-html

# Firefox 浏览器测试
set TEST_BROWSER=firefox
pytest test_selenium_performance.py -v --html=report_firefox.html --self-contained-html
```

### 4.3.3 批量测试（所有浏览器）

```bash
# Windows
run_selenium_tests.bat all

# 或手动执行
set TEST_BROWSER=chrome
pytest test_selenium_performance.py -v --html=report_chrome.html --self-contained-html

set TEST_BROWSER=edge
pytest test_selenium_performance.py -v --html=report_edge.html --self-contained-html

set TEST_BROWSER=firefox
pytest test_selenium_performance.py -v --html=report_firefox.html --self-contained-html
```

### 4.3.4 无头模式测试（不显示浏览器窗口）

```bash
set HEADLESS=true
set TEST_BROWSER=chrome
pytest test_selenium_performance.py -v --html=report_headless.html --self-contained-html
```

---

## 4.4 测试用例说明

### 4.4.1 独立操作测试

| 测试用例 | 操作内容 | 验证点 |
|---------|---------|--------|
| test_01_page_load | 页面加载 | 页面标题、商品列表数量、加载时间 |
| test_02_change_currency | 货币更改 | 价格显示货币符号变化 |
| test_03_load_product | 加载商品 | 商品名称显示、页面跳转 |
| test_04_add_to_cart | 添加购物车 | 购物车页面跳转、商品存在 |
| test_05_empty_cart | 清空购物车 | 购物车为空 |
| test_06_return_home | 返回主页 | 主页加载、商品列表 |
| test_07_fill_email | 填写邮箱 | 输入框值验证 |
| test_08_place_order | 提交订单 | 订单完成页显示 |

### 4.4.2 完整用户旅程测试

| 测试用例 | 操作内容 | 验证点 |
|---------|---------|--------|
| test_09_full_user_journey | 完整购物流程 | 所有步骤串联、总耗时 |

完整用户旅程包含：
1. 页面加载
2. 更改货币
3. 加载商品
4. 添加购物车
5. 提交订单

---

## 4.5 测试报告

### 4.5.1 HTML 报告

pytest-html 生成的报告包含：

| 内容 | 说明 |
|-----|------|
| 测试摘要 | 通过/失败/跳过数量 |
| 测试详情 | 每个测试用例的执行时间、状态 |
| 环境信息 | Python 版本、浏览器版本、操作系统 |
| 日志输出 | 测试过程中的打印信息 |

### 4.5.2 性能数据文件

JSON 格式的性能数据：

```json
[
  {
    "browser": "chrome",
    "operation": "页面加载",
    "duration_ms": 1234.56,
    "status": "success",
    "detail": "找到 9 个商品",
    "timestamp": "2026-06-02T21:00:00.000000"
  }
]
```

### 4.5.3 报告文件位置

```
tests/selenium/
├── report_chrome.html          # Chrome 测试报告
├── report_edge.html            # Edge 测试报告
├── report_firefox.html         # Firefox 测试报告
├── selenium_performance_*.json # 性能数据文件
└── assets/                     # 报告资源文件
```

---

## 4.6 结合故障注入的测试

### 4.6.1 测试流程

```
1. 正常状态 Selenium 测试（基线）
   → 记录各操作响应时间

2. 注入 ChaosMesh 故障
   → kubectl apply -f chaos-experiments/xxx.yaml

3. 故障期间 Selenium 测试
   → 记录响应时间变化、功能可用性

4. 停止故障
   → kubectl delete -f chaos-experiments/xxx.yaml

5. 恢复后 Selenium 测试
   → 记录恢复情况
```

### 4.6.2 执行命令

```bash
# 1. 基线测试
set TEST_BROWSER=chrome
pytest test_selenium_performance.py -v --html=report_selenium_baseline.html

# 2. 注入故障
kubectl apply -f chaos-experiments/cpu-stress-frontend.yaml

# 3. 故障期间测试
pytest test_selenium_performance.py -v --html=report_selenium_chaos.html

# 4. 停止故障
kubectl delete -f chaos-experiments/cpu-stress-frontend.yaml

# 5. 恢复测试
pytest test_selenium_performance.py -v --html=report_selenium_recovery.html
```

---

## 4.7 论文可用数据

### 4.7.1 性能对比表格

| 操作 | Chrome (ms) | Edge (ms) | Firefox (ms) | 故障期间 (ms) | 变化率 |
|-----|------------|-----------|-------------|--------------|--------|
| 页面加载 | 【数据】 | 【数据】 | 【数据】 | 【数据】 | 【计算】 |
| 货币更改 | 【数据】 | 【数据】 | 【数据】 | 【数据】 | 【计算】 |
| 加载商品 | 【数据】 | 【数据】 | 【数据】 | 【数据】 | 【计算】 |
| 添加购物车 | 【数据】 | 【数据】 | 【数据】 | 【数据】 | 【计算】 |
| 提交订单 | 【数据】 | 【数据】 | 【数据】 | 【数据】 | 【计算】 |
| 完整旅程 | 【数据】 | 【数据】 | 【数据】 | 【数据】 | 【计算】 |

### 4.7.2 功能可用性表格

| 功能 | 正常状态 | 故障期间 | 恢复后 |
|-----|---------|---------|--------|
| 页面加载 | ✅ | 【记录】 | ✅ |
| 货币更改 | ✅ | 【记录】 | ✅ |
| 商品浏览 | ✅ | 【记录】 | ✅ |
| 购物车操作 | ✅ | 【记录】 | ✅ |
| 下单 | ✅ | 【记录】 | ✅ |

---

## 4.8 常见问题

### Q: WebDriver 下载失败

```bash
# 手动指定驱动路径
set CHROMEDRIVER_PATH=C:\path\to\chromedriver.exe
```

### Q: 元素定位失败

```bash
# 增加等待时间
set IMPLICIT_WAIT=20
```

### Q: 报告中文乱码

```bash
# 设置 UTF-8 编码
chcp 65001
```

---

## 4.9 文件结构

```
tests/selenium/
├── test_selenium_performance.py    # 主测试脚本
├── conftest.py                      # pytest 配置
├── requirements.txt                 # Python 依赖
├── run_selenium_tests.bat           # 批量测试脚本
├── report_chrome.html               # Chrome 测试报告
├── report_edge.html                 # Edge 测试报告
├── report_firefox.html              # Firefox 测试报告
└── selenium_performance_*.json      # 性能数据文件
```
