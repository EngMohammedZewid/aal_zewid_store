import { NavLink } from "react-router-dom";
import { useAuth } from "../auth";

const LINKS = [
  { to: "/", label: "📊 لوحة التحكم", end: true, managerOnly: false },
  { to: "/pos", label: "🛒 نقطة البيع (POS)", end: false, managerOnly: false },
  { to: "/inventory", label: "📦 المخزون والمنتجات", end: false, managerOnly: true },
  { to: "/suppliers", label: "🚚 المورّدون والمشتريات", end: false, managerOnly: true },
  { to: "/customers", label: "👥 العملاء والولاء", end: false, managerOnly: true },
  { to: "/analytics", label: "📈 التحليلات والتقارير", end: false, managerOnly: true },
  { to: "/users", label: "👤 المستخدمون", end: false, managerOnly: true },
];

export function Layout({ children }: { children: React.ReactNode }) {
  const { user, logout } = useAuth();
  const links = LINKS.filter((link) => user?.role === "manager" || !link.managerOnly);

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="logo">
          <strong>🏬 إدارة المتجر</strong>
          <span>نظام الإدارة الاحترافي</span>
        </div>
        <nav className="nav">
          {links.map((link) => (
            <NavLink key={link.to} to={link.to} end={link.end} className={({ isActive }) => (isActive ? "active" : "")}>
              {link.label}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-footer">
          <p>{user?.role === "manager" ? "👤 مدير النظام" : "👤 الكاشير"}: {user?.username}</p>
          <p className="ok">🟢 قاعدة البيانات متصلة</p>
          <button className="danger-link" onClick={() => logout()}>🚪 تسجيل الخروج</button>
        </div>
      </aside>
      <main className="content">{children}</main>
    </div>
  );
}
