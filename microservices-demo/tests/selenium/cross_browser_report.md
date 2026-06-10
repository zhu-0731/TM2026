# Selenium 跨浏览器兼容性测试报告

**测试时间**: 2026-06-03 12:03:02
**测试目标**: OnlineBoutique 前端功能与性能
**测试浏览器**: Chrome、Edge、Firefox

---

## 一、测试结果汇总

| 浏览器 | 状态 | 报告文件 |
|--------|------|----------|
| CHROME | ✅ 通过 | report_chrome.html |
| EDGE | ✅ 通过 | report_edge.html |
| FIREFOX | ✅ 通过 | report_firefox.html |

---

## 二、性能数据对比

| 指标 | Chrome | Edge | Firefox |
|------|--------|------|---------|
| 平均响应时间 | 4325.91 ms | 3776.93 ms | 4991.74 ms |
| 最大响应时间 | 16801.43 ms | 11341.7 ms | 40487.27 ms |
| 最小响应时间 | 68.37 ms | 51.12 ms | 55.33 ms |
| 测试通过率 | 100.0% | 100.0% | 100.0% |

### 各浏览器详细性能数据

#### CHROME

| 操作 | 响应时间 | 状态 |
|------|----------|------|
| 首页加载 | 16801.43 ms | success |
| 货币切换 | 10583.82 ms | success |
| 商品详情浏览 | 457.45 ms | success |
| 添加购物车 | 535.62 ms | success |
| 清空购物车 | 1349.17 ms | success |
| 返回主页 | 143.14 ms | success |
| 提交订单 | 4224.02 ms | success |
| 优惠券功能 | 4828.63 ms | success |
| 货币切换-USD | 10452.37 ms | success |
| 货币切换-EUR | 10715.53 ms | success |
| 货币切换-JPY | 10716.79 ms | success |
| 货币切换-GBP | 10651.29 ms | success |
| 商品数量选择 | 238.36 ms | success |
| 空购物车状态 | 68.37 ms | success |
| 订单确认详情 | 3842.23 ms | success |
| 推荐商品展示 | 1441.59 ms | success |
| 旅程-首页加载 | 369.83 ms | success |
| 旅程-货币切换 | 390.57 ms | success |
| 旅程-浏览商品 | 364.47 ms | success |
| 旅程-添加购物车 | 281.18 ms | success |
| 旅程-提交订单 | 2653.57 ms | success |
| 完整用户旅程 | 4060.61 ms | success |

#### EDGE

| 操作 | 响应时间 | 状态 |
|------|----------|------|
| 首页加载 | 11341.7 ms | success |
| 货币切换 | 10412.8 ms | success |
| 商品详情浏览 | 231.67 ms | success |
| 添加购物车 | 200.36 ms | success |
| 清空购物车 | 1175.08 ms | success |
| 返回主页 | 99.22 ms | success |
| 提交订单 | 3830.69 ms | success |
| 优惠券功能 | 3849.52 ms | success |
| 货币切换-USD | 10449.73 ms | success |
| 货币切换-EUR | 10287.81 ms | success |
| 货币切换-JPY | 10301.55 ms | success |
| 货币切换-GBP | 10442.73 ms | success |
| 商品数量选择 | 143.44 ms | success |
| 空购物车状态 | 51.12 ms | success |
| 订单确认详情 | 3846.19 ms | success |
| 推荐商品展示 | 1395.34 ms | success |
| 旅程-首页加载 | 96.33 ms | success |
| 旅程-货币切换 | 136.34 ms | success |
| 旅程-浏览商品 | 258.51 ms | success |
| 旅程-添加购物车 | 247.77 ms | success |
| 旅程-提交订单 | 1777.75 ms | success |
| 完整用户旅程 | 2516.71 ms | success |

#### FIREFOX

| 操作 | 响应时间 | 状态 |
|------|----------|------|
| 首页加载 | 40487.27 ms | success |
| 货币切换 | 10210.4 ms | success |
| 商品详情浏览 | 219.05 ms | success |
| 添加购物车 | 265.43 ms | success |
| 清空购物车 | 1175.36 ms | success |
| 返回主页 | 97.56 ms | success |
| 提交订单 | 3293.58 ms | success |
| 优惠券功能 | 3337.63 ms | success |
| 货币切换-USD | 10278.67 ms | success |
| 货币切换-EUR | 10155.31 ms | success |
| 货币切换-JPY | 10154.49 ms | success |
| 货币切换-GBP | 10211.07 ms | success |
| 商品数量选择 | 123.93 ms | success |
| 空购物车状态 | 133.81 ms | success |
| 订单确认详情 | 3515.63 ms | success |
| 推荐商品展示 | 1505.97 ms | success |
| 旅程-首页加载 | 131.81 ms | success |
| 旅程-货币切换 | 55.33 ms | success |
| 旅程-浏览商品 | 515.46 ms | success |
| 旅程-添加购物车 | 194.05 ms | success |
| 旅程-提交订单 | 1429.67 ms | success |
| 完整用户旅程 | 2326.83 ms | success |

---

## 三、兼容性结论

- **通过浏览器**: 3/3
- **兼容性**: 良好

- **CHROME**: 所有功能正常，前端兼容性良好。
- **EDGE**: 所有功能正常，前端兼容性良好。
- **FIREFOX**: 所有功能正常，前端兼容性良好。

---

*报告由 Selenium 跨浏览器测试自动生成*