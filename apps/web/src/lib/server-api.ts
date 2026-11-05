import { serverEnv } from "./env";

export async function apiFetch(path: string, init?: RequestInit) {
  const { API_URL } = serverEnv();
  const { cookies } = await import("next/headers");
  const token = (await cookies()).get("bv_token")?.value;
  const headers = new Headers(init?.headers);
  headers.set("accept", "application/json");
  if (init?.body && !headers.has("content-type")) headers.set("content-type", "application/json");
  if (token) headers.set("authorization", `Bearer ${token}`);
  return fetch(`${API_URL}${path}`, { ...init, headers, cache: "no-store" });
}
