from fastapi import APIRouter, Depends, HTTPException

from api.deps import get_current_user, get_db_path, require_manager, unwrap
from api.schemas import CategoryCodeIn, CategoryIn, ProductIn, StockIn, UnitIn
from core.db import (
    add_category,
    add_product_with_category_sku,
    adjust_stock,
    delete_product,
    ensure_product_unit,
    get_all_categories,
    get_all_products,
    get_all_suppliers,
    get_low_stock_products,
    get_product_units,
    preview_product_sku,
    search_products,
    update_category_code,
    update_product,
)

router = APIRouter(prefix="/api", tags=["catalog"])


def _empty_to_none(value):
    return value if value else None


@router.get("/products")
def list_products(low_stock: bool = False, q: str = "", user=Depends(get_current_user)):
    db_path = get_db_path()
    if q.strip():
        return search_products(q.strip(), db_path=db_path)
    if low_stock:
        return get_low_stock_products(db_path=db_path)
    return get_all_products(db_path=db_path)


@router.get("/products/{product_id}/units")
def list_units(product_id: int, user=Depends(get_current_user)):
    return get_product_units(product_id, db_path=get_db_path())


@router.post("/products")
def create_product(body: ProductIn, user=Depends(require_manager)):
    if not body.category_id:
        raise HTTPException(status_code=400, detail="يرجى اختيار التصنيف أولاً.")
    return unwrap(
        add_product_with_category_sku(
            body.name.strip(),
            body.category_id,
            body.cost_price,
            body.selling_price,
            body.stock_quantity,
            body.reorder_level,
            _empty_to_none(body.supplier_id),
            db_path=get_db_path(),
        )
    )


@router.put("/products/{product_id}")
def edit_product(product_id: int, body: ProductIn, user=Depends(require_manager)):
    if not body.sku.strip():
        raise HTTPException(status_code=400, detail="كود المنتج مطلوب")
    return unwrap(
        update_product(
            product_id,
            body.sku.strip(),
            body.name.strip(),
            _empty_to_none(body.category_id),
            body.cost_price,
            body.selling_price,
            body.stock_quantity,
            body.reorder_level,
            _empty_to_none(body.supplier_id),
            db_path=get_db_path(),
        )
    )


@router.delete("/products/{product_id}")
def remove_product(product_id: int, user=Depends(require_manager)):
    return unwrap(delete_product(product_id, db_path=get_db_path()))


@router.post("/products/{product_id}/stock")
def set_stock(product_id: int, body: StockIn, user=Depends(require_manager)):
    if body.new_quantity < 0:
        raise HTTPException(status_code=400, detail="كمية المخزون غير صحيحة")
    return unwrap(adjust_stock(product_id, body.new_quantity, db_path=get_db_path()))


@router.post("/products/{product_id}/units")
def save_unit(product_id: int, body: UnitIn, user=Depends(require_manager)):
    return unwrap(
        ensure_product_unit(
            product_id,
            body.unit_name.strip(),
            body.pieces_per_unit,
            cost_price=body.cost_price,
            selling_price=body.selling_price,
            is_default=body.is_default,
            db_path=get_db_path(),
        )
    )


@router.get("/categories")
def list_categories(user=Depends(get_current_user)):
    return get_all_categories(db_path=get_db_path())


@router.get("/categories/{category_id}/next-sku")
def next_category_sku(category_id: int, user=Depends(require_manager)):
    return unwrap(preview_product_sku(category_id, db_path=get_db_path()))


@router.post("/categories")
def create_category(body: CategoryIn, user=Depends(require_manager)):
    return unwrap(add_category(body.code, body.name, body.description, db_path=get_db_path()))


@router.put("/categories/{category_id}")
def edit_category_code(category_id: int, body: CategoryCodeIn, user=Depends(require_manager)):
    return unwrap(update_category_code(category_id, body.code, db_path=get_db_path()))


@router.get("/suppliers/options")
def supplier_options(user=Depends(get_current_user)):
    return get_all_suppliers(db_path=get_db_path())
