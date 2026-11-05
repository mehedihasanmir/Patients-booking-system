import { serverEnv } from "@/lib/env";

export async function POST(request: Request) {
  const ip = request.headers.get("x-forwarded-for") ?? "local";
  const upstream = await fetch(`${serverEnv().API_URL}/api/livekit/token`, {
    method: "POST",
    headers: { "content-type": "application/json", "x-forwarded-for": ip },
    body: "{}",
  });
  const text = await upstream.text();
  try {
    const body = JSON.parse(text) as { code?: string; detail?: { code?: string } };
    const code = body.code ?? body.detail?.code;
    if (code) {
      return Response.json({ ...body, code }, { status: upstream.status });
    }
  } catch {
    /* upstream was not JSON */
  }
  return new Response(text, {
    status: upstream.status,
    headers: { "content-type": "application/json" },
  });
}
