from fastapi import APIRouter, Depends, HTTPException

from api.deps import get_db_path, require_manager, unwrap
from api.schemas import PurchaseOrderIn, SupplierIn
from core.db import add_supplier, create_purchase_order, get_all_purchase_orders, get_all_suppliers, get_po_items, mark_po_received, round_amount

router = APIRouter(prefix="/api", tags=["suppliers"])


@router.get("/suppliers")
def list_suppliers(user=Depends(require_manager)):
    return get_all_suppliers(db_path=get_db_path())


@router.post("/suppliers")
def create_supplier(body: SupplierIn, user=Depends(require_manager)):
    if not body.name.strip() or not body.phone.strip():
        raise HTTPException(status_code=400, detail="اسم الشركة ورقم الهاتف مطلوبان.")
    return unwrap(
        add_supplier(
            body.name.strip(),
            body.contact_person.strip(),
            body.phone.strip(),
            body.email.strip(),
            body.address.strip(),
            db_path=get_db_path(),
        )
    )


@router.get("/purchase-orders")
def list_purchase_orders(user=Depends(require_manager)):
    return get_all_purchase_orders(db_path=get_db_path())


@router.get("/purchase-orders/{po_id}/items")
def purchase_order_items(po_id: int, user=Depends(require_manager)):
    return get_po_items(po_id, db_path=get_db_path())


@router.post("/purchase-orders")
def create_po(body: PurchaseOrderIn, user=Depends(require_manager)):
    if not body.items:
        raise HTTPException(status_code=400, detail="أضف صنفاً واحداً على الأقل لأمر الشراء.")
    items = []
    total = 0.0
    for item in body.items:
        if item.quantity <= 0:
            raise HTTPException(status_code=400, detail="كمية أمر الشراء غير صحيحة")
        items.append((item.product_id, item.quantity, item.unit_cost))
        total = round_amount(total + (item.quantity * item.unit_cost))
    return unwrap(create_purchase_order(body.supplier_id, items, total, db_path=get_db_path()))


@router.post("/purchase-orders/{po_id}/receive")
def receive_po(po_id: int, user=Depends(require_manager)):
    return unwrap(mark_po_received(po_id, db_path=get_db_path()))
