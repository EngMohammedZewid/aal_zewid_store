from typing import List, Optional

from pydantic import BaseModel


class LoginIn(BaseModel):
    username: str
    password: str


class ProductIn(BaseModel):
    sku: str
    name: str
    category_id: Optional[int] = None
    cost_price: float
    selling_price: float
    stock_quantity: int
    reorder_level: int = 5
    supplier_id: Optional[int] = None


class UnitIn(BaseModel):
    unit_name: str
    pieces_per_unit: float
    cost_price: Optional[float] = None
    selling_price: Optional[float] = None
    is_default: bool = False


class CategoryIn(BaseModel):
    name: str
    description: str = ""


class CustomerIn(BaseModel):
    name: str
    phone: str
    email: str = ""


class CustomerUpdate(BaseModel):
    name: str
    phone: str
    email: str = ""
    loyalty_points: int = 0


class SupplierIn(BaseModel):
    name: str
    contact_person: str = ""
    phone: str
    email: str = ""
    address: str = ""


class POItemIn(BaseModel):
    product_id: int
    quantity: int
    unit_cost: float


class PurchaseOrderIn(BaseModel):
    supplier_id: int
    items: List[POItemIn]


class StockIn(BaseModel):
    new_quantity: int


class OpenSessionIn(BaseModel):
    opening_balance: float
    notes: Optional[str] = None


class CloseSessionIn(BaseModel):
    actual_balance: float
    notes: Optional[str] = None


class SaleItemIn(BaseModel):
    product_id: int
    product_unit_id: Optional[int] = None
    quantity: int
    unit_price: float


class SaleIn(BaseModel):
    customer_id: Optional[int] = None
    items: List[SaleItemIn]
    discount: float = 0
    tax_amount: float
    total_amount: float
    payment_method: str


class ExpenseIn(BaseModel):
    category: str
    description: str
    amount: float
    payment_method: str = "كاش"
    reference_number: Optional[str] = None
    notes: Optional[str] = None


class ReturnItemIn(BaseModel):
    original_sale_item_id: int
    quantity: int


class ReturnIn(BaseModel):
    original_sale_id: int
    items: List[ReturnItemIn]
    refund_method: str = "نفس طريقة الدفع الأصلية"
    reason: Optional[str] = None
    notes: Optional[str] = None


class UserIn(BaseModel):
    username: str
    password: str
    role: str


class UserUpdate(BaseModel):
    role: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None
