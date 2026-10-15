import { FormEvent, useEffect, useState } from "react";
import { api, ApiError } from "../api";
import { Modal } from "../components/Modal";
import { money } from "../constants";

type Supplier = { id: number; name: string; contact_person: string | null; phone: string | null; email: string | null; address: string | null };
type Product = { id: number; name: string; sku: string; cost_price: number };
type PO = { id: number; po_date: string; supplier_name: string; total_cost: number; status: string };
type POItem = { product_name: string; sku: string; quantity: number; unit_cost: number };
type DraftItem = { product_id: number; quantity: number; unit_cost: number; name: string };

export function SuppliersPage() {
  const [tab, setTab] = useState<"suppliers" | "orders">("suppliers");
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [orders, setOrders] = useState<PO[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [adding, setAdding] = useState(false);
  const [creating, setCreating] = useState(false);
  const [supplierId, setSupplierId] = useState("");
  const [productId, setProductId] = useState("");
  const [quantity, setQuantity] = useState("1");
  const [unitCost, setUnitCost] = useState("0");
  const [draft, setDraft] = useState<DraftItem[]>([]);
  const [details, setDetails] = useState<{ po: PO; items: POItem[] } | null>(null);
  const [error, setError] = useState("");

  async function load() {
    const [nextSuppliers, nextOrders, nextProducts] = await Promise.all([
      api<Supplier[]>("/api/suppliers"),
      api<PO[]>("/api/purchase-orders"),
      api<Product[]>("/api/products"),
    ]);
    setSuppliers(nextSuppliers);
    setOrders(nextOrders);
    setProducts(nextProducts);
  }

  useEffect(() => { load(); }, []);

  async function saveSupplier(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    try {
      await api("/api/suppliers", {
        method: "POST",
        body: JSON.stringify({
          name: form.get("name"),
          contact_person: form.get("contact_person"),
          phone: form.get("phone"),
          email: form.get("email"),
          address: form.get("address"),
        }),
      });
      setAdding(false);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "تعذر حفظ المورّد");
    }
  }

  function addDraft() {
    const product = products.find((item) => item.id === Number(productId));
    if (!product || Number(quantity) <= 0) return;
    setDraft([...draft, { product_id: product.id, quantity: Number(quantity), unit_cost: Number(unitCost), name: product.name }]);
  }

  async function saveOrder() {
    try {
      await api("/api/purchase-orders", {
        method: "POST",
        body: JSON.stringify({ supplier_id: Number(supplierId), items: draft.map(({ product_id, quantity: qty, unit_cost }) => ({ product_id, quantity: qty, unit_cost })) }),
      });
      setCreating(false);
      setDraft([]);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "تعذر إنشاء أمر الشراء");
    }
  }

  async function receive(po: PO) {
    try {
      await api(`/api/purchase-orders/${po.id}/receive`, { method: "POST" });
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "تعذر الاستلام");
    }
  }

  async function view(po: PO) {
    const items = await api<POItem[]>(`/api/purchase-orders/${po.id}/items`);
    setDetails({ po, items });
  }

  const draftTotal = draft.reduce((sum, item) => sum + item.quantity * item.unit_cost, 0);

  return (
    <div>
      <div className="page-head"><h1>المورّدون وطلبات الشراء</h1></div>
      {error && <div className="error">{error}</div>}
      <div className="tabs">
        <button className={tab === "suppliers" ? "active" : ""} onClick={() => setTab("suppliers")}>دليل المورّدين</button>
        <button className={tab === "orders" ? "active" : ""} onClick={() => setTab("orders")}>أوامر الشراء</button>
      </div>
      {tab === "suppliers" ? (
        <section className="panel">
          <div className="page-head"><h2>الشركات والمورّدون</h2><button className="btn btn-primary" onClick={() => setAdding(true)}>+ إضافة مورّد جديد</button></div>
          <table>
            <thead><tr><th>الرقم</th><th>الاسم</th><th>المسؤول</th><th>الهاتف</th><th>البريد</th><th>العنوان</th></tr></thead>
            <tbody>{suppliers.map((supplier) => <tr key={supplier.id}><td>{supplier.id}</td><td>{supplier.name}</td><td>{supplier.contact_person || "—"}</td><td>{supplier.phone || "—"}</td><td>{supplier.email || "—"}</td><td>{supplier.address || "—"}</td></tr>)}</tbody>
          </table>
        </section>
      ) : (
        <section className="panel">
          <div className="page-head"><h2>سجل أوامر الشراء</h2><button className="btn btn-green" onClick={() => setCreating(true)}>إنشاء أمر شراء</button></div>
          <table>
            <thead><tr><th>الرقم</th><th>التاريخ</th><th>المورّد</th><th>التكلفة</th><th>الحالة</th><th></th></tr></thead>
            <tbody>
              {orders.map((order) => (
                <tr key={order.id}>
                  <td>{order.id}</td><td>{order.po_date}</td><td>{order.supplier_name}</td><td>{money(order.total_cost)}</td>
                  <td className={order.status === "تم الاستلام" ? "status-open" : "status-closed"}>{order.status}</td>
                  <td>
                    <button className="btn btn-muted" onClick={() => view(order)}>التفاصيل</button>{" "}
                    <button className="btn btn-primary" disabled={order.status === "تم الاستلام"} onClick={() => receive(order)}>تسجيل الاستلام</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
      {adding && (
        <Modal title="إضافة مورّد" onClose={() => setAdding(false)}>
          <form className="form-grid" onSubmit={saveSupplier}>
            <label>اسم الشركة<input name="name" required /></label>
            <label>الشخص المسؤول<input name="contact_person" /></label>
            <label>الهاتف<input name="phone" required /></label>
            <label>البريد<input name="email" /></label>
            <label>العنوان<input name="address" /></label>
            <button className="btn btn-primary" type="submit">حفظ</button>
          </form>
        </Modal>
      )}
      {creating && (
        <Modal title="أمر شراء جديد" onClose={() => setCreating(false)}>
          <div className="form-grid">
            <label>المورّد
              <select value={supplierId} onChange={(event) => setSupplierId(event.target.value)}>
                <option value="">اختر</option>
                {suppliers.map((supplier) => <option key={supplier.id} value={supplier.id}>{supplier.name}</option>)}
              </select>
            </label>
            <div className="toolbar">
              <select value={productId} onChange={(event) => setProductId(event.target.value)}>
                <option value="">المنتج</option>
                {products.map((product) => <option key={product.id} value={product.id}>{product.name}</option>)}
              </select>
              <input type="number" value={quantity} onChange={(event) => setQuantity(event.target.value)} />
              <input type="number" step="0.01" value={unitCost} onChange={(event) => setUnitCost(event.target.value)} />
              <button className="btn btn-muted" type="button" onClick={addDraft}>إضافة</button>
            </div>
            <ul>{draft.map((item, index) => <li key={index}>{item.name} × {item.quantity} @ {money(item.unit_cost)}</li>)}</ul>
            <strong>الإجمالي: {money(draftTotal)}</strong>
            <button className="btn btn-primary" disabled={!supplierId || draft.length === 0} onClick={saveOrder}>حفظ الأمر</button>
          </div>
        </Modal>
      )}
      {details && (
        <Modal title={`أمر شراء #${details.po.id}`} onClose={() => setDetails(null)}>
          <table>
            <thead><tr><th>المنتج</th><th>الكمية</th><th>تكلفة الوحدة</th></tr></thead>
            <tbody>{details.items.map((item, index) => <tr key={index}><td>[{item.sku}] {item.product_name}</td><td>{item.quantity}</td><td>{money(item.unit_cost)}</td></tr>)}</tbody>
          </table>
        </Modal>
      )}
    </div>
  );
}
