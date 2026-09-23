import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import { Modal } from "../components/Modal";
import { money } from "../constants";

type Summary = {
  total_products: number;
  inventory_value: number;
  low_stock: number;
  sales_today: number;
  returns_today: number;
  expenses_today: number;
  net_sales_today: number;
  current_session_status: string;
  current_session_id: number | null;
  current_session_expected_cash: number;
};

type Sale = { id: number; sale_date: string; customer_name: string | null; total_amount: number; payment_method: string };
type SaleItem = { sku: string; product_name: string; quantity: number; unit_price: number; subtotal: number; unit_name?: string };

export function DashboardPage() {
  const { user } = useAuth();
  const [summary, setSummary] = useState<Summary | null>(null);
  const [sales, setSales] = useState<Sale[]>([]);
  const [receipt, setReceipt] = useState<{ sale: Sale; items: SaleItem[] } | null>(null);

  async function load() {
    const [nextSummary, nextSales] = await Promise.all([
      api<Summary>("/api/dashboard/summary"),
      api<Sale[]>("/api/sales/recent?limit=20"),
    ]);
    setSummary(nextSummary);
    setSales(nextSales);
  }

  useEffect(() => { load(); }, []);

  async function openReceipt(saleId: number) {
    const detail = await api<{ sale: Sale; items: SaleItem[] }>(`/api/sales/${saleId}`);
    setReceipt(detail);
  }

  return (
    <div>
      <div className="page-head">
        <h1>لوحة التحكم</h1>
        <div className="actions">
          <Link className="btn btn-primary" to="/pos">🛒 بدء عملية بيع</Link>
          {user?.role === "manager" && <Link className="btn btn-green" to="/inventory">📦 إضافة منتج جديد</Link>}
          <button className="btn btn-muted" onClick={load}>تحديث البيانات</button>
        </div>
      </div>
      {summary && (
        <div className="cards">
          <div className="card"><span>حالة الجلسة الحالية</span><strong className={summary.current_session_id ? "status-open" : "status-closed"}>{summary.current_session_id ? `جلسة #${summary.current_session_id} - ${summary.current_session_status}` : summary.current_session_status}</strong></div>
          <div className="card"><span>الرصيد النقدي المتوقع</span><strong>{money(summary.current_session_expected_cash)}</strong></div>
          <div className="card"><span>مبيعات اليوم</span><strong>{money(summary.sales_today)}</strong></div>
          <div className="card"><span>صافي مبيعات اليوم</span><strong>{money(summary.net_sales_today)}</strong></div>
          <div className="card"><span>مرتجعات اليوم</span><strong>{money(summary.returns_today)}</strong></div>
          <div className="card"><span>مصروفات اليوم</span><strong>{money(summary.expenses_today)}</strong></div>
          <div className="card"><span>إجمالي المنتجات</span><strong>{summary.total_products}</strong></div>
          <div className="card"><span>تنبيهات نواقص المخزون</span><strong>{summary.low_stock}</strong></div>
          <div className="card"><span>إجمالي قيمة المخزون</span><strong>{money(summary.inventory_value)}</strong></div>
        </div>
      )}
      <section className="panel">
        <h2>أحدث العمليات والفواتير</h2>
        <p className="hint">انقر على أي صف لعرض إيصال الفاتورة.</p>
        <div className="table-wrap">
          <table>
            <thead><tr><th>رقم الفاتورة</th><th>التاريخ والوقت</th><th>اسم العميل</th><th>المبلغ الإجمالي</th><th>طريقة الدفع</th></tr></thead>
            <tbody>
              {sales.map((sale) => (
                <tr key={sale.id} className="clickable" onClick={() => openReceipt(sale.id)}>
                  <td>{sale.id}</td>
                  <td>{sale.sale_date}</td>
                  <td>{sale.customer_name || "عميل عام (نقدي)"}</td>
                  <td>{money(sale.total_amount)}</td>
                  <td>{sale.payment_method}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      {receipt && (
        <Modal title={`إيصال مبيعات - فاتورة #${receipt.sale.id}`} onClose={() => setReceipt(null)}>
          <p>التاريخ: {receipt.sale.sale_date}</p>
          <p>العميل: {receipt.sale.customer_name || "عميل عام (نقدي)"} | طريقة الدفع: {receipt.sale.payment_method}</p>
          <table>
            <thead><tr><th>المنتج</th><th>الكمية</th><th>سعر الوحدة</th><th>المجموع</th></tr></thead>
            <tbody>
              {receipt.items.map((item, index) => (
                <tr key={index}><td>[{item.sku}] {item.product_name}</td><td>{item.quantity}</td><td>{money(item.unit_price)}</td><td>{money(item.subtotal)}</td></tr>
              ))}
            </tbody>
          </table>
          <p className="totals"><span className="final">الإجمالي المدفوع: {money(receipt.sale.total_amount)}</span></p>
        </Modal>
      )}
    </div>
  );
}
