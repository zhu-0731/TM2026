# OnlineBoutique Selenium 前端测试（阶段三）

## 概述

本目录包含 OnlineBoutique 微服务系统的 **Selenium 前端自动化测试**，覆盖阶段三要求的：

- ✅ 页面加载测试
- ✅ 功能交互测试（货币切换、商品浏览、购物车、订单提交）
- ✅ 多浏览器兼容性测试（Chrome、Edge）
- ✅ 性能指标记录（页面加载时间、交互响应时间）
- ✅ 故障注入期间的功能测试
- ✅ HTML 测试报告生成

---

## 文件结构

```
tests/selenium/
├── test_selenium_performance.py      # 基线功能与性能测试（8个测试用例）
├── test_selenium_chaos.py            # 故障注入期间功能测试
├── run_selenium_with_chaos.py        # Selenium + ChaosMesh 集成测试脚本
├── run_selenium_tests.bat            # Windows 一键运行脚本
├── conftest.py                       # pytest 配置（HTML报告元数据）
├── requirements.txt                  # Python 依赖
├── README.md                         # 本文件
├── report_chrome.html                # Chrome 测试报告（生成）
├── report_edge.html                  # Edge 测试报告（生成）
└── selenium_baseline_*.json          # 性能数据文件（生成）
```

---

## 环境准备

### 1. 前置条件

- Python 3.10+（conda 环境: py310）
- Chrome 或 Edge 浏览器已安装
- OnlineBoutique 前端服务可访问
- Minikube 集群运行中

### 2. 安装依赖

```bash
cd tests/selenium
pip install -r requirements.txt
```

### 3. 配置前端地址

默认使用 `http://localhost:18080`，如需修改：

```bash
# 方式1：环境变量
export FRONTEND_URL=http://localhost:18080

# 方式2：启动 port-forward
kubectl port-forward svc/frontend-external 18080:80 -n default --address 0.0.0.0
```

---

## 快速开始

### 运行基线测试（正常状态）

```bash
# Chrome 浏览器
export FRONTEND_URL=http://localhost:18080
export TEST_BROWSER=chrome
pytest test_selenium_performance.py -v --html=report_chrome.html --self-contained-html

# Edge 浏览器
export TEST_BROWSER=edge
pytest test_selenium_performance.py -v --html=report_edge.html --self-contained-html
```

### Windows 一键运行

```cmd
# 运行 Chrome 测试
run_selenium_tests.bat chrome

# 运行 Edge 测试
run_selenium_tests.bat edge

# 运行所有浏览器测试
run_selenium_tests.bat all
```

---

## 测试用例说明

| 测试编号 | 测试名称 | 描述 | 验证点 |
|---------|---------|------|--------|
| test_01 | 首页加载 | 访问首页，验证标题和商品列表 | 页面标题、商品数量 |
| test_02 | 货币切换 | 切换为 EUR，验证价格显示 | 欧元符号 € |
| test_03 | 商品浏览 | 点击商品进入详情页 | 商品价格显示 |
| test_04 | 添加购物车 | 将商品添加到购物车 | 购物车商品数 |
| test_05 | 清空购物车 | 清空购物车内容 | 购物车为空 |
| test_06 | 返回主页 | 导航回首页 | 商品列表加载 |
| test_07 | 提交订单 | 填写表单并提交订单 | 订单完成确认 |
| test_08 | 优惠券功能 | 输入优惠券码并验证折扣 | 优惠券应用确认 |
| test_09 | 多货币支持 | 验证 USD/EUR/JPY/GBP 四种货币 | 各货币符号显示 |
| test_10 | 商品数量选择 | 选择数量 3 并验证购物车 | 数量正确性 |
| test_11 | 空购物车状态 | 验证空购物车页面显示 | 空提示、继续购物按钮 |
| test_12 | 订单确认详情 | 验证订单完成页信息完整性 | 6项关键信息 |
| test_13 | 推荐商品展示 | 验证商品详情页推荐区域 | 推荐商品数量 |
| test_14 | 完整用户旅程 | 串联所有操作的端到端测试 | 全流程成功 |

---

## 故障注入集成测试

### 运行 Chaos 测试

```bash
# 步骤1：注入故障（例如 CPU Stress）
kubectl apply -f chaos-experiments/cpu-stress-frontend.yaml

# 步骤2：运行故障期间测试
export CHAOS_TYPE=cpu_stress
export TEST_BROWSER=chrome
pytest test_selenium_chaos.py -v --html=report_chaos.html --self-contained-html

# 步骤3：停止故障
kubectl delete -f chaos-experiments/cpu-stress-frontend.yaml
```

### 自动化集成测试

```bash
# 一键运行：基线测试 -> 注入故障 -> Chaos测试 -> 停止故障 -> 生成对比报告
python run_selenium_with_chaos.py --experiment cpu_stress --browser chrome

# 可用实验类型：
#   cpu_stress     - CPU 压力测试（frontend）
#   memory_stress  - 内存压力测试（cartservice）
#   network_delay  - 网络延迟测试（checkoutservice）
#   pod_kill       - Pod 杀死测试（couponservice）
```

---

## 性能数据

测试完成后自动生成 JSON 性能数据文件：

```json
{
  "test_mode": "baseline",
  "browser": "chrome",
  "timestamp": "2026-06-02T23:30:00",
  "summary": {
    "total_tests": 8,
    "passed": 8,
    "failed": 0,
    "pass_rate": "100.0%",
    "avg_response_ms": 1234.56,
    "max_response_ms": 5678.90,
    "min_response_ms": 123.45
  },
  "details": [
    {
      "operation": "首页加载",
      "duration_ms": 456.78,
      "status": "success",
      "detail": "找到 9 个商品"
    }
  ]
}
```

---

## 环境变量

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `FRONTEND_URL` | `http://localhost:8080` | 前端服务地址 |
| `TEST_BROWSER` | `chrome` | 测试浏览器（chrome/edge/firefox） |
| `HEADLESS` | `false` | 是否无头模式 |
| `TEST_MODE` | `baseline` | 测试模式（baseline/chaos） |
| `CHAOS_TYPE` | `unknown` | 故障类型（用于 Chaos 测试） |

---

## 常见问题

### Q1: 前端服务无法访问

```bash
# 启动 port-forward
kubectl port-forward svc/frontend-external 18080:80 -n default --address 0.0.0.0

# 验证
curl http://localhost:18080
```

### Q2: 浏览器驱动下载失败（GitHub API 限流）

Firefox 的 GeckoDriver 可能因 GitHub API 限流无法下载。解决方案：
- 等待一段时间后重试
- 或手动下载 geckodriver 并添加到 PATH

### Q3: 订单提交失败（购物车为空）

test_05 清空购物车后，test_07 会自动重新添加商品。如果仍然失败：
- 检查前端服务是否正常运行
- 检查 Redis 购物车服务是否正常

---

## 测试报告

测试完成后查看 HTML 报告：

```bash
# Chrome 报告
start report_chrome.html

# Edge 报告
start report_edge.html
```

报告包含：
- 测试用例执行结果（通过/失败）
- 每个操作的响应时间
- 浏览器信息
- 测试环境配置
