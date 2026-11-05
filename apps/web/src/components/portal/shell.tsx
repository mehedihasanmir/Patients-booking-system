"use client";

import type { ReactNode } from "react";
import { useLocale, useTranslations } from "next-intl";
import { Link, usePathname } from "@/i18n/navigation";
import { LanguageToggle } from "@/components/language-toggle";

const links = [
  ["", "dashboard"],
  ["/calls", "calls"],
  ["/appointments", "appointments"],
  ["/patients", "patients"],
  ["/callbacks", "callbacks"],
  ["/data-model", "model"],
] as const;

export function Shell({ email, children }: { email: string; children: ReactNode }) {
  const t = useTranslations("portalNav");
  const pathname = usePathname();
  const locale = useLocale();
  return (
    <div className="min-h-screen bg-foam">
      <header className="border-b border-line bg-white">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-3 px-4 py-4">
          <Link href="/portal" className="font-display text-xl text-deep">
            {t("brand")}
          </Link>
          <nav className="flex flex-1 flex-wrap gap-1">
            {links.map(([href, key]) => {
              const path = `/portal${href}`;
              const active = pathname === path;
              return (
                <Link
                  key={key}
                  href={path}
                  className={`bn rounded-full px-3 py-2 text-sm ${active ? "bg-deep text-white" : "text-ink/80"}`}
                >
                  {t(key)}
                </Link>
              );
            })}
          </nav>
          <span className="text-xs text-ink/60">{email}</span>
          <LanguageToggle />
          <button
            className="bn text-sm font-semibold text-tide"
            onClick={async () => {
              await fetch("/api/auth/logout", { method: "POST" });
              window.location.href = `/${locale}/portal/login`;
            }}
          >
            {t("logout")}
          </button>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-6">{children}</main>
    </div>
  );
}
