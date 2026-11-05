import { cookies } from "next/headers";
import { serverEnv } from "@/lib/env";

export async function GET() {
  const token = (await cookies()).get("bv_token")?.value;
  if (!token) return new Response("unauthorized", { status: 401 });
  const upstream = await fetch(`${serverEnv().API_URL}/api/calls/stream`, {
    headers: { authorization: `Bearer ${token}` },
    cache: "no-store",
  });
  return new Response(upstream.body, {
    status: upstream.status,
    headers: { "content-type": "text/event-stream", "cache-control": "no-cache" },
  });
}
