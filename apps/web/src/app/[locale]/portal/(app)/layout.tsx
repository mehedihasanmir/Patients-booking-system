import type { ReactNode } from "react";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { Shell } from "@/components/portal/shell";
import { serverEnv } from "@/lib/env";

export default async function PortalLayout({
  children,
  params,
}: {
  children: ReactNode;
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  const token = (await cookies()).get("bv_token")?.value;
  if (!token) redirect(`/${locale}/portal/login`);
  const me = await fetch(`${serverEnv().API_URL}/api/auth/me`, {
    headers: { authorization: `Bearer ${token}` },
    cache: "no-store",
  });
  if (!me.ok) redirect(`/${locale}/portal/login`);
  const user = (await me.json()) as { email: string };
  return <Shell email={user.email}>{children}</Shell>;
}
