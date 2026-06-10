# Coupon Service 优惠券微服务实验报告

## 一、实验目标

在 OnlineBoutique 微服务架构中新增 **Coupon Service（优惠券服务）**，实现结算时输入优惠码自动打折功能，并展示三种下单场景对比：
- **无优惠券**：正常下单
- **合法优惠券**：如 `SAVE10`、`WELCOME20`，订单总价自动打折
- **非法优惠券**：如 `FAKE99`，订单继续完成但无折扣

## 二、涉及修改的文件清单

### 2.1 新增文件

| 文件路径 | 说明 |
|---------|------|
| `src/couponservice/main.py` | 优惠券服务主程序（FastAPI） |
| `src/couponservice/Dockerfile` | 优惠券服务容器镜像构建文件 |
| `src/couponservice/requirements.txt` | Python 依赖 |
| `kubernetes-manifests/couponservice.yaml` | K8s Deployment + Service |
| `kustomize/base/couponservice.yaml` | Kustomize base 配置 |
| `kustomize/components/couponservice/couponservice.yaml` | Kustomize component 配置 |

### 2.2 修改文件

| 文件路径 | 修改内容 |
|---------|---------|
| `src/checkoutservice/main.go` | 添加优惠券调用逻辑，通过 HTTP REST 调用 couponservice，通过 gRPC metadata 传回折扣信息 |
| `src/frontend/handlers.go` | 读取表单 `coupon_code`，通过 gRPC metadata 传递给 checkoutservice，读取 response metadata 获取折扣信息 |
| `src/frontend/templates/cart.html` | 结算表单新增 **Coupon Code** 输入框 |
| `src/frontend/templates/order.html` | 订单完成页展示 **Coupon Applied** 和 **Discount** |
| `src/frontend/Dockerfile` | 显式复制文件避免 Docker build 缓存问题 |
| `kubernetes-manifests/checkoutservice.yaml` | 添加 `COUPON_SERVICE_ADDR` 环境变量 |
| `kubernetes-manifests/frontend.yaml` | 添加 `imagePullPolicy: Never` |
| `kubernetes-manifests/kustomization.yaml` | 添加 `couponservice.yaml` |
| `skaffold.yaml` | 添加 `couponservice` build 配置 |

## 三、关键目录结构

```
src/
├── couponservice/              # 新增：优惠券服务
│   ├── main.py                 # FastAPI 服务，内置 SAVE10/WELCOME20 等优惠码
│   ├── Dockerfile              # 基于 python:3.12-slim
│   └── requirements.txt        # fastapi + uvicorn + pydantic
│
├── checkoutservice/            # 修改：结算服务
│   └── main.go                 # 调用 couponservice，计算折扣后总价
│
└── frontend/                   # 修改：前端服务
    ├── handlers.go             # 传递/读取 coupon_code
    ├── templates/
    │   ├── cart.html           # 新增 Coupon Code 输入框
    │   └── order.html          # 新增 Coupon Applied / Discount 展示
    └── Dockerfile              # 显式 COPY 避免缓存问题

kubernetes-manifests/
├── couponservice.yaml          # 新增：K8s 部署配置
├── checkoutservice.yaml        # 修改：添加 COUPON_SERVICE_ADDR
└── frontend.yaml               # 修改：添加 imagePullPolicy: Never
```

## 四、核心交互流程

```
┌─────────────┐     POST /cart/checkout      ┌─────────────┐
│   Browser   │ ────────────────────────────> │   frontend  │
│  (输入SAVE10)│    FormData: coupon_code=SAVE10│  (handlers.go)│
└─────────────┘                              └──────┬──────┘
                                                    │
                                                    │ gRPC metadata: x-coupon-code
                                                    ▼
                                            ┌─────────────┐
                                            │ checkoutservice│
                                            │   (main.go)   │
                                            └──────┬──────┘
                                                   │
                                                   │ HTTP POST /apply
                                                   ▼
                                            ┌─────────────┐
                                            │ couponservice │
                                            │   (main.py)   │
                                            └──────┬──────┘
                                                   │
                                                   │ 返回折扣金额
                                                   ▼
                                            ┌─────────────┐
                                            │ checkoutservice│
                                            │ 计算折扣后总价  │
                                            │ gRPC metadata  │
                                            │ 传回折扣信息    │
                                            └──────┬──────┘
                                                   │
                                                   ▼
                                            ┌─────────────┐
                                            │   frontend   │
                                            │ 渲染订单完成页 │
                                            │ 展示 Coupon   │
                                            │ Applied +     │
                                            │ Discount      │
                                            └──────┬──────┘
                                                   │
                                                   ▼
                                            ┌─────────────┐
                                            │   Browser   │
                                            │ 显示折扣结果  │
                                            └─────────────┘
```

