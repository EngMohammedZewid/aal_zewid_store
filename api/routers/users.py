from fastapi import APIRouter, Depends

from api.deps import get_db_path, require_manager, unwrap
from api.schemas import UserIn, UserUpdate
from core.auth import create_user, list_users, update_user

router = APIRouter(prefix="/api", tags=["users"])


@router.get("/users")
def users(_user=Depends(require_manager)):
    return list_users(get_db_path())


@router.post("/users")
def add_user(body: UserIn, _user=Depends(require_manager)):
    return unwrap(create_user(body.username, body.password, body.role, get_db_path()))


@router.put("/users/{user_id}")
def edit_user(user_id: int, body: UserUpdate, _user=Depends(require_manager)):
    return unwrap(update_user(user_id, get_db_path(), role=body.role, is_active=body.is_active, password=body.password))
