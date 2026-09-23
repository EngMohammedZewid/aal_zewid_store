import os

from fastapi import Depends, HTTPException, Request

from core.auth import COOKIE_NAME, get_user_by_token
from core.db import DEFAULT_DB_PATH


def get_db_path():
    return os.environ.get("STORE_DB_PATH", DEFAULT_DB_PATH)


def unwrap(result):
    success, payload = result
    if not success:
        detail = payload if isinstance(payload, str) else "حدث خطأ"
        raise HTTPException(status_code=400, detail=detail)
    if isinstance(payload, dict):
        return payload
    if isinstance(payload, int):
        return {"ok": True, "id": payload}
    return {"ok": True, "message": payload}


def get_current_user(request: Request):
    token = request.cookies.get(COOKIE_NAME)
    user = get_user_by_token(token, get_db_path())
    if not user:
        raise HTTPException(status_code=401, detail="يلزم تسجيل الدخول")
    return user


def require_manager(user=Depends(get_current_user)):
    if user["role"] != "manager":
        raise HTTPException(status_code=403, detail="هذه العملية متاحة للمدير فقط")
    return user
