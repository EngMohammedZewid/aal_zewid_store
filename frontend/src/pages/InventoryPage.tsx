import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { api, ApiError } from "../api";
import { Modal } from "../components/Modal";
import { money, UNIT_OPTIONS, unitLabel } from "../constants";

type Product = {
  id: number;
  sku: string;
  name: string;
  category_id: number | null;
  category_code: string | null;
  category_name: string | null;
  supplier_id: number | null;
  supplier_name: string | null;
  cost_price: number;
  selling_price: number;
  stock_quantity: number;
  reorder_level: number;
};
type Category = { id: number; code: string | null; name: string; description: string | null };
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
  const [catCode, setCatCode] = useState("");
  const [catName, setCatName] = useState("");
  const [catDesc, setCatDesc] = useState("");
  const [categoryError, setCategoryError] = useState("");
  const [categorySavedKey, setCategorySavedKey] = useState(0);
  const categorySavedTimer = useRef<number | null>(null);
  const [error, setError] = useState("");
  const [savedMessage, setSavedMessage] = useState("");
  const [productFormKey, setProductFormKey] = useState(0);
  const [newCategoryId, setNewCategoryId] = useState("");
  const [generatedSku, setGeneratedSku] = useState("");
  const [skuError, setSkuError] = useState("");

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
    setSavedMessage("");
    if (product === "new") {
      setEditing("new");
      setUnits([emptyUnit()]);
      setNewCategoryId("");
      setGeneratedSku("");
      setSkuError("");
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

  useEffect(() => {
    if (editing !== "new") return;
    if (!newCategoryId) {
      setGeneratedSku("");
      setSkuError("");
      return;
    }
    let cancelled = false;
    api<{ sku: string }>(`/api/categories/${newCategoryId}/next-sku`)
      .then((result) => {
        if (cancelled) return;
        setGeneratedSku(result.sku);
        setSkuError("");
      })
      .catch((err) => {
        if (cancelled) return;
        setGeneratedSku("");
        setSkuError(err instanceof ApiError ? err.message : "تعذر إنشاء كود المنتج");
      });
    return () => { cancelled = true; };
  }, [editing, newCategoryId]);

  async function saveProduct(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const isNew = editing === "new";
    const categoryValue = isNew ? newCategoryId : String(form.get("category_id") || "");
    const payload = {
      sku: isNew ? generatedSku : String(form.get("sku") || ""),
      name: String(form.get("name") || ""),
      category_id: categoryValue ? Number(categoryValue) : null,
      supplier_id: form.get("supplier_id") ? Number(form.get("supplier_id")) : null,
      cost_price: Number(form.get("cost_price") || 0),
      selling_price: Number(form.get("selling_price") || 0),
      stock_quantity: Number(form.get("stock_quantity") || 0),
      reorder_level: Number(form.get("reorder_level") || 0),
    };
    if (isNew && !payload.category_id) {
      setSkuError("يرجى اختيار التصنيف أولاً.");
      return;
    }
    if (isNew && !generatedSku) {
      setSkuError("اختر تصنيفاً له رمز حتى يظهر كود المنتج.");
      return;
    }
    try {
      let savedId: number | null = null;
      if (isNew) {
        const created = await api<{ id: number; sku: string }>("/api/products", { method: "POST", body: JSON.stringify(payload) });
        savedId = created.id;
      } else if (editing) {
        await api(`/api/products/${editing.id}`, { method: "PUT", body: JSON.stringify(payload) });
        savedId = editing.id;
      }
      if (savedId) {
        for (const unit of units) {
          await api(`/api/products/${savedId}/units`, {
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
      if (isNew) {
        setUnits([{ unit_name: "Piece", pieces: "", cost: "", selling: "", is_default: true }]);
        setNewCategoryId("");
        setGeneratedSku("");
        setSkuError("");
        setProductFormKey((key) => key + 1);
        setSavedMessage("تم حفظ المنتج بنجاح. يمكنك إضافة المنتج التالي.");
        setError("");
      } else {
        setEditing(null);
      }
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

  function categoryLabel(category: { code?: string | null; name: string }) {
    return category.code ? `${category.code} — ${category.name}` : category.name;
  }

  useEffect(() => {
    return () => {
      if (categorySavedTimer.current !== null) window.clearTimeout(categorySavedTimer.current);
    };
  }, []);

  function clearCategorySaved() {
    if (categorySavedTimer.current !== null) {
      window.clearTimeout(categorySavedTimer.current);
      categorySavedTimer.current = null;
    }
    setCategorySavedKey(0);
  }

  async function addCategory() {
    try {
      await api("/api/categories", { method: "POST", body: JSON.stringify({ code: catCode, name: catName, description: catDesc }) });
      setCatCode("");
      setCatName("");
      setCatDesc("");
      setCategoryError("");
      await load();
      setCategorySavedKey((key) => key + 1);
      if (categorySavedTimer.current !== null) window.clearTimeout(categorySavedTimer.current);
      categorySavedTimer.current = window.setTimeout(() => {
        categorySavedTimer.current = null;
        setCategorySavedKey(0);
      }, 3000);
    } catch (err) {
      clearCategorySaved();
      setCategoryError(err instanceof ApiError ? err.message : "تعذر إضافة التصنيف");
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
          {categories.map((category) => <option key={category.id} value={category.id}>{categoryLabel(category)}</option>)}
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
                  <td>{product.id}</td><td>{product.sku}</td><td>{product.name}</td><td>{product.category_name ? categoryLabel({ code: product.category_code, name: product.category_name }) : "—"}</td><td>{product.supplier_name || "—"}</td>
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
          {savedMessage && editing === "new" && <div className="note">{savedMessage}</div>}
          <form key={productFormKey} className="form-grid" onSubmit={saveProduct}>
            {editing === "new" ? (
              <>
                <label>التصنيف
                  <select name="category_id" value={newCategoryId} onChange={(event) => setNewCategoryId(event.target.value)} required>
                    <option value="">اختر التصنيف</option>
                    {categories.map((category) => (
                      <option key={category.id} value={category.id} disabled={!category.code}>
                        {category.code ? categoryLabel(category) : `${category.name} — بدون رمز`}
                      </option>
                    ))}
                  </select>
                </label>
                <label>SKU<input name="sku" value={generatedSku} readOnly required placeholder="يظهر بعد اختيار التصنيف" /></label>
                {skuError && <div className="error">{skuError}</div>}
                {!categories.some((category) => category.code) && <div className="note">أضف رمز التصنيف أولاً من إدارة التصنيفات، ثم اختره هنا.</div>}
                <label>اسم المنتج<input name="name" required /></label>
              </>
            ) : (
              <>
                <label>SKU<input name="sku" defaultValue={draft?.sku || ""} required /></label>
                <label>اسم المنتج<input name="name" defaultValue={draft?.name || ""} required /></label>
                <label>التصنيف
                  <select name="category_id" defaultValue={draft?.category_id || ""}>
                    <option value="">بدون</option>
                    {categories.map((category) => <option key={category.id} value={category.id}>{categoryLabel(category)}</option>)}
                  </select>
                </label>
              </>
            )}
            <label>المورّد
              <select name="supplier_id" defaultValue={draft?.supplier_id || ""}>
                <option value="">بدون</option>
                {suppliers.map((supplier) => <option key={supplier.id} value={supplier.id}>{supplier.name}</option>)}
              </select>
            </label>
            <label>سعر التكلفة<input name="cost_price" type="number" step="0.01" defaultValue={draft ? draft.cost_price : ""} required /></label>
            <label>سعر البيع<input name="selling_price" type="number" step="0.01" defaultValue={draft ? draft.selling_price : ""} required /></label>
            <label>الكمية<input name="stock_quantity" type="number" defaultValue={draft ? draft.stock_quantity : ""} required /></label>
            <label>حد التنبيه<input name="reorder_level" type="number" defaultValue={draft ? draft.reorder_level : ""} required /></label>
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
        <Modal className="categories-modal" title="تصنيفات المنتجات" onClose={() => { setCategoriesOpen(false); setCategoryError(""); clearCategorySaved(); }}>
          {categoryError && <div className="error">{categoryError}</div>}
          <h3 className="category-section-title">إضافة تصنيف جديد</h3>
          <div className="category-create">
            <label className="field-code">رمز التصنيف
              <input placeholder="مثال: SN" value={catCode} maxLength={10} onChange={(event) => setCatCode(event.target.value.toUpperCase())} />
            </label>
            <label className="field-name">اسم التصنيف
              <input value={catName} onChange={(event) => setCatName(event.target.value)} />
            </label>
            <label className="field-desc">وصف التصنيف
              <input value={catDesc} onChange={(event) => setCatDesc(event.target.value)} />
            </label>
            <button type="button" className="btn btn-primary add-category-btn" onClick={addCategory}>إضافة التصنيف</button>
            {categorySavedKey > 0 && (
              <p key={categorySavedKey} className="category-saved" role="status">
                <svg className="category-check" viewBox="0 0 24 24" aria-hidden="true">
                  <path d="M5 13.2 9.2 17.4 19 7.6" />
                </svg>
                تم إضافة التصنيف بنجاح
              </p>
            )}
          </div>
          <div className="table-wrap">
            <table>
              <thead><tr><th>الرمز</th><th>الاسم</th><th>الوصف</th></tr></thead>
              <tbody>
                {categories.map((category) => (
                  <tr key={category.id}>
                    <td>{category.code || "—"}</td>
                    <td>{category.name || "—"}</td>
                    <td>{category.description || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Modal>
      )}
    </div>
  );
}
