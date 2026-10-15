import type { ReactNode } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./auth";
import { Layout } from "./components/Layout";
import { AnalyticsPage } from "./pages/AnalyticsPage";
import { CustomersPage } from "./pages/CustomersPage";
import { DashboardPage } from "./pages/DashboardPage";
import { InventoryPage } from "./pages/InventoryPage";
import { LoginPage } from "./pages/LoginPage";
import { PosPage } from "./pages/PosPage";
import { SuppliersPage } from "./pages/SuppliersPage";
import { UsersPage } from "./pages/UsersPage";

function Guard({ manager = false, children }: { manager?: boolean; children: ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return <p className="content">جارٍ التحميل...</p>;
  if (!user) return <Navigate to="/login" replace />;
  if (manager && user.role !== "manager") return <Navigate to="/" replace />;
  return <Layout>{children}</Layout>;
}

export function App() {
  const { user, loading } = useAuth();
  return (
    <Routes>
      <Route path="/login" element={loading ? <p className="content">جارٍ التحميل...</p> : user ? <Navigate to="/" replace /> : <LoginPage />} />
      <Route path="/" element={<Guard><DashboardPage /></Guard>} />
      <Route path="/pos" element={<Guard><PosPage /></Guard>} />
      <Route path="/inventory" element={<Guard manager><InventoryPage /></Guard>} />
      <Route path="/suppliers" element={<Guard manager><SuppliersPage /></Guard>} />
      <Route path="/customers" element={<Guard manager><CustomersPage /></Guard>} />
      <Route path="/analytics" element={<Guard manager><AnalyticsPage /></Guard>} />
      <Route path="/users" element={<Guard manager><UsersPage /></Guard>} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
