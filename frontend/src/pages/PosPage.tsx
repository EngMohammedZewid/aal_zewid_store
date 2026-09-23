import { FormEvent, useEffect, useMemo, useState } from "react";
import { api, ApiError } from "../api";
import { Modal } from "../components/Modal";
import {
  EXPENSE_CATEGORIES,
  EXPENSE_PAYMENT_METHODS,
  money,
  PAYMENT_METHODS,
  RETURN_REASONS,
  RETURN_REFUND_METHODS,
  roundMoney,
  taxOf,
  unitLabel,
} from "../constants";

type Product = { id: number; sku: string; name: string; selling_price: number; category_name: string | null; stock_quantity: number };
type Unit = { id: number; unit_name: string; selling_price: number; pieces_per_unit: number; is_default: number };
type Customer = { id: number; name: string; phone: string | null };
type CartLine = {
  key: string;
  product_id: number;
  product_unit_id: number;
  name: string;
  unit_name: string;
  quantity: number;
  unit_price: number;
};
type Session = { id: number; opened_at: string; opening_balance: number; status: string; opening_notes?: string | null };
type Summary = {
  expected_cash_balance: number;
  cash_sales: number;
  cash_returns: number;
  cash_expenses: number;
  total_sales: number;
  total_returns: number;
  total_expenses: number;
  sales_count: number;
  returns_count: number;
  expenses_count: number;
  opening_balance: number;
  status: string;
  difference?: number | null;
  actual_closing_balance?: number | null;
};
type Returnable = {
  id: number;
  product_name: string;
  sku: string;
  quantity: number;
  returned_quantity: number;
  available_return_quantity: number;
  unit_price: number;
};
type Expense = { id: number; expense_date: string; category: string; description: string; amount: number; payment_method: string; notes?: string | null; reference_number?: string | null };

