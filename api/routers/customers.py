from fastapi import APIRouter, Depends, HTTPException

from api.deps import get_current_user, get_db_path, require_manager, unwrap
from api.schemas import CustomerIn, CustomerUpdate
from core.db import add_customer, delete_customer, get_all_customers, get_customer_sales, get_generic_customer_id, update_customer

router = APIRouter(prefix="/api", tags=["customers"])


@router.get("/customers")
def list_customers(user=Depends(get_current_user)):
    return get_all_customers(db_path=get_db_path())


@router.get("/customers/generic")
def generic_customer(user=Depends(get_current_user)):
    return {"id": get_generic_customer_id(db_path=get_db_path())}


@router.post("/customers")
def create_customer(body: CustomerIn, user=Depends(get_current_user)):
    if not body.name.strip() or not body.phone.strip():
        raise HTTPException(status_code=400, detail="يرجى إدخال اسم العميل ورقم الهاتف.")
    return unwrap(add_customer(body.name.strip(), body.phone.strip(), body.email.strip(), db_path=get_db_path()))


@router.put("/customers/{customer_id}")
def edit_customer(customer_id: int, body: CustomerUpdate, user=Depends(require_manager)):
    generic_id = get_generic_customer_id(db_path=get_db_path())
    if generic_id and customer_id == generic_id:
        raise HTTPException(status_code=400, detail="لا يمكن تعديل بيانات العميل الافتراضي العام.")
    if body.loyalty_points < 0:
        raise HTTPException(status_code=400, detail="نقاط الولاء يجب أن تكون رقماً صحيحاً.")
    return unwrap(
        update_customer(
            customer_id,
            body.name.strip(),
            body.phone.strip(),
            body.email.strip(),
            body.loyalty_points,
            db_path=get_db_path(),
        )
    )


@router.delete("/customers/{customer_id}")
def remove_customer(customer_id: int, user=Depends(require_manager)):
    return unwrap(delete_customer(customer_id, db_path=get_db_path()))


@router.get("/customers/{customer_id}/sales")
def customer_sales(customer_id: int, user=Depends(get_current_user)):
    return get_customer_sales(customer_id, db_path=get_db_path())
