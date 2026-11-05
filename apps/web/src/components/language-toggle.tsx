"use client";

import { useLocale } from "next-intl";
import { usePathname, useRouter } from "@/i18n/navigation";

export function LanguageToggle() {
  const locale = useLocale();
  const pathname = usePathname();
  const router = useRouter();
  const next = locale === "bn" ? "en" : "bn";
  return (
    <button
      type="button"
      className="bn min-h-12 rounded-full border border-line bg-white px-4 text-sm font-semibold"
      onClick={() => router.replace(pathname, { locale: next })}
    >
      {locale === "bn" ? "English" : "বাংলা"}
    </button>
  );
}
