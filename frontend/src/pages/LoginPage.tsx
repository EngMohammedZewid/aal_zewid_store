import { FormEvent, useState } from "react";
import { Navigate } from "react-router-dom";
import { ApiError } from "../api";
import { useAuth } from "../auth";

export function LoginPage() {
  const { user, login } = useAuth();
  const [username, setUsername] = useState("manager");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  if (user) return <Navigate to="/" replace />;

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError("");
    try {
      await login(username, password);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "تعذر تسجيل الدخول");
    }
  }

  return (
    <div className="login-page">
      <form className="login-card" onSubmit={onSubmit}>
        <h1>إدارة المتجر برو</h1>
        <p className="hint">سجل الدخول بحساب المدير أو الكاشير. الحسابات الأولى: manager / cashier، وكلمة المرور الافتراضية manager123 و cashier123 ما لم تُغيَّر من البيئة.</p>
        {error && <div className="error">{error}</div>}
        <div className="form-grid">
          <label>اسم المستخدم<input value={username} onChange={(event) => setUsername(event.target.value)} /></label>
          <label>كلمة المرور<input type="password" value={password} onChange={(event) => setPassword(event.target.value)} /></label>
          <button className="btn btn-primary" type="submit">دخول</button>
        </div>
      </form>
    </div>
  );
}
