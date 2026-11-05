import { cookies } from "next/headers";
import { serverEnv } from "@/lib/env";

async function forward(request: Request, path: string[]) {
  const token = (await cookies()).get("bv_token")?.value;
  if (!token) return Response.json({ code: "unauthorized" }, { status: 401 });
  const url = new URL(request.url);
  const target = `${serverEnv().API_URL}/api/${path.join("/")}${url.search}`;
  const headers = new Headers();
  headers.set("authorization", `Bearer ${token}`);
  const contentType = request.headers.get("content-type");
  if (contentType) headers.set("content-type", contentType);
  const upstream = await fetch(target, {
    method: request.method,
    headers,
    body: request.method === "GET" || request.method === "HEAD" ? undefined : await request.text(),
    cache: "no-store",
  });
  return new Response(await upstream.text(), {
    status: upstream.status,
    headers: { "content-type": upstream.headers.get("content-type") || "application/json" },
  });
}

type Ctx = { params: Promise<{ path: string[] }> };

export async function GET(request: Request, context: Ctx) {
  return forward(request, (await context.params).path);
}
export async function POST(request: Request, context: Ctx) {
  return forward(request, (await context.params).path);
}
export async function PATCH(request: Request, context: Ctx) {
  return forward(request, (await context.params).path);
}
