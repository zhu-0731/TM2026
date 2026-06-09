"""Service dependency map for Online Boutique."""

from __future__ import annotations

SERVICE_DEPENDENCIES: dict[str, list[str]] = {
    "frontend": [
        "productcatalogservice",
        "cartservice",
        "currencyservice",
        "recommendationservice",
        "checkoutservice",
    ],
    "checkoutservice": [
        "paymentservice",
        "shippingservice",
        "emailservice",
        "cartservice",
    ],
    "cartservice": ["redis-cart"],
}


def get_downstream_services(service_name: str) -> list[str]:
    """Return directly dependent downstream services for one service."""

    return SERVICE_DEPENDENCIES.get(service_name, [])