## 五、关键技术点

### 5.1 服务间通信

| 调用方 | 被调用方 | 协议 | 地址 |
|-------|---------|------|------|
| frontend | checkoutservice | gRPC | `checkoutservice:5050` |
| checkoutservice | couponservice | HTTP REST | `http://couponservice:8080/apply` |

### 5.2 优惠码传递方式

- **frontend → checkoutservice**：通过 **gRPC Request Metadata** (`x-coupon-code`)
- **checkoutservice → frontend**：通过 **gRPC Response Metadata** (`x-coupon-code`, `x-coupon-discount-units`, `x-coupon-discount-nanos`)

> 注：由于手动修改了 protobuf 生成的 Go 代码但未重新生成 `rawDesc`，`OrderResult.CouponCode` 和 `CouponDiscount` 字段在 gRPC 序列化时会丢失，因此采用 **gRPC Metadata** 作为替代传输方案。

### 5.3 折扣计算逻辑

```
商品小计 = Σ(商品单价 × 数量)
折扣金额 = 调用 couponservice /apply 接口计算
折扣后小计 = 商品小计 - 折扣金额
最终总价 = 折扣后小计 + 运费
```

> 优惠券仅作用于**商品小计**，运费不参与打折。

## 六、关键指令

### 6.1 构建镜像

```bash
# 构建三个修改过的服务
docker build --no-cache -t couponservice:latest src/couponservice
docker build --no-cache -t checkoutservice:latest src/checkoutservice
docker build --no-cache -t frontend:latest src/frontend
```

### 6.2 导入 minikube

```bash
minikube image load couponservice:latest --overwrite
minikube image load checkoutservice:latest --overwrite
minikube image load frontend:latest --overwrite
```

### 6.3 部署到 K8s

```bash
kubectl apply -k kubernetes-manifests/
```

### 6.4 暴露前端访问

```bash
kubectl port-forward svc/frontend 8080:80
```

浏览器访问：`http://localhost:8080`

### 6.5 查看日志

```bash
# 优惠券服务日志
kubectl logs -l app=couponservice -f

# 结算服务日志
kubectl logs -l app=checkoutservice -f

# 前端服务日志
kubectl logs -l app=frontend -f
```

## 七、演示场景

| 场景 | 优惠码输入 | 订单完成页显示 | 后端行为 |
|-----|-----------|--------------|---------|
| 无优惠券 | 留空 | 无 Coupon 相关行 | 正常结算 |
| 合法优惠券 | `SAVE10` | Coupon Applied: SAVE10<br>Discount: -$X.XX | 调用 couponservice，扣减折扣 |
| 非法优惠券 | `FAKE99` | 无 Coupon 相关行 | 调用 couponservice 返回 404，记录 warning，按原价结算 |

## 八、内置优惠码

| 优惠码 | 类型 | 折扣 | 描述 | 最低订单 |
|-------|------|------|------|---------|
| `SAVE10` | 百分比 | 10% | 全场9折 | $0 |
| `SAVE20` | 百分比 | 20% | 全场8折 | $30 |
| `WELCOME20` | 百分比 | 20% | 新用户专享8折 | $0 |
| `OFF5` | 固定金额 | $5 | 立减 $5 | $20 |
| `OFF15` | 固定金额 | $15 | 立减 $15 | $60 |
| `FREESHIP` | 运费 | 免运费 | 免运费 | $0 |
