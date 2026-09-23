import { FormEvent, useEffect, useMemo, useState } from "react";
import { api, ApiError } from "../api";
import { Modal } from "../components/Modal";
import { money } from "../constants";

type Customer = { id: number; name: string; phone: string | null; email: string | null; loyalty_points: number };
type Sale = { id: number; sale_date: string; total_amount: number; payment_method: string };

export function CustomersPage() {
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [genericId, setGenericId] = useState<number | null>(null);
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<Customer | null>(null);
  const [editing, setEditing] = useState<Customer | "new" | null>(null);
  const [history, setHistory] = useState<{ customer: Customer; sales: Sale[] } | null>(null);
  const [error, setError] = useState("");

  async function load() {
    const [rows, generic] = await Promise.all([
      api<Customer[]>("/api/customers"),
      api<{ id: number | null }>("/api/customers/generic"),
    ]);
    setCustomers(rows);
    setGenericId(generic.id);
  }

  useEffect(() => { load(); }, []);

  const visible = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return customers;
    return customers.filter((customer) =>
      customer.name.toLowerCase().includes(needle) ||
      (customer.phone || "").toLowerCase().includes(needle) ||
      (customer.email || "").toLowerCase().includes(needle)
    );
  }, [customers, query]);

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const payload = {
      name: String(form.get("name") || ""),
      phone: String(form.get("phone") || ""),
      email: String(form.get("email") || ""),
      loyalty_points: Number(form.get("loyalty_points") || 0),
    };
    try {
      if (editing === "new") {
        await api("/api/customers", { method: "POST", body: JSON.stringify(payload) });
      } else if (editing) {
        await api(`/api/customers/${editing.id}`, { method: "PUT", body: JSON.stringify(payload) });
      }
      setEditing(null);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "تعذر حفظ العميل");
    }
  }

  async function remove() {
    if (!selected) return;
    if (selected.id === genericId) {
      setError("لا يمكن حذف العميل الافتراضي العام.");
      return;
    }
    if (!window.confirm(`حذف العميل ${selected.name}؟`)) return;
    try {
      await api(`/api/customers/${selected.id}`, { method: "DELETE" });
      setSelected(null);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "تعذر الحذف");
    }
  }

  async function openHistory(customer: Customer) {
    const sales = await api<Sale[]>(`/api/customers/${customer.id}/sales`);
    setHistory({ customer, sales });
  }

  const draft = editing && editing !== "new" ? editing : null;

  return (
    <div>
      <div className="page-head">
        <h1>العملاء والولاء</h1>
        <button className="btn btn-primary" onClick={() => setEditing("new")}>+ عميل جديد</button>
      </div>
      {error && <div className="error">{error}</div>}
      <div className="toolbar"><input className="grow" placeholder="بحث بالاسم أو الهاتف أو البريد" value={query} onChange={(event) => setQuery(event.target.value)} /></div>
      <section className="panel">
        <table>
          <thead><tr><th>الرقم</th><th>الاسم</th><th>الهاتف</th><th>البريد</th><th>نقاط الولاء</th></tr></thead>
          <tbody>
            {visible.map((customer) => (
              <tr key={customer.id} className={`clickable ${selected?.id === customer.id ? "selected" : ""}`} onClick={() => setSelected(customer)} onDoubleClick={() => openHistory(customer)}>
                <td>{customer.id}</td><td>{customer.name}</td><td>{customer.phone || "—"}</td><td>{customer.email || "—"}</td><td>{customer.loyalty_points}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="actions" style={{ marginTop: 12 }}>
          <button className="btn btn-muted" disabled={!selected} onClick={() => selected && setEditing(selected)}>تعديل</button>
          <button className="btn btn-muted" disabled={!selected} onClick={() => selected && openHistory(selected)}>سجل المشتريات</button>
          <button className="btn btn-danger" disabled={!selected} onClick={remove}>حذف</button>
        </div>
      </section>
      {editing && (
        <Modal title={editing === "new" ? "عميل جديد" : "تعديل العميل"} onClose={() => setEditing(null)}>
          <form className="form-grid" onSubmit={save}>
            <label>الاسم<input name="name" defaultValue={draft?.name || ""} required /></label>
            <label>الهاتف<input name="phone" defaultValue={draft?.phone || ""} required /></label>
            <label>البريد<input name="email" defaultValue={draft?.email || ""} /></label>
            {editing !== "new" && <label>نقاط الولاء<input name="loyalty_points" type="number" defaultValue={draft?.loyalty_points || 0} /></label>}
            <button className="btn btn-primary" type="submit">حفظ</button>
          </form>
        </Modal>
      )}
      {history && (
        <Modal title={`سجل مشتريات ${history.customer.name}`} onClose={() => setHistory(null)}>
          <p>عدد الفواتير: {history.sales.length}</p>
          <table>
            <thead><tr><th>الرقم</th><th>التاريخ</th><th>المبلغ</th><th>الدفع</th></tr></thead>
            <tbody>{history.sales.map((sale) => <tr key={sale.id}><td>{sale.id}</td><td>{sale.sale_date}</td><td>{money(sale.total_amount)}</td><td>{sale.payment_method}</td></tr>)}</tbody>
          </table>
        </Modal>
      )}
    </div>
  );
}