export function PosPage() {
  const [products, setProducts] = useState<Product[]>([]);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [genericId, setGenericId] = useState<number | null>(null);
  const [query, setQuery] = useState("");
  const [cart, setCart] = useState<CartLine[]>([]);
  const [customerId, setCustomerId] = useState("");
  const [discount, setDiscount] = useState("0");
  const [payment, setPayment] = useState(PAYMENT_METHODS[0]);
  const [session, setSession] = useState<Session | null>(null);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);
  const [units, setUnits] = useState<Unit[]>([]);
  const [unitId, setUnitId] = useState<number | null>(null);
  const [qty, setQty] = useState("1");
  const [openModal, setOpenModal] = useState(false);
  const [closeModal, setCloseModal] = useState(false);
  const [expenseModal, setExpenseModal] = useState(false);
  const [returnModal, setReturnModal] = useState(false);
  const [historyModal, setHistoryModal] = useState(false);
  const [customerModal, setCustomerModal] = useState(false);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [report, setReport] = useState<Summary | null>(null);

  async function loadSession() {
    const payload = await api<{ session: Session | null; summary: Summary | null }>("/api/pos/session");
    setSession(payload.session);
    setSummary(payload.summary);
  }

  async function loadCatalog() {
    const [nextProducts, nextCustomers, generic] = await Promise.all([
      api<Product[]>("/api/products"),
      api<Customer[]>("/api/customers"),
      api<{ id: number | null }>("/api/customers/generic"),
    ]);
    setProducts(nextProducts);
    setCustomers(nextCustomers);
    setGenericId(generic.id);
    setCustomerId((current) => current || (generic.id ? String(generic.id) : ""));
  }

  useEffect(() => {
    loadCatalog();
    loadSession();
  }, []);

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return products;
    return products.filter((product) =>
      product.name.toLowerCase().includes(needle) ||
      product.sku.toLowerCase().includes(needle) ||
      (product.category_name || "").toLowerCase().includes(needle)
    );
  }, [products, query]);

  const subtotal = roundMoney(cart.reduce((sum, line) => sum + line.quantity * line.unit_price, 0));
  const discountValue = roundMoney(Number(discount || 0));
  const tax = taxOf(subtotal);
  const total = roundMoney(subtotal + tax - discountValue);

  async function chooseProduct(product: Product) {
    setSelectedProduct(product);
    const nextUnits = await api<Unit[]>(`/api/products/${product.id}/units`);
    setUnits(nextUnits);
    const preferred = nextUnits.find((unit) => unit.is_default) || nextUnits[0];
    setUnitId(preferred ? preferred.id : null);
    setQty("1");
  }

  function addToCart() {
    if (!selectedProduct || unitId == null) return;
    const unit = units.find((item) => item.id === unitId);
    if (!unit) return;
    const quantity = Number(qty);
    if (!Number.isInteger(quantity) || quantity <= 0) {
      setError("الكمية غير صحيحة");
      return;
    }
    setError("");
    setCart((current) => {
      const key = `${selectedProduct.id}-${unit.id}`;
      const existing = current.find((line) => line.key === key);
      if (existing) {
        return current.map((line) => line.key === key ? { ...line, quantity: line.quantity + quantity } : line);
      }
      return [...current, {
        key,
        product_id: selectedProduct.id,
        product_unit_id: unit.id,
        name: selectedProduct.name,
        unit_name: unit.unit_name,
        quantity,
        unit_price: unit.selling_price,
      }];
    });
  }

  function updateLine(key: string, delta: number) {
    setCart((current) => current.flatMap((line) => {
      if (line.key !== key) return [line];
      const quantity = line.quantity + delta;
      return quantity <= 0 ? [] : [{ ...line, quantity }];
    }));
  }

  async function checkout() {
    setError("");
    setNotice("");
    try {
      const result = await api<{ id: number }>("/api/pos/sales", {
        method: "POST",
        body: JSON.stringify({
          customer_id: customerId ? Number(customerId) : genericId,
          discount: discountValue,
          tax_amount: tax,
          total_amount: total,
          payment_method: payment,
          items: cart.map((line) => ({
            product_id: line.product_id,
            product_unit_id: line.product_unit_id,
            quantity: line.quantity,
            unit_price: line.unit_price,
          })),
        }),
      });
      setNotice(`تم إصدار الفاتورة رقم #${result.id} بمبلغ ${money(total)}`);
      setCart([]);
      setDiscount("0");
      await loadSession();
      await loadCatalog();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "تعذر إتمام البيع");
    }
  }

  async function openSession(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    try {
      await api("/api/pos/session", { method: "POST", body: JSON.stringify({ opening_balance: Number(form.get("opening_balance")), notes: form.get("notes") }) });
      setOpenModal(false);
      await loadSession();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "تعذر فتح الجلسة");
    }
  }

  async function closeSession(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    try {
      await api("/api/pos/session/close", { method: "POST", body: JSON.stringify({ actual_balance: Number(form.get("actual_balance")), notes: form.get("notes") }) });
      setCloseModal(false);
      await loadSession();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "تعذر إغلاق الجلسة");
    }
  }

  return (
    <div>
      <div className="page-head"><h1>نقطة البيع</h1></div>
      {error && <div className="error">{error}</div>}
      {notice && <div className="note">{notice}</div>}
      <section className="panel session-bar">
        <div>
          <strong>{session ? `جلسة #${session.id}` : "لا توجد جلسة كاشير مفتوحة"}</strong>
          {session && <p className="hint">فُتحت {session.opened_at} — افتتاحي {money(session.opening_balance)} — النقدي المتوقع {money(summary?.expected_cash_balance || 0)}</p>}
        </div>
        <div className="actions">
          <button className="btn btn-green" onClick={() => setOpenModal(true)} disabled={Boolean(session)}>فتح جلسة</button>
          <button className="btn btn-danger" onClick={() => setCloseModal(true)} disabled={!session}>إغلاق الجلسة</button>
          <button className="btn btn-muted" onClick={() => setExpenseModal(true)} disabled={!session}>مصروف</button>
          <button className="btn btn-muted" onClick={() => setReturnModal(true)} disabled={!session}>استرجاع</button>
          <button className="btn btn-muted" onClick={async () => { setSessions(await api<Session[]>("/api/pos/sessions")); setHistoryModal(true); }}>سجل الجلسات</button>
        </div>
      </section>
      <div className="pos-layout">
        <section className="panel">
          <h2>السلة</h2>
          <div className="toolbar">
            <select value={customerId} onChange={(event) => setCustomerId(event.target.value)}>
              {customers.map((customer) => <option key={customer.id} value={customer.id}>{customer.name}</option>)}
            </select>
            <button className="btn btn-muted" onClick={() => setCustomerModal(true)}>عميل جديد</button>
          </div>
          <table>
            <thead><tr><th>المنتج</th><th>الوحدة</th><th>الكمية</th><th>السعر</th><th>المجموع</th><th></th></tr></thead>
            <tbody>
              {cart.map((line) => (
                <tr key={line.key}>
                  <td>{line.name}</td>
                  <td>{unitLabel(line.unit_name)}</td>
                  <td>{line.quantity}</td>
                  <td>{money(line.unit_price)}</td>
                  <td>{money(line.quantity * line.unit_price)}</td>
                  <td>
                    <button className="btn btn-muted" onClick={() => updateLine(line.key, 1)}>+</button>
                    <button className="btn btn-muted" onClick={() => updateLine(line.key, -1)}>-</button>
                    <button className="btn btn-danger" onClick={() => setCart(cart.filter((item) => item.key !== line.key))}>حذف</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="totals">
            <div><span>المجموع الفرعي</span><strong>{money(subtotal)}</strong></div>
            <div><span>الضريبة 8%</span><strong>{money(tax)}</strong></div>
            <label>خصم إضافي<input type="number" step="0.01" value={discount} onChange={(event) => setDiscount(event.target.value)} /></label>
            <div className="final"><span>الإجمالي</span><span>{money(total)}</span></div>
          </div>
          <label>طريقة الدفع
            <select value={payment} onChange={(event) => setPayment(event.target.value)}>
              {PAYMENT_METHODS.map((method) => <option key={method}>{method}</option>)}
            </select>
          </label>
          <button className="btn btn-green" style={{ marginTop: 12, width: "100%" }} disabled={!session || cart.length === 0} onClick={checkout}>تأكيد العملية</button>
        </section>
        <section className="panel">
          <h2>الكتالوج</h2>
          <input className="grow" placeholder="بحث بالاسم أو الباركود" value={query} onChange={(event) => setQuery(event.target.value)} />
          <div className="table-wrap catalog-scroll">
            <table>
              <thead><tr><th>SKU</th><th>المنتج</th><th>السعر</th><th>المخزون</th></tr></thead>
              <tbody>
                {filtered.map((product) => (
                  <tr key={product.id} className={`clickable ${selectedProduct?.id === product.id ? "selected" : ""}`} onClick={() => chooseProduct(product)}>
                    <td>{product.sku}</td><td>{product.name}</td><td>{money(product.selling_price)}</td><td>{product.stock_quantity}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {selectedProduct && (
            <div className="toolbar" style={{ marginTop: 12 }}>
              <strong>{selectedProduct.name}</strong>
              <select value={unitId ?? ""} onChange={(event) => setUnitId(Number(event.target.value))}>
                {units.map((unit) => <option key={unit.id} value={unit.id}>{unitLabel(unit.unit_name)} — {money(unit.selling_price)}</option>)}
              </select>
              <input type="number" min={1} value={qty} onChange={(event) => setQty(event.target.value)} />
              <button className="btn btn-primary" onClick={addToCart}>إضافة للسلة</button>
            </div>
          )}
        </section>
      </div>

      {openModal && (
        <Modal title="فتح جلسة الكاشير" onClose={() => setOpenModal(false)}>
          <form className="form-grid" onSubmit={openSession}>
            <label>الرصيد الافتتاحي<input name="opening_balance" type="number" step="0.01" required /></label>
            <label>ملاحظات<textarea name="notes" /></label>
            <button className="btn btn-green" type="submit">فتح</button>
          </form>
        </Modal>
      )}
      {closeModal && summary && (
        <Modal title="إغلاق جلسة الكاشير" onClose={() => setCloseModal(false)}>
          <p>المتوقع = الافتتاحي {money(summary.opening_balance)} + مبيعات نقدية {money(summary.cash_sales)} - مرتجعات نقدية {money(summary.cash_returns)} - مصروفات نقدية {money(summary.cash_expenses)}</p>
          <p><strong>الرصيد المتوقع: {money(summary.expected_cash_balance)}</strong></p>
          <form className="form-grid" onSubmit={closeSession}>
            <label>الرصيد الفعلي في الدرج<input name="actual_balance" type="number" step="0.01" required /></label>
            <label>ملاحظات<textarea name="notes" /></label>
            <button className="btn btn-danger" type="submit">إغلاق الجلسة</button>
          </form>
        </Modal>
      )}
      {expenseModal && session && <ExpenseDialog sessionId={session.id} onClose={() => { setExpenseModal(false); loadSession(); }} onError={setError} />}
      {returnModal && <ReturnDialog onClose={() => { setReturnModal(false); loadSession(); loadCatalog(); }} onError={setError} onDone={setNotice} />}
      {customerModal && <NewCustomer onClose={() => setCustomerModal(false)} onCreated={async (id) => { await loadCatalog(); setCustomerId(String(id)); setCustomerModal(false); }} />}
      {historyModal && (
        <Modal title="سجل جلسات الكاشير" onClose={() => { setHistoryModal(false); setReport(null); }}>
          {report ? (
            <div>
              <p>الحالة: {report.status} — المبيعات {money(report.total_sales)} — المرتجعات {money(report.total_returns)} — المصروفات {money(report.total_expenses)}</p>
              <p>النقدي المتوقع {money(report.expected_cash_balance)} — الفعلي {report.actual_closing_balance == null ? "—" : money(report.actual_closing_balance)} — الفرق {report.difference == null ? "—" : money(report.difference)}</p>
              <button className="btn btn-muted" onClick={() => setReport(null)}>رجوع</button>
            </div>
          ) : (
            <table>
              <thead><tr><th>الرقم</th><th>الفتح</th><th>الحالة</th><th></th></tr></thead>
              <tbody>
                {sessions.map((item) => (
                  <tr key={item.id}>
                    <td>{item.id}</td><td>{item.opened_at}</td><td>{item.status}</td>
                    <td><button className="btn btn-muted" onClick={async () => setReport(await api<Summary>(`/api/pos/sessions/${item.id}/summary`))}>التقرير</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Modal>
      )}
    </div>
  );
}

function ExpenseDialog({ sessionId, onClose, onError }: { sessionId: number; onClose: () => void; onError: (message: string) => void }) {
  const [expenses, setExpenses] = useState<Expense[]>([]);
  const [selected, setSelected] = useState<Expense | null>(null);

  async function load() {
    setExpenses(await api<Expense[]>(`/api/pos/sessions/${sessionId}/expenses`));
  }
  useEffect(() => { load(); }, [sessionId]);

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    try {
      await api("/api/pos/expenses", {
        method: "POST",
        body: JSON.stringify({
          category: form.get("category"),
          description: form.get("description"),
          amount: Number(form.get("amount")),
          payment_method: form.get("payment_method"),
          reference_number: form.get("reference_number"),
          notes: form.get("notes"),
        }),
      });
      await load();
      event.currentTarget.reset();
    } catch (err) {
      onError(err instanceof ApiError ? err.message : "تعذر تسجيل المصروف");
    }
  }

  async function remove(expenseId: number) {
    try {
      await api(`/api/pos/expenses/${expenseId}`, { method: "DELETE" });
      setSelected(null);
      await load();
    } catch (err) {
      onError(err instanceof ApiError ? err.message : "تعذر حذف المصروف");
    }
  }

  return (
    <Modal title="مصروفات الجلسة" onClose={onClose}>
      <form className="form-grid" onSubmit={save}>
        <label>النوع
          <select name="category" defaultValue={EXPENSE_CATEGORIES[0]}>{EXPENSE_CATEGORIES.map((category) => <option key={category}>{category}</option>)}</select>
        </label>
        <label>الوصف<input name="description" required /></label>
        <label>المبلغ<input name="amount" type="number" step="0.01" required /></label>
        <label>طريقة الدفع
          <select name="payment_method" defaultValue={EXPENSE_PAYMENT_METHODS[0]}>{EXPENSE_PAYMENT_METHODS.map((method) => <option key={method}>{method}</option>)}</select>
        </label>
        <label>رقم المرجع<input name="reference_number" /></label>
        <label>ملاحظات<textarea name="notes" /></label>
        <button className="btn btn-primary" type="submit">تسجيل المصروف</button>
      </form>
      <table>
        <thead><tr><th>الرقم</th><th>التاريخ</th><th>النوع</th><th>المبلغ</th><th>الدفع</th></tr></thead>
        <tbody>
          {expenses.map((expense) => (
            <tr key={expense.id} className="clickable" onClick={async () => setSelected(await api<Expense>(`/api/pos/expenses/${expense.id}`))}>
              <td>{expense.id}</td><td>{expense.expense_date}</td><td>{expense.category}</td><td>{money(expense.amount)}</td><td>{expense.payment_method}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {selected && (
        <div className="note">
          <p>{selected.description} — {money(selected.amount)} — {selected.payment_method}</p>
          <button className="btn btn-danger" onClick={() => remove(selected.id)}>حذف المصروف</button>
        </div>
      )}
    </Modal>
  );
}

function ReturnDialog({ onClose, onError, onDone }: { onClose: () => void; onError: (message: string) => void; onDone: (message: string) => void }) {
  const [saleId, setSaleId] = useState("");
  const [sale, setSale] = useState<{ id: number; payment_method: string; customer_name?: string | null; total_amount: number } | null>(null);
  const [items, setItems] = useState<Returnable[]>([]);
  const [quantities, setQuantities] = useState<Record<number, string>>({});
  const [refundMethod, setRefundMethod] = useState(RETURN_REFUND_METHODS[3]);
  const [reason, setReason] = useState(RETURN_REASONS[0]);
  const [preview, setPreview] = useState<{ totals: { total_amount: number; tax_amount: number; discount_amount: number; subtotal: number } } | null>(null);

  async function lookup() {
    try {
      const result = await api<{ sale: { id: number; payment_method: string; customer_name?: string | null; total_amount: number }; items: Returnable[] }>(`/api/pos/returns/lookup/${saleId}`);
      setSale(result.sale);
      setItems(result.items);
      setPreview(null);
    } catch (err) {
      onError(err instanceof ApiError ? err.message : "الفاتورة غير موجودة");
    }
  }

  function payloadItems() {
    return items
      .map((item) => ({ original_sale_item_id: item.id, quantity: Number(quantities[item.id] || 0) }))
      .filter((item) => item.quantity > 0);
  }

  async function previewReturn() {
    try {
      const result = await api<{ totals: { total_amount: number; tax_amount: number; discount_amount: number; subtotal: number } }>("/api/pos/returns/preview", {
        method: "POST",
        body: JSON.stringify({ original_sale_id: Number(saleId), refund_method: refundMethod, reason, items: payloadItems() }),
      });
      setPreview(result);
    } catch (err) {
      onError(err instanceof ApiError ? err.message : "تعذر حساب الاسترجاع");
    }
  }

  async function commit() {
    try {
      const result = await api<{ id: number }>("/api/pos/returns", {
        method: "POST",
        body: JSON.stringify({ original_sale_id: Number(saleId), refund_method: refundMethod, reason, items: payloadItems() }),
      });
      onDone(`تم إصدار فاتورة الاسترجاع #${result.id}`);
      onClose();
    } catch (err) {
      onError(err instanceof ApiError ? err.message : "تعذر حفظ الاسترجاع");
    }
  }

  return (
    <Modal title="فاتورة استرجاع" onClose={onClose}>
      <div className="toolbar">
        <input placeholder="رقم الفاتورة الأصلية" value={saleId} onChange={(event) => setSaleId(event.target.value)} />
        <button className="btn btn-muted" onClick={lookup}>بحث</button>
      </div>
      {sale && <p>فاتورة #{sale.id} — {sale.customer_name || "عميل عام"} — {sale.payment_method} — {money(sale.total_amount)}</p>}
      <table>
        <thead><tr><th>المنتج</th><th>المباع</th><th>المسترجع</th><th>المتاح</th><th>كمية الاسترجاع</th></tr></thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.id}>
              <td>[{item.sku}] {item.product_name}</td>
              <td>{item.quantity}</td>
              <td>{item.returned_quantity}</td>
              <td>{item.available_return_quantity}</td>
              <td><input type="number" min={0} max={item.available_return_quantity} value={quantities[item.id] || ""} onChange={(event) => setQuantities({ ...quantities, [item.id]: event.target.value })} /></td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="form-grid" style={{ marginTop: 12 }}>
        <label>طريقة الاسترجاع
          <select value={refundMethod} onChange={(event) => setRefundMethod(event.target.value)}>{RETURN_REFUND_METHODS.map((method) => <option key={method}>{method}</option>)}</select>
        </label>
        <label>السبب
          <select value={reason} onChange={(event) => setReason(event.target.value)}>{RETURN_REASONS.map((item) => <option key={item}>{item}</option>)}</select>
        </label>
        {preview && <p>المسترجع: {money(preview.totals.total_amount)} (ضريبة {money(preview.totals.tax_amount)} / خصم {money(preview.totals.discount_amount)})</p>}
        <div className="actions">
          <button className="btn btn-muted" onClick={previewReturn}>معاينة</button>
          <button className="btn btn-primary" onClick={commit}>اعتماد الاسترجاع</button>
        </div>
      </div>
    </Modal>
  );
}

function NewCustomer({ onClose, onCreated }: { onClose: () => void; onCreated: (id: number) => void }) {
  const [error, setError] = useState("");
  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    try {
      await api("/api/customers", {
        method: "POST",
        body: JSON.stringify({ name: form.get("name"), phone: form.get("phone"), email: form.get("email") }),
      });
      const customers = await api<Customer[]>("/api/customers");
      const created = customers.find((customer) => customer.phone === String(form.get("phone")));
      if (created) onCreated(created.id);
      else onClose();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "تعذر إضافة العميل");
    }
  }
  return (
    <Modal title="عميل جديد" onClose={onClose}>
      {error && <div className="error">{error}</div>}
      <form className="form-grid" onSubmit={save}>
        <label>الاسم<input name="name" required /></label>
        <label>الهاتف<input name="phone" required /></label>
        <label>البريد<input name="email" /></label>
        <button className="btn btn-primary" type="submit">حفظ</button>
      </form>
    </Modal>
  );
}
