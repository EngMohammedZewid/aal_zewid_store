import { FormEvent, useEffect, useMemo, useState } from "react";
import { api, ApiError } from "../api";
import { Modal } from "../components/Modal";
import { money, UNIT_OPTIONS, unitLabel } from "../constants";

type Product = {
  id: number;
  sku: string;
  name: string;
  category_id: number | null;
  category_name: string | null;
  supplier_id: number | null;
  supplier_name: string | null;
  cost_price: number;
  selling_price: number;
  stock_quantity: number;
  reorder_level: number;
};
type Category = { id: number; name: string; description: string | null };
type Supplier = { id: number; name: string };
type UnitRow = { unit_name: string; pieces: string; cost: string; selling: string; is_default: boolean };

const emptyUnit = (): UnitRow => ({ unit_name: "Piece", pieces: "1", cost: "", selling: "", is_default: true });

export function InventoryPage() {
  const [products, setProducts] = useState<Product[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [query, setQuery] = useState("");
  const [categoryId, setCategoryId] = useState("");
  const [lowOnly, setLowOnly] = useState(false);
  const [selected, setSelected] = useState<Product | null>(null);
  const [editing, setEditing] = useState<Product | null | "new">(null);
  const [units, setUnits] = useState<UnitRow[]>([emptyUnit()]);
  const [stockOpen, setStockOpen] = useState(false);
  const [stockQty, setStockQty] = useState("0");
  const [categoriesOpen, setCategoriesOpen] = useState(false);
  const [catName, setCatName] = useState("");
  const [catDesc, setCatDesc] = useState("");
  const [error, setError] = useState("");

  async function load() {
    const params = new URLSearchParams();
    if (lowOnly) params.set("low_stock", "true");
    if (query.trim()) params.set("q", query.trim());
    const [nextProducts, nextCategories, nextSuppliers] = await Promise.all([
      api<Product[]>(`/api/products?${params.toString()}`),
      api<Category[]>("/api/categories"),
      api<Supplier[]>("/api/suppliers/options"),
    ]);
    setProducts(nextProducts);
    setCategories(nextCategories);
    setSuppliers(nextSuppliers);
  }

  useEffect(() => { load(); }, [lowOnly]);

  const visible = useMemo(() => {
    return products.filter((product) => !categoryId || String(product.category_id) === categoryId);
  }, [products, categoryId]);

  async function openEditor(product: Product | "new") {
    setError("");
    if (product === "new") {
      setEditing("new");
      setUnits([emptyUnit()]);
      return;
    }
    setEditing(product);
    const existing = await api<Array<{ unit_name: string; pieces_per_unit: number; cost_price: number; selling_price: number; is_default: number }>>(`/api/products/${product.id}/units`);
    setUnits(existing.length ? existing.map((unit) => ({
      unit_name: unit.unit_name,
      pieces: String(unit.pieces_per_unit),
      cost: String(unit.cost_price),
      selling: String(unit.selling_price),
      is_default: Boolean(unit.is_default),
    })) : [emptyUnit()]);
  }

  async function saveProduct(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const payload = {
      sku: String(form.get("sku") || ""),
      name: String(form.get("name") || ""),
      category_id: form.get("category_id") ? Number(form.get("category_id")) : null,
      supplier_id: form.get("supplier_id") ? Number(form.get("supplier_id")) : null,
      cost_price: Number(form.get("cost_price") || 0),
      selling_price: Number(form.get("selling_price") || 0),
      stock_quantity: Number(form.get("stock_quantity") || 0),
      reorder_level: Number(form.get("reorder_level") || 0),
    };
    try {
      if (editing === "new") {
        await api("/api/products", { method: "POST", body: JSON.stringify(payload) });
      } else if (editing) {
        await api(`/api/products/${editing.id}`, { method: "PUT", body: JSON.stringify(payload) });
      }
      const refreshed = await api<Product[]>(`/api/products?q=${encodeURIComponent(payload.sku)}`);
      const saved = refreshed.find((product) => product.sku === payload.sku);
      if (saved) {
        for (const unit of units) {
          await api(`/api/products/${saved.id}/units`, {
            method: "POST",
            body: JSON.stringify({
              unit_name: unit.unit_name,
              pieces_per_unit: Number(unit.pieces),
              cost_price: Number(unit.cost || payload.cost_price),
              selling_price: Number(unit.selling || payload.selling_price),
              is_default: unit.is_default,
            }),
          });
        }
      }
      setEditing(null);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "تعذر حفظ المنتج");
    }
  }

  async function removeProduct() {
    if (!selected) return;
    if (!window.confirm(`حذف المنتج ${selected.name}؟`)) return;
    try {
      await api(`/api/products/${selected.id}`, { method: "DELETE" });
      setSelected(null);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "تعذر الحذف");
    }
  }

  async function applyStock() {
    if (!selected) return;
    try {
      await api(`/api/products/${selected.id}/stock`, { method: "POST", body: JSON.stringify({ new_quantity: Number(stockQty) }) });
      setStockOpen(false);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "تعذر تعديل المخزون");
    }
  }

  async function addCategory() {
    try {
      await api("/api/categories", { method: "POST", body: JSON.stringify({ name: catName, description: catDesc }) });
      setCatName("");
      setCatDesc("");
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "تعذر إضافة التصنيف");
    }
  }

  const draft = editing && editing !== "new" ? editing : null;

  return (
    <div>
      <div className="page-head">
        <h1>المخزون والمنتجات</h1>
        <div className="actions">
          <button className="btn btn-primary" onClick={() => openEditor("new")}>+ إضافة منتج جديد</button>
          <button className="btn btn-dark" onClick={() => setCategoriesOpen(true)}>🏷️ إدارة التصنيفات</button>
          <button className="btn btn-muted" onClick={() => setLowOnly((value) => !value)}>{lowOnly ? "عرض كل المنتجات" : "⚠️ نواقص المخزون"}</button>
        </div>
      </div>
      {error && <div className="error">{error}</div>}
      <div className="toolbar">
        <input className="grow" placeholder="بحث بالاسم أو SKU أو التصنيف" value={query} onChange={(event) => setQuery(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") load(); }} />
        <select value={categoryId} onChange={(event) => setCategoryId(event.target.value)}>
          <option value="">كل التصنيفات</option>
          {categories.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}
        </select>
        <button className="btn btn-muted" onClick={load}>بحث</button>
      </div>
      <section className="panel">
        <div className="table-wrap inventory-scroll">
          <table>
            <thead>
              <tr><th>الرقم</th><th>SKU</th><th>الاسم</th><th>التصنيف</th><th>المورّد</th><th>التكلفة</th><th>البيع</th><th>المخزون</th><th>حد التنبيه</th></tr>
            </thead>
            <tbody>
              {visible.map((product) => (
                <tr key={product.id} className={`${product.stock_quantity <= product.reorder_level ? "low-stock" : ""} ${selected?.id === product.id ? "selected" : ""} clickable`} onClick={() => setSelected(product)}>
                  <td>{product.id}</td><td>{product.sku}</td><td>{product.name}</td><td>{product.category_name || "—"}</td><td>{product.supplier_name || "—"}</td>
                  <td>{money(product.cost_price)}</td><td>{money(product.selling_price)}</td><td>{product.stock_quantity}</td><td>{product.reorder_level}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="actions" style={{ marginTop: 12 }}>
          <button className="btn btn-muted" disabled={!selected} onClick={() => selected && openEditor(selected)}>تعديل المحدد</button>
          <button className="btn btn-muted" disabled={!selected} onClick={() => { if (!selected) return; setStockQty(String(selected.stock_quantity)); setStockOpen(true); }}>تعديل المخزون</button>
          <button className="btn btn-danger" disabled={!selected} onClick={removeProduct}>حذف المحدد</button>
        </div>
      </section>

      {editing && (
        <Modal title={editing === "new" ? "إضافة منتج" : "تعديل منتج"} onClose={() => setEditing(null)}>
          <form className="form-grid" onSubmit={saveProduct}>
            <label>SKU<input name="sku" defaultValue={draft?.sku || ""} required /></label>
            <label>اسم المنتج<input name="name" defaultValue={draft?.name || ""} required /></label>
            <label>التصنيف
              <select name="category_id" defaultValue={draft?.category_id || ""}>
                <option value="">بدون</option>
                {categories.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}
              </select>
            </label>
            <label>المورّد
              <select name="supplier_id" defaultValue={draft?.supplier_id || ""}>
                <option value="">بدون</option>
                {suppliers.map((supplier) => <option key={supplier.id} value={supplier.id}>{supplier.name}</option>)}
              </select>
            </label>
            <label>سعر التكلفة<input name="cost_price" type="number" step="0.01" defaultValue={draft?.cost_price ?? 0} required /></label>
            <label>سعر البيع<input name="selling_price" type="number" step="0.01" defaultValue={draft?.selling_price ?? 0} required /></label>
            <label>الكمية<input name="stock_quantity" type="number" defaultValue={draft?.stock_quantity ?? 0} required /></label>
            <label>حد التنبيه<input name="reorder_level" type="number" defaultValue={draft?.reorder_level ?? 5} required /></label>
            <h3>وحدات البيع</h3>
            {units.map((unit, index) => (
              <div className="toolbar" key={index}>
                <select value={unit.unit_name} onChange={(event) => setUnits(units.map((row, rowIndex) => rowIndex === index ? { ...row, unit_name: event.target.value } : row))}>
                  {UNIT_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
                </select>
                <input placeholder="القطع داخل الوحدة" value={unit.pieces} onChange={(event) => setUnits(units.map((row, rowIndex) => rowIndex === index ? { ...row, pieces: event.target.value } : row))} />
                <input placeholder="تكلفة الوحدة" value={unit.cost} onChange={(event) => setUnits(units.map((row, rowIndex) => rowIndex === index ? { ...row, cost: event.target.value } : row))} />
                <input placeholder="سعر الوحدة" value={unit.selling} onChange={(event) => setUnits(units.map((row, rowIndex) => rowIndex === index ? { ...row, selling: event.target.value } : row))} />
                <label><input type="radio" checked={unit.is_default} onChange={() => setUnits(units.map((row, rowIndex) => ({ ...row, is_default: rowIndex === index })))} /> افتراضية</label>
              </div>
            ))}
            <button type="button" className="btn btn-muted" onClick={() => setUnits([...units, { ...emptyUnit(), is_default: false }])}>إضافة وحدة ({unitLabel("Piece")} / باكو / كرتونة)</button>
            <button className="btn btn-primary" type="submit">حفظ</button>
          </form>
        </Modal>
      )}

      {stockOpen && selected && (
        <Modal title="تعديل المخزون" onClose={() => setStockOpen(false)}>
          <p>{selected.name} — الحالي: {selected.stock_quantity}</p>
          <input type="number" value={stockQty} onChange={(event) => setStockQty(event.target.value)} />
          <div className="actions" style={{ marginTop: 12 }}><button className="btn btn-primary" onClick={applyStock}>تطبيق</button></div>
        </Modal>
      )}

      {categoriesOpen && (
        <Modal title="تصنيفات المنتجات" onClose={() => setCategoriesOpen(false)}>
          <table><thead><tr><th>الاسم</th><th>الوصف</th></tr></thead><tbody>{categories.map((category) => <tr key={category.id}><td>{category.name}</td><td>{category.description || "—"}</td></tr>)}</tbody></table>
          <div className="form-grid" style={{ marginTop: 12 }}>
            <input placeholder="اسم التصنيف" value={catName} onChange={(event) => setCatName(event.target.value)} />
            <input placeholder="الوصف" value={catDesc} onChange={(event) => setCatDesc(event.target.value)} />
            <button className="btn btn-primary" onClick={addCategory}>إضافة التصنيف</button>
          </div>
        </Modal>
      )}
    </div>
  );
}
