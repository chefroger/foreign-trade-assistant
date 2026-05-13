"""
Trade AI Assistant — REST API Router。

组装所有子路由模块，对外暴露统一的 router。
server.py 通过 ``from trade.api import router`` 挂载到 /api/trade。
"""

from fastapi import APIRouter

from trade.api.deps import require_company, opt_company
from trade.api.companies import router as companies_router
from trade.api.onboarding import router as onboarding_router
from trade.api.libraries import router as libraries_router
from trade.api.customers import router as customers_router
from trade.api.conversations import router as conversations_router
from trade.api.chat import router as chat_router
from trade.api.memory import router as memory_router

router = APIRouter(tags=["trade"])

# 按业务域挂载子路由（顺序无关，FastAPI 自动按路径匹配）
router.include_router(companies_router)
router.include_router(onboarding_router)
router.include_router(libraries_router)
router.include_router(customers_router)
router.include_router(conversations_router)
router.include_router(chat_router)
router.include_router(memory_router)

# 便捷导出（供测试或扩展使用）
__all__ = [
    "router",
    "require_company",
    "opt_company",
]
