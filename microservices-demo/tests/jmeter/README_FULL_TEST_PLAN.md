# OnlineBoutique 完整性能测试计划

## 文件
- `onlineboutique_full_test_plan.jmx` - **一次测试覆盖所有场景**

---

## 覆盖检查清单

| 要求 | 覆盖情况 | 说明 |
|------|---------|------|
| 线程组模拟多用户并发 | ✅ 5个ThreadGroup | 基线5人/负载20人/压力50人/峰值100人/优惠券30人 |
| 覆盖所有微服务模块 | ✅ 全部覆盖 | Frontend/Rec/Ad/Currency/ProductCatalog/Cart/Checkout/Payment/Shipping/Email/Coupon |
| 不同负载场景 | ✅ 4种负载模式 | 基线/负载/压力/峰值，不同并发数+持续时间 |
| 监控响应时间 | ✅ 6种监控器 | Summary/Aggregate/Table/Tree/ResponseTimeGraph/ThroughputGraph |
| 监控吞吐量 | ✅ 同上 | Throughput Graph + Summary Report |
| 监控错误率 | ✅ 同上 | Aggregate Report 显示 Error% |
| 一次测试完成 | ✅ 全部启用 | 5个场景同时运行，一次执行全覆盖 |

---

## 5个测试场景（全部同时运行）

### S1-Baseline: 5 Users, 60s（基线测试）
| 参数 | 值 |
|------|-----|
| 并发用户 | 5 |
| Ramp-up | 10秒 |
| 持续时间 | 60秒 |
| 循环次数 | 3次/用户 |
| 思考时间 | 500-1500ms |
| 断言 | HTTP 200, 包含产品信息, 响应<3s |

**覆盖接口**: 首页 → 货币 → 商品详情 → 加购 → 查看购物车 → 下单

### S2-Load: 20 Users, 180s（日常负载）
| 参数 | 值 |
|------|-----|
| 并发用户 | 20 |
| Ramp-up | 30秒 |
| 持续时间 | 180秒 |
| 循环次数 | 5次/用户 |
| 思考时间 | 500-1500ms |
| 断言 | HTTP 200, 订单确认, 响应<3s |

**覆盖接口**: 首页 → 货币 → 商品详情 → 加购 → 查看购物车 → 下单

### S3-Stress: 50 Users, 300s（压力测试）
| 参数 | 值 |
|------|-----|
| 并发用户 | 50 |
| Ramp-up | 60秒 |
| 持续时间 | 300秒 |
| 循环次数 | 8次/用户 |
| 思考时间 | 300-700ms |
| 断言 | HTTP 200, 响应<5s |

**覆盖接口**: 首页 → 商品详情 → 加购 → 下单

### S4-Spike: 100 Users, 120s（峰值测试）
| 参数 | 值 |
|------|-----|
| 并发用户 | 100 |
| Ramp-up | 5秒（瞬间加压） |
| 持续时间 | 120秒 |
| 循环次数 | 2次/用户 |
| 思考时间 | 100-300ms |
| 断言 | HTTP 200, 响应<10s |

**覆盖接口**: 首页 → 下单

### S5-Coupon: 30 Users, 240s（优惠券专项）
| 参数 | 值 |
|------|-----|
| 并发用户 | 30 |
| Ramp-up | 30秒 |
| 持续时间 | 240秒 |
| 循环次数 | 6次/用户 |
| 思考时间 | 500-1500ms |
| 断言 | HTTP 200, 优惠券已应用 |

**覆盖接口**: 加购 → 使用SAVE10结账 → 使用OFF15结账 → 使用FREESHIP结账

---

## 微服务覆盖矩阵

| 微服务 | S1 | S2 | S3 | S4 | S5 | 测试接口 |
|--------|:--:|:--:|:--:|:--:|:--:|----------|
| Frontend | ✅ | ✅ | ✅ | ✅ | ✅ | GET / |
| Recommendation | ✅ | ✅ | ✅ | ✅ | | 首页推荐 |
| AdService | ✅ | ✅ | ✅ | ✅ | | 首页广告 |
| CurrencyService | ✅ | ✅ | | | | POST /setCurrency |
| ProductCatalogService | ✅ | ✅ | ✅ | | | GET /product/{id} |
| CartService | ✅ | ✅ | ✅ | | ✅ | POST/GET /cart |
| CheckoutService | ✅ | ✅ | ✅ | ✅ | ✅ | POST /cart/checkout |
| PaymentService | ✅ | ✅ | ✅ | ✅ | ✅ | 结账时调用 |
| ShippingService | ✅ | ✅ | ✅ | ✅ | ✅ | 结账时调用 |
| EmailService | ✅ | ✅ | ✅ | ✅ | ✅ | 结账后发送 |
| CouponService | | | | | ✅ | 优惠券验证和应用 |

---

## 全局监控组件

| 监控器 | 用途 | 指标 |
|--------|------|------|
| **View Results Tree** | 调试查看单个请求 | 请求/响应详情 |
| **View Results in Table** | 表格查看所有请求 | 时间、状态、字节数 |
| **Summary Report** | 汇总统计 | 吞吐量、平均/最小/最大响应时间 |
| **Aggregate Report** | 聚合统计 | 中位数、90%/95%/99%线、错误率 |
| **Response Time Graph** | 响应时间趋势图 | 随时间变化的响应时间 |
| **Throughput Graph** | 吞吐量趋势图 | 随时间变化的吞吐量 |

结果保存: `results/full_test_summary.jtl`

