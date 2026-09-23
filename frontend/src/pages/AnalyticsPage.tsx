import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api";
import { money } from "../constants";

type Overview = {
  gross_sales: number;
  returns_total: number;
  net_sales: number;
  gross_cogs: number;
  returned_cogs: number;
  net_cogs: number;
  gross_profit_after_returns: number;
  expenses_total: number;
  operating_result: number;
  profit_margin: number;
};

type Charts = {
  daily_sales: { labels: string[]; values: number[] };
  top_products: { labels: string[]; values: number[] };
};

export function AnalyticsPage() {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [charts, setCharts] = useState<Charts | null>(null);

  useEffect(() => {
    Promise.all([api<Overview>("/api/analytics/overview"), api<Charts>("/api/analytics/charts")]).then(([nextOverview, nextCharts]) => {
      setOverview(nextOverview);
      setCharts(nextCharts);
    });
  }, []);

  async function download() {
    const blob = await api<Blob>("/api/analytics/export.csv");
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "sales_report.csv";
    link.click();
    URL.revokeObjectURL(url);
  }

  const daily = charts?.daily_sales.labels.map((label, index) => ({ label, value: charts.daily_sales.values[index] })) || [];
  const top = charts?.top_products.labels.map((label, index) => ({ label, value: charts.top_products.values[index] })) || [];
  const cards: Array<[string, string]> = overview ? [
    ["إجمالي المبيعات", money(overview.gross_sales)],
    ["إجمالي المرتجعات", money(overview.returns_total)],
    ["صافي المبيعات", money(overview.net_sales)],
    ["إجمالي تكلفة البضاعة", money(overview.gross_cogs)],
    ["تكلفة البضاعة المرتجعة", money(overview.returned_cogs)],
    ["صافي تكلفة البضاعة", money(overview.net_cogs)],
    ["الربح بعد المرتجعات", money(overview.gross_profit_after_returns)],
    ["النتيجة التشغيلية", money(overview.operating_result)],
    ["هامش الربح", `${money(overview.profit_margin)}%`],
    ["إجمالي المصروفات", money(overview.expenses_total)],
  ] : [];

  return (
    <div>
      <div className="page-head">
        <h1>التحليلات والتقارير</h1>
        <button className="btn btn-green" onClick={download}>تصدير التقرير (CSV)</button>
      </div>
      <div className="note">تكلفة البضاعة المرتجعة تستخدم سعر تكلفة المنتج الحالي، وليس تكلفة تاريخية مخزنة وقت البيع.</div>
      <div className="cards">{cards.map(([label, value]) => <div className="card" key={label}><span>{label}</span><strong>{value}</strong></div>)}</div>
      <div className="charts">
        <section className="panel">
          <h2>صافي المبيعات لآخر 7 أيام</h2>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={daily}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="label" /><YAxis /><Tooltip /><Bar dataKey="value" fill="#2563eb" /></BarChart>
          </ResponsiveContainer>
        </section>
        <section className="panel">
          <h2>أكثر 5 منتجات مبيعاً بعد الاسترجاع</h2>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={top} layout="vertical"><CartesianGrid strokeDasharray="3 3" /><XAxis type="number" /><YAxis type="category" dataKey="label" width={120} /><Tooltip /><Bar dataKey="value" fill="#16a34a" /></BarChart>
          </ResponsiveContainer>
        </section>
      </div>
    </div>
  );
}
