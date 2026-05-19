"""许可证 API 路由（不需要 session token）。"""

from fastapi import APIRouter
from pydantic import BaseModel

from trade.license import activate as _activate
from trade.license import status as _status

router = APIRouter(tags=["license"])


class ActivateRequest(BaseModel):
    code: str


@router.get("/license/status")
def license_status():
    """返回许可证状态。"""
    return _status()


@router.post("/license/activate")
def license_activate(payload: ActivateRequest):
    """激活许可证。"""
    ok, msg = _activate(payload.code)
    if not ok:
        return {"ok": False, "error": msg}
    return {"ok": True, "message": msg}
