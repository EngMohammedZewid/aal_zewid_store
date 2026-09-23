from fastapi import APIRouter, Depends, HTTPException

from api.deps import get_current_user, get_db_path, unwrap
from api.schemas import CloseSessionIn, ExpenseIn, OpenSessionIn, ReturnIn, SaleIn
from core.db import (
    add_expense,
    calculate_session_summary,
    calculate_tax,
    close_pos_session,
    delete_expense,
    get_active_pos_session,
    get_expense,
    get_pos_sessions,
    get_product_units,
    get_return_details,
    get_returnable_sale_items,
    get_sale_for_return,
    get_session_expenses,
    open_pos_session,
    preview_sale_return,
    record_sale,
    record_sale_return,
    round_amount,
)

router = APIRouter(prefix="/api/pos", tags=["pos"])


def _active_session_or_error():
    session = get_active_pos_session(db_path=get_db_path())
    if not session:
        raise HTTPException(status_code=400, detail="لا توجد جلسة كاشير مفتوحة")
    return session


def _priced_sale_lines(items):
    priced = []
    subtotal = 0.0
    for item in items:
        if item.quantity <= 0:
            raise HTTPException(status_code=400, detail="كمية البيع غير صحيحة")
        units = get_product_units(item.product_id, db_path=get_db_path())
        if not units:
            raise HTTPException(status_code=400, detail="المنتج غير موجود")
        selected = None
        if item.product_unit_id is not None:
            selected = next((unit for unit in units if unit["id"] == item.product_unit_id), None)
        else:
            selected = next((unit for unit in units if unit["is_default"]), units[0])
        if not selected:
            raise HTTPException(status_code=400, detail="وحدة المنتج غير موجودة")
        if abs(round_amount(item.unit_price) - round_amount(selected["selling_price"])) > 0.01:
            raise HTTPException(status_code=400, detail="سعر الوحدة لا يطابق سعر المنتج")
        unit_price = round_amount(selected["selling_price"])
        line_subtotal = round_amount(item.quantity * unit_price)
        subtotal = round_amount(subtotal + line_subtotal)
        priced.append(
            {
                "product_id": item.product_id,
                "product_unit_id": selected["id"],
                "unit_name": selected["unit_name"],
                "pieces_per_unit": selected["pieces_per_unit"],
                "quantity": item.quantity,
                "unit_price": unit_price,
                "subtotal": line_subtotal,
            }
        )
    return priced, subtotal


@router.get("/session")
def active_session(user=Depends(get_current_user)):
    session = get_active_pos_session(db_path=get_db_path())
    summary = calculate_session_summary(session["id"], db_path=get_db_path()) if session else None
    return {"session": session, "summary": summary}


@router.post("/session")
def open_session(body: OpenSessionIn, user=Depends(get_current_user)):
    return unwrap(open_pos_session(body.opening_balance, body.notes, db_path=get_db_path(), opened_by_user_id=user["id"]))


@router.post("/session/close")
def close_session(body: CloseSessionIn, user=Depends(get_current_user)):
    session = _active_session_or_error()
    return unwrap(
        close_pos_session(
            session["id"],
            body.actual_balance,
            body.notes,
            db_path=get_db_path(),
            closed_by_user_id=user["id"],
        )
    )


@router.get("/sessions")
def session_history(user=Depends(get_current_user)):
    return get_pos_sessions(db_path=get_db_path())


@router.get("/sessions/{session_id}/summary")
def session_summary(session_id: int, user=Depends(get_current_user)):
    summary = calculate_session_summary(session_id, db_path=get_db_path())
    if not summary:
        raise HTTPException(status_code=404, detail="الجلسة غير موجودة")
    return summary


@router.get("/sessions/{session_id}/expenses")
def session_expenses(session_id: int, user=Depends(get_current_user)):
    return get_session_expenses(session_id, db_path=get_db_path())


@router.post("/expenses")
def create_expense(body: ExpenseIn, user=Depends(get_current_user)):
    session = _active_session_or_error()
    return unwrap(
        add_expense(
            session["id"],
            body.category,
            body.description,
            body.amount,
            payment_method=body.payment_method,
            reference_number=body.reference_number,
            notes=body.notes,
            db_path=get_db_path(),
            user_id=user["id"],
        )
    )


@router.get("/expenses/{expense_id}")
def expense_detail(expense_id: int, user=Depends(get_current_user)):
    expense = get_expense(expense_id, db_path=get_db_path())
    if not expense:
        raise HTTPException(status_code=404, detail="المصروف غير موجود")
    return expense


@router.delete("/expenses/{expense_id}")
def remove_expense(expense_id: int, user=Depends(get_current_user)):
    return unwrap(delete_expense(expense_id, db_path=get_db_path()))


@router.post("/sales")
def create_sale(body: SaleIn, user=Depends(get_current_user)):
    session = _active_session_or_error()
    if not body.items:
        raise HTTPException(status_code=400, detail="سلة المشتريات فارغة")
    if not (body.payment_method or "").strip():
        raise HTTPException(status_code=400, detail="طريقة الدفع مطلوبة")
    priced, subtotal = _priced_sale_lines(body.items)
    discount = round_amount(body.discount)
    if discount < 0:
        raise HTTPException(status_code=400, detail="الخصم غير صحيح")
    tax = calculate_tax(subtotal)
    total = round_amount(subtotal + tax - discount)
    if total < 0:
        raise HTTPException(status_code=400, detail="الخصم أكبر من قيمة الفاتورة")
    if abs(round_amount(body.tax_amount) - tax) > 0.01 or abs(round_amount(body.total_amount) - total) > 0.01:
        raise HTTPException(status_code=400, detail="الإجمالي لا يطابق الحساب")
    return unwrap(
        record_sale(
            body.customer_id,
            priced,
            total,
            discount,
            tax,
            body.payment_method.strip(),
            session_id=session["id"],
            db_path=get_db_path(),
            user_id=user["id"],
        )
    )


@router.get("/returns/lookup/{sale_id}")
def lookup_return(sale_id: int, user=Depends(get_current_user)):
    sale = get_sale_for_return(sale_id, db_path=get_db_path())
    if not sale:
        raise HTTPException(status_code=404, detail="رقم الفاتورة غير موجود")
    return {"sale": sale, "items": get_returnable_sale_items(sale_id, db_path=get_db_path())}


@router.post("/returns/preview")
def preview_return(body: ReturnIn, user=Depends(get_current_user)):
    items = [{"original_sale_item_id": item.original_sale_item_id, "quantity": item.quantity} for item in body.items]
    return unwrap(preview_sale_return(body.original_sale_id, items, body.refund_method, db_path=get_db_path()))


@router.post("/returns")
def commit_return(body: ReturnIn, user=Depends(get_current_user)):
    session = _active_session_or_error()
    items = [{"original_sale_item_id": item.original_sale_item_id, "quantity": item.quantity} for item in body.items]
    return unwrap(
        record_sale_return(
            body.original_sale_id,
            session["id"],
            items,
            body.refund_method,
            reason=body.reason,
            notes=body.notes,
            db_path=get_db_path(),
            user_id=user["id"],
        )
    )


@router.get("/returns/{return_id}")
def return_detail(return_id: int, user=Depends(get_current_user)):
    details = get_return_details(return_id, db_path=get_db_path())
    if not details:
        raise HTTPException(status_code=404, detail="فاتورة الاسترجاع غير موجودة")
    return details
