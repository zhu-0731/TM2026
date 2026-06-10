# Selenium + JMeter 快速开始指南

> 直接复制粘贴执行

---

## 一、Selenium 功能测试

### 1. 安装依赖

```cmd
cd tests/selenium
pip install -r requirements.txt
```

### 2. 运行基础功能测试

```cmd
cd tests/selenium
python test_onlineboutique.py
```

**预期输出：**
```
test_01_homepage_load (__main__.OnlineBoutiqueTest) ... 首页加载成功，找到 9 个商品
ok
test_02_product_detail (__main__.OnlineBoutiqueTest) ... 商品详情页加载成功: Vintage Typewriter
ok
test_03_add_to_cart (__main__.OnlineBoutiqueTest) ... 添加商品到购物车成功
ok
test_04_place_order_without_coupon (__main__.OnlineBoutiqueTest) ... 无优惠券下单成功
ok
test_05_place_order_with_coupon (__main__.OnlineBoutiqueTest) ... 使用优惠券下单成功
ok
test_06_page_load_time (__main__.OnlineBoutiqueTest) ... 首页加载时间: 1.23秒
ok

----------------------------------------------------------------------
Ran 6 tests in 45.123s

OK
```

### 3. 运行增强功能测试（无头模式）

```cmd
cd tests/selenium
set HEADLESS=true
python test_onlineboutique_advanced.py
```

### 4. 故障期间功能测试

```cmd
cd tests/selenium
set HEADLESS=true
set FRONTEND_URL=http://localhost:8080
python test_chaos_resilience.py
```

---

## 二、JMeter 性能测试

### 1. 确认 JMeter 安装

```cmd
jmeter --version
```

### 2. 修改目标地址

用文本编辑器打开 `tests/jmeter/onlineboutique_test_plan.jmx`

找到：
```xml
<stringProp name="Argument.value">localhost</stringProp>
```

改为你的前端地址（如 `192.168.49.2`）

### 3. 运行基准测试

```cmd
cd tests/jmeter
mkdir results
jmeter -n -t onlineboutique_test_plan.jmx -l results/baseline.jtl -e -o report/baseline
```

### 4. 查看报告

```cmd
start report/baseline/index.html
```

---

## 三、结合故障注入的完整测试流程

### 步骤 1：JMeter 基线测试

```cmd
cd tests/jmeter
jmeter -n -t onlineboutique_test_plan.jmx -l results/step1_baseline.jtl -e -o report/step1_baseline
```

### 步骤 2：注入 CPU 故障

```cmd
kubectl apply -f chaos-experiments/cpu-stress-frontend.yaml
```

### 步骤 3：JMeter 故障期间测试

```cmd
cd tests/jmeter
jmeter -n -t onlineboutique_test_plan.jmx -l results/step2_chaos.jtl -e -o report/step2_chaos
```

### 步骤 4：Selenium 故障期间功能测试

```cmd
cd tests/selenium
set HEADLESS=true
python test_chaos_resilience.py
```

### 步骤 5：停止故障

```cmd
kubectl delete -f chaos-experiments/cpu-stress-frontend.yaml
```

### 步骤 6：JMeter 恢复测试

```cmd
cd tests/jmeter
jmeter -n -t onlineboutique_test_plan.jmx -l results/step3_recovery.jtl -e -o report/step3_recovery
```

---

## 四、测试报告清单

### Selenium 报告

| 测试 | 报告位置 | 内容 |
|-----|---------|------|
| 基础功能 | 控制台输出 | 6个测试用例通过/失败 |
| 增强功能 | `performance_*.json` | 页面加载时间、性能指标 |
| 故障期间 | 控制台输出 | 功能可用性、降级情况 |

### JMeter 报告

| 测试 | 报告位置 | 关键指标 |
|-----|---------|---------|
| 基线 | `report/step1_baseline/` | 正常状态性能 |
| 故障期间 | `report/step2_chaos/` | 故障状态性能 |
| 恢复 | `report/step3_recovery/` | 恢复后性能 |

---

## 五、论文可用数据

### 性能对比表格

| 指标 | 基线 | 故障期间 | 恢复后 | 变化率 |
|-----|------|---------|--------|--------|
| 平均响应时间 | 【从报告获取】 | 【从报告获取】 | 【从报告获取】 | 【计算】 |
| 吞吐量 (RPS) | 【从报告获取】 | 【从报告获取】 | 【从报告获取】 | 【计算】 |
| 错误率 | 【从报告获取】 | 【从报告获取】 | 【从报告获取】 | 【计算】 |

### 功能可用性表格

| 功能 | 正常状态 | 故障期间 | 恢复后 |
|-----|---------|---------|--------|
| 首页访问 | ✅ | 【记录】 | ✅ |
| 商品浏览 | ✅ | 【记录】 | ✅ |
| 添加购物车 | ✅ | 【记录】 | ✅ |
| 下单 | ✅ | 【记录】 | ✅ |

---

## 六、常见问题

### Q: Selenium 报错 ChromeDriver 找不到

```cmd
# 手动安装 ChromeDriver
pip install --upgrade webdriver-manager
```

### Q: JMeter 报告中文乱码

编辑 `jmeter.properties`，添加：
```properties
sampleresult.default.encoding=UTF-8
```

### Q: 前端地址不是 localhost

```cmd
# 获取 Minikube 地址
minikube service frontend-external --url -n default

# 或设置环境变量
set FRONTEND_URL=http://192.168.49.2:30001
```
