from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime
from typing import Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Coupon Service", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 优惠码数据库（演示用，生产环境换 Redis / PostgreSQL）──
COUPONS = {
    "SAVE10": {
        "discount_type": "percent",
        "value": 10,
        "description": "全场9折",
        "min_order": 0.0,
        "expires": "2099-12-31",
    },
    "SAVE20": {
        "discount_type": "percent",
        "value": 20,
        "description": "全场8折",
        "min_order": 30.0,
        "expires": "2099-12-31",
    },
    "WELCOME20": {
        "discount_type": "percent",
        "value": 20,
        "description": "新用户专享8折",
        "min_order": 0.0,
        "expires": "2099-12-31",
    },
    "OFF5": {
        "discount_type": "fixed",
        "value": 5,
        "description": "立减 $5",
        "min_order": 20.0,
        "expires": "2099-12-31",
    },
    "OFF15": {
        "discount_type": "fixed",
        "value": 15,
        "description": "立减 $15",
        "min_order": 60.0,
        "expires": "2099-12-31",
    },
    "FREESHIP": {
        "discount_type": "shipping",
        "value": 0,
        "description": "免运费",
        "min_order": 0.0,
        "expires": "2099-12-31",
    },
}

# ── 请求 / 响应模型 ──
class ApplyRequest(BaseModel):
    code: str
    original_price: float          # 单位: USD
    user_id: Optional[str] = None  # 可选，用于用户级别限制

class CouponResult(BaseModel):
    valid: bool
    code: str
    description: str = ""
    discount_type: str = ""
    original_price: float = 0.0
    discounted_price: float = 0.0
    saved: float = 0.0
    message: str = ""

class ValidateRequest(BaseModel):
    code: str

# ── 路由 ──

@app.get("/health")
def health():
    return {"status": "ok", "service": "couponservice", "timestamp": datetime.utcnow().isoformat()}

@app.get("/coupons")
def list_coupons():
    """列出所有可用优惠码（管理/演示用）"""
    result = []
    for code, info in COUPONS.items():
        result.append({
            "code": code,
            "description": info["description"],
            "discount_type": info["discount_type"],
            "value": info["value"],
            "min_order": info["min_order"],
        })
    return {"coupons": result, "total": len(result)}

@app.get("/validate/{code}")
def validate_coupon(code: str):
    """仅验证优惠码是否有效，不计算价格"""
    code = code.strip().upper()
    if code not in COUPONS:
        return {"valid": False, "code": code, "message": "优惠码不存在"}
    coupon = COUPONS[code]
    return {
        "valid": True,
        "code": code,
        "description": coupon["description"],
        "discount_type": coupon["discount_type"],
        "value": coupon["value"],
        "min_order": coupon["min_order"],
        "message": "优惠码有效",
    }

@app.post("/apply", response_model=CouponResult)
def apply_coupon(req: ApplyRequest):
    """应用优惠码，返回折扣后价格"""
    code = req.code.strip().upper()

    # 1. 优惠码存在性检查
    if code not in COUPONS:
        logger.warning(f"Invalid coupon code attempted: {code}")
        raise HTTPException(status_code=404, detail=f"优惠码 '{code}' 不存在或已失效")

    coupon = COUPONS[code]
    original = req.original_price

    # 2. 最低订单金额检查
    if original < coupon["min_order"]:
        raise HTTPException(
            status_code=400,
            detail=f"订单金额不足，使用 '{code}' 最低需满 ${coupon['min_order']:.2f}"
        )

    # 3. 计算折扣
    if coupon["discount_type"] == "percent":
        discounted = original * (1 - coupon["value"] / 100)
    elif coupon["discount_type"] == "fixed":
        discounted = max(0.0, original - coupon["value"])
    elif coupon["discount_type"] == "shipping":
        discounted = original  # 运费由 checkout 另行处理
    else:
        discounted = original

    saved = round(original - discounted, 2)
    discounted = round(discounted, 2)

    logger.info(f"Coupon {code} applied: ${original:.2f} -> ${discounted:.2f} (saved ${saved:.2f})")

    return CouponResult(
        valid=True,
        code=code,
        description=coupon["description"],
        discount_type=coupon["discount_type"],
        original_price=round(original, 2),
        discounted_price=discounted,
        saved=saved,
        message=f"优惠码 '{code}' 已成功应用！",
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
