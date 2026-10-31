from fastapi import APIRouter

from app.api.routes import (
    discounts,
    items,
    login,
    payment_terms,
    plans,
    private,
    products,
    quotation_templates,
    taxes,
    users,
    utils,
)
from app.core.config import settings

api_router = APIRouter()
api_router.include_router(login.router)
api_router.include_router(users.router)
api_router.include_router(utils.router)
api_router.include_router(items.router)
api_router.include_router(products.router)
api_router.include_router(plans.router)
api_router.include_router(taxes.router)
api_router.include_router(payment_terms.router)
api_router.include_router(discounts.router)
api_router.include_router(quotation_templates.router)


if settings.FASTAPI_ENV == "development":
    api_router.include_router(private.router)
