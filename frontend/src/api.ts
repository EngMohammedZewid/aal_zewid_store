export type Role = "manager" | "cashier";

export type User = {
  id: number;
  username: string;
  role: Role;
  is_active: boolean;
  created_at?: string;
};

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  if (options.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(path, { ...options, headers, credentials: "include" });
  if (!response.ok) {
    let message = "حدث خطأ";
    try {
      const body = await response.json();
      if (typeof body.detail === "string") message = body.detail;
    } catch {
      message = "حدث خطأ";
    }
    throw new ApiError(response.status, message);
  }
  if (response.status === 204) return undefined as T;
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("text/csv")) {
    return (await response.blob()) as T;
  }
  return response.json() as Promise<T>;
}
