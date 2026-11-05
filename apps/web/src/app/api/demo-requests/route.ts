import { serverEnv } from "@/lib/env";

export async function POST(request: Request) {
  const upstream = await fetch(`${serverEnv().API_URL}/api/demo-requests`, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "x-forwarded-for": request.headers.get("x-forwarded-for") ?? "local",
    },
    body: await request.text(),
  });
  return new Response(await upstream.text(), {
    status: upstream.status,
    headers: { "content-type": "application/json" },
  });
}
