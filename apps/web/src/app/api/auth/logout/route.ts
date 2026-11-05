import { cookies } from "next/headers";

export async function POST() {
  const jar = await cookies();
  jar.set("bv_token", "", { httpOnly: true, path: "/", maxAge: 0 });
  return Response.json({ ok: true });
}