---

## 断言清单

| 断言 | 应用场景 | 说明 |
|------|---------|------|
| HTTP 200 | 所有请求 | 验证接口返回成功 |
| 包含 Products | 首页 | 验证页面渲染正确 |
| 包含 Product Name | 商品详情 | 验证商品数据加载 |
| 包含 Shopping Cart | 购物车 | 验证购物车页面 |
| 包含 Order Confirmation | 下单 | 验证订单提交成功 |
| 包含 Coupon Applied | 优惠券 | 验证优惠券生效 |
| 响应时间 < 3s | 基线/负载 | 正常负载性能要求 |
| 响应时间 < 5s | 压力 | 高负载性能要求 |
| 响应时间 < 10s | 峰值 | 极端负载性能要求 |

---

## 使用步骤

### 1. 更新服务地址
在 JMeter GUI 中打开测试计划，修改 **Test Plan > User Defined Variables**:
```
BASE_URL = 127.0.0.1
PORT     = 54770  (根据 minikube service 实际端口修改)
```

获取当前端口:
```bash
minikube service frontend-external --url -n default
```

### 2. GUI 验证（推荐首次使用）
1. 启动 JMeter GUI: `jmeter.bat`
2. 打开 `onlineboutique_full_test_plan.jmx`
3. 点击运行按钮
4. 在 **View Results Tree** 中验证请求成功
5. 在 **Summary Report** 中查看实时指标

### 3. CLI 执行（正式测试）
```bash
# 进入目录
cd tests/jmeter

# 创建结果目录
mkdir -p results

# 执行完整测试
jmeter -n -t onlineboutique_full_test_plan.jmx -l results/full_test.jtl

# 生成 HTML 报告
jmeter -g results/full_test.jtl -o results/html_report
```

### 4. 分析结果

**关键指标关注点**:
- **吞吐量 (Throughput)**: 越高越好，反映系统处理能力
- **平均响应时间**: 基线<500ms, 负载<1s, 压力<3s, 峰值<5s
- **错误率 (Error%)**: 应接近 0%，>1% 需排查
- **90% Line**: 90% 请求的响应时间，反映用户体验

**结果文件**:
- `results/full_test_summary.jtl` - 原始数据
- `results/html_report/` - HTML 可视化报告

---

## 调整并发数

如需调整某个场景的并发数，在 JMeter GUI 中:
1. 选择对应 ThreadGroup
2. 修改 **Number of Threads (users)**
3. 修改 **Ramp-up period** (建议保持用户/秒比例)

**建议调整范围**:
| 场景 | 最小 | 建议 | 最大 |
|------|------|------|------|
| 基线 | 1 | 5 | 10 |
| 负载 | 10 | 20 | 50 |
| 压力 | 30 | 50 | 100 |
| 峰值 | 50 | 100 | 200 |
| 优惠券 | 10 | 30 | 50 |

---

## 故障排除

### 连接失败
- 确认 Minikube 运行: `minikube status`
- 确认服务端口: `minikube service frontend-external --url`
- 检查 BASE_URL 和 PORT 变量

### 大量 500 错误
- 检查各微服务 Pod 状态: `kubectl get pods`
- 查看错误日志: `kubectl logs <pod-name>`
- 可能是数据库连接池耗尽

### 响应时间过长
- 检查资源使用: `kubectl top pods`
- 可能是 CPU/内存瓶颈
- 考虑增加 Pod 副本数

### JMeter 内存不足
编辑 `jmeter.bat`:
```
set HEAP=-Xms2g -Xmx4g
```

---

## 测试计划结构图

```
TestPlan
├── User Defined Variables (BASE_URL, PORT, PRODUCT_IDs)
├── HTTP Request Defaults
├── HTTP Cookie Manager
├── HTTP Cache Manager
├── HTTP Header Manager
│
├── S1-Baseline: 5 Users
│   ├── 1.1 Homepage (GET /)
│   ├── 1.2 Set Currency (POST /setCurrency)
│   ├── 1.3 Product Detail (GET /product/{id})
│   ├── 1.4 Add to Cart (POST /cart)
│   ├── 1.5 View Cart (GET /cart)
│   ├── 1.6 Place Order (POST /cart/checkout)
│   └── Gaussian Random Timer
│
├── S2-Load: 20 Users
│   ├── 2.1 Homepage
│   ├── 2.2 Set Currency
│   ├── 2.3 Product Detail
│   ├── 2.4 Add to Cart
│   ├── 2.5 View Cart
│   ├── 2.6 Place Order
│   └── Gaussian Random Timer
│
├── S3-Stress: 50 Users
│   ├── 3.1 Homepage
│   ├── 3.2 Product Detail
│   ├── 3.3 Add to Cart
│   ├── 3.4 Place Order
│   └── Gaussian Random Timer
│
├── S4-Spike: 100 Users
│   ├── 4.1 Homepage
│   ├── 4.2 Place Order
│   └── Gaussian Random Timer
│
├── S5-Coupon: 30 Users
│   ├── 5.1 Add to Cart
│   ├── 5.2 Checkout SAVE10
│   ├── 5.3 Checkout OFF15
│   ├── 5.4 Checkout FREESHIP
│   └── Gaussian Random Timer
│
└── Global Result Collectors
    ├── View Results Tree
    ├── View Results in Table
    ├── Summary Report → results/full_test_summary.jtl
    ├── Aggregate Report
    ├── Response Time Graph
    └── Throughput Graph
```
