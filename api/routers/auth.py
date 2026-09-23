from fastapi import APIRouter, Depends, HTTPException, Request, Response

from api.deps import get_current_user, get_db_path
from api.schemas import LoginIn
from core.auth import COOKIE_NAME, SESSION_HOURS, authenticate, create_session, delete_session

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login")
def login(body: LoginIn, response: Response):
    user = authenticate(body.username, body.password, get_db_path())
    if not user:
        raise HTTPException(status_code=401, detail="اسم المستخدم أو كلمة المرور غير صحيحة")
    token = create_session(user["id"], get_db_path())
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        max_age=SESSION_HOURS * 3600,
        path="/",
    )
    return user


@router.post("/logout")
def logout(request: Request, response: Response):
    delete_session(request.cookies.get(COOKIE_NAME), get_db_path())
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True}


@router.get("/me")
def me(user=Depends(get_current_user)):
    return user
