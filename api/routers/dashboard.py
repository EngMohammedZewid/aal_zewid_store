from fastapi import APIRouter, Depends, HTTPException

from api.deps import get_current_user, get_db_path
from core.db import get_dashboard_summary, get_recent_sales, get_sale_details, get_sale_for_return

router = APIRouter(prefix="/api", tags=["dashboard"])


@router.get("/dashboard/summary")
def dashboard_summary(user=Depends(get_current_user)):
    return get_dashboard_summary(db_path=get_db_path())


@router.get("/sales/recent")
def recent_sales(limit: int = 20, user=Depends(get_current_user)):
    safe_limit = max(1, min(limit, 200))
    return get_recent_sales(limit=safe_limit, db_path=get_db_path())


@router.get("/sales/{sale_id}")
def sale_detail(sale_id: int, user=Depends(get_current_user)):
    sale = get_sale_for_return(sale_id, db_path=get_db_path())
    if not sale:
        raise HTTPException(status_code=404, detail="رقم الفاتورة غير موجود")
    return {"sale": sale, "items": get_sale_details(sale_id, db_path=get_db_path())}
