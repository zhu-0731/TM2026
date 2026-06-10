# 阶段三：Selenium & JMeter 自动化测试指南

> 使用 Selenium 进行功能测试，JMeter 进行性能测试，验证 OnlineBoutique 微服务系统在不同场景下的表现。

---

## 目录

- [环境准备](#环境准备)
- [Selenium 功能测试](#selenium-功能测试)
- [JMeter 性能测试](#jmeter-性能测试)
- [结合故障注入的测试](#结合故障注入的测试)
- [测试报告汇总](#测试报告汇总)

---

## 环境准备

### 1. 确认微服务可访问

```bash
# 获取前端访问地址
minikube service frontend-external --url -n default

# 或使用 port-forward
kubectl port-forward svc/frontend-external 8080:80 -n default
```

确认浏览器能访问：`http://localhost:8080`

### 2. 安装 Python 依赖

```bash
cd tests/selenium

# 创建虚拟环境（可选）
python -m venv venv
venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt
```

### 3. 安装 JMeter

```bash
# 下载 JMeter（如未安装）
# https://dlcdn.apache.org//jmeter/binaries/apache-jmeter-5.6.3.zip

# 解压后配置环境变量
set JMETER_HOME=C:\apache-jmeter-5.6.3
set PATH=%JMETER_HOME%\bin;%PATH%

# 验证安装
jmeter --version
```

---

## Selenium 功能测试

### 测试脚本位置

`tests/selenium/test_onlineboutique.py`

### 运行基础功能测试

```bash
cd tests/selenium
python test_onlineboutique.py
```

### 测试用例说明

| 用例编号 | 测试内容 | 验证点 |
|---------|---------|--------|
| test_01 | 首页加载 | 页面标题、商品列表存在 |
| test_02 | 商品详情页 | 商品名称显示正确 |
| test_03 | 添加购物车 | 购物车页面跳转、商品存在 |
| test_04 | 无优惠券下单 | 订单完成页显示 |
| test_05 | 使用优惠券下单 | 优惠券信息正确显示 |
| test_06 | 页面加载时间 | 首页加载 < 5 秒 |

### 运行增强功能测试（多浏览器、性能指标）

```bash
# Chrome 浏览器（默认）
python test_onlineboutique_advanced.py

# 无头模式（不显示浏览器窗口）
set HEADLESS=true
python test_onlineboutique_advanced.py

# 指定前端地址
set FRONTEND_URL=http://localhost:8080
python test_onlineboutique_advanced.py
```

### 跨浏览器测试

```bash
# 测试 Chrome、Firefox、Edge
set CROSS_BROWSER=true
python test_onlineboutique_advanced.py
```

### 故障期间功能测试

```bash
# 在 ChaosMesh 注入故障时运行
set HEADLESS=true
set FRONTEND_URL=http://localhost:8080
python test_chaos_resilience.py
```

---

## JMeter 性能测试

### 测试计划位置

`tests/jmeter/onlineboutique_test_plan.jmx`

### 修改目标地址

用文本编辑器打开 `onlineboutique_test_plan.jmx`，找到并修改：

```xml
<stringProp name="Argument.value">localhost</stringProp>
<!-- 改为你的前端地址，如 192.168.49.2 -->
```

或运行时通过命令行参数指定。

### 运行基准测试（10用户，5分钟）

```bash
cd tests/jmeter

# 创建结果目录
mkdir results

# 非 GUI 模式运行
jmeter -n -t onlineboutique_test_plan.jmx -l results/baseline.jtl -e -o report/baseline
```

### 查看测试报告

```bash
# 打开 HTML 报告
start report/baseline/index.html
```

### 测试场景说明

| 场景 | 并发用户数 | Ramp-up | 持续时间 | 状态 |
|-----|-----------|---------|---------|------|
| 场景一：基准测试 | 10 | 30s | 5分钟 | 默认启用 |
| 场景二：负载测试 | 50 | 60s | 10分钟 | 禁用 |
| 场景三：压力测试 | 100 | 120s | 10分钟 | 禁用 |
| 场景四：峰值测试 | 200 | 180s | 5分钟 | 禁用 |

### 切换测试场景

在 JMeter GUI 中：
1. 右键点击要启用的 Thread Group → 启用
2. 右键点击其他 Thread Group → 禁用
3. 保存并运行

---

## 结合故障注入的测试

### 测试流程

```
1. 运行 JMeter 基线测试（正常状态）
   → 记录响应时间、吞吐量、错误率

2. 注入 ChaosMesh 故障
   → kubectl apply -f chaos-experiments/xxx.yaml

3. 运行 JMeter 故障期间测试
   → 记录性能指标变化

4. 停止故障
   → kubectl delete -f chaos-experiments/xxx.yaml

5. 运行 JMeter 恢复测试
   → 记录系统恢复情况

6. 对比分析
   → 基线 vs 故障 vs 恢复
```

### 示例：CPU Stress 期间性能测试

```bash
# 1. 基线测试
jmeter -n -t onlineboutique_test_plan.jmx -l results/cpu_baseline.jtl -e -o report/cpu_baseline

# 2. 注入 CPU 故障
kubectl apply -f chaos-experiments/cpu-stress-frontend.yaml

# 3. 故障期间测试
jmeter -n -t onlineboutique_test_plan.jmx -l results/cpu_chaos.jtl -e -o report/cpu_chaos

# 4. 停止故障
kubectl delete -f chaos-experiments/cpu-stress-frontend.yaml

# 5. 恢复测试（等待1分钟后）
jmeter -n -t onlineboutique_test_plan.jmx -l results/cpu_recovery.jtl -e -o report/cpu_recovery
```

---

## 测试报告汇总

### Selenium 测试报告

| 测试类型 | 报告位置 | 内容 |
|---------|---------|------|
| 基础功能测试 | 控制台输出 | 6个测试用例结果 |
| 增强功能测试 | `performance_*.json` | 页面加载时间、性能指标 |
| 跨浏览器测试 | 控制台输出 | Chrome/Firefox/Edge 结果 |
| 故障期间测试 | `tests/selenium/` 日志 | 故障期间功能可用性 |

### JMeter 测试报告

| 测试类型 | 报告位置 | 关键指标 |
|---------|---------|---------|
| 基准测试 | `report/baseline/` | 平均响应时间、吞吐量 |
| 负载测试 | `report/load/` | 50用户并发性能 |
| 压力测试 | `report/stress/` | 100用户并发性能 |
| 故障期间测试 | `report/cpu_chaos/` | 故障期间性能变化 |

### 关键性能指标

| 指标 | 健康阈值 | 说明 |
|-----|---------|------|
| 平均响应时间 | < 500ms | 请求平均耗时 |
| 95% 响应时间 | < 1000ms | 95%请求耗时 |
| 吞吐量 | > 100 RPS | 每秒请求数 |
| 错误率 | < 1% | 失败请求占比 |

---

## 常见问题

### Q: Selenium 报错 WebDriver 找不到
A: 确保已安装 Chrome 浏览器，并允许 `webdriver-manager` 自动下载 ChromeDriver

### Q: JMeter 报告中文乱码
A: 修改 `jmeter.properties`：`sampleresult.default.encoding=UTF-8`

### Q: 测试时前端无法访问
A: 确认 `kubectl port-forward svc/frontend-external 8080:80` 正在运行

---

## 文件结构

```
tests/
├── selenium/
│   ├── test_onlineboutique.py           # 基础功能测试
│   ├── test_onlineboutique_advanced.py  # 增强功能测试
│   ├── test_chaos_resilience.py         # 故障期间测试
│   └── requirements.txt                 # Python 依赖
├── jmeter/
│   ├── onlineboutique_test_plan.jmx     # JMeter 测试计划
│   ├── README.md                        # JMeter 使用说明
│   └── results/                         # 测试结果目录
├── prometheus/
│   └── collect_metrics.py               # 数据采集脚本
├── EXPERIMENT_REPORT.md                 # 故障注入实验报告
├── TEST_GUIDE.md                        # 完整测试指南
└── SELENIUM_JMETER_GUIDE.md             # 本文件
```
