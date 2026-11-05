import { cookies } from "next/headers";
import { serverEnv } from "@/lib/env";

export async function POST(request: Request) {
  const upstream = await fetch(`${serverEnv().API_URL}/api/auth/login`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: await request.text(),
  });
  const data = await upstream.json().catch(() => ({}));
  if (!upstream.ok) return Response.json(data, { status: upstream.status });
  const jar = await cookies();
  jar.set("bv_token", data.access_token, {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: 60 * 60 * 12,
  });
  return Response.json({ user: data.user });
}
