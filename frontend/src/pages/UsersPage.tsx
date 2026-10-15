import { FormEvent, useEffect, useState } from "react";
import { api, ApiError, User } from "../api";

export function UsersPage() {
  const [users, setUsers] = useState<User[]>([]);
  const [error, setError] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("cashier");

  async function load() {
    setUsers(await api<User[]>("/api/users"));
  }

  useEffect(() => { load(); }, []);

  async function create(event: FormEvent) {
    event.preventDefault();
    setError("");
    try {
      await api("/api/users", { method: "POST", body: JSON.stringify({ username, password, role }) });
      setUsername("");
      setPassword("");
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "تعذر إنشاء المستخدم");
    }
  }

  async function toggle(user: User) {
    try {
      await api(`/api/users/${user.id}`, { method: "PUT", body: JSON.stringify({ is_active: !user.is_active, role: user.role }) });
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "تعذر تحديث المستخدم");
    }
  }

  return (
    <div>
      <div className="page-head"><h1>المستخدمون</h1></div>
      {error && <div className="error">{error}</div>}
      <section className="panel" style={{ marginBottom: 16 }}>
        <h2>حساب جديد</h2>
        <form className="toolbar" onSubmit={create}>
          <input placeholder="اسم المستخدم" value={username} onChange={(event) => setUsername(event.target.value)} required />
          <input placeholder="كلمة المرور" type="password" value={password} onChange={(event) => setPassword(event.target.value)} required />
          <select value={role} onChange={(event) => setRole(event.target.value)}>
            <option value="cashier">كاشير</option>
            <option value="manager">مدير</option>
          </select>
          <button className="btn btn-primary" type="submit">إضافة</button>
        </form>
      </section>
      <section className="panel">
        <table>
          <thead><tr><th>الاسم</th><th>الدور</th><th>الحالة</th><th></th></tr></thead>
          <tbody>
            {users.map((user) => (
              <tr key={user.id}>
                <td>{user.username}</td>
                <td>{user.role === "manager" ? "مدير" : "كاشير"}</td>
                <td>{user.is_active ? "نشط" : "موقوف"}</td>
                <td><button className="btn btn-muted" onClick={() => toggle(user)}>{user.is_active ? "إيقاف" : "تفعيل"}</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
