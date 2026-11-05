"use client";

import { useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export function LoginForm() {
  const t = useTranslations("login");
  const locale = useLocale();
  const [error, setError] = useState("");

  return (
    <main className="mx-auto flex min-h-screen max-w-md flex-col justify-center px-4">
      <p className="font-display text-3xl text-deep">{t("brand")}</p>
      <h1 className="bn mt-2 text-xl">{t("title")}</h1>
      <form
        className="mt-6 space-y-3 rounded-[28px] bg-white p-6 shadow-card"
        onSubmit={async (event) => {
          event.preventDefault();
          const form = new FormData(event.currentTarget);
          const response = await fetch("/api/auth/login", {
            method: "POST",
            headers: { "content-type": "application/json" },
            body: JSON.stringify({ email: form.get("email"), password: form.get("password") }),
          });
          if (!response.ok) {
            setError(t("failed"));
            return;
          }
          window.location.href = `/${locale}/portal`;
        }}
      >
        <label className="bn block text-sm">
          {t("email")}
          <Input name="email" type="email" required autoComplete="username" />
        </label>
        <label className="bn block text-sm">
          {t("password")}
          <Input name="password" type="password" required autoComplete="current-password" />
        </label>
        {error ? <p className="text-sm text-[#8d2b2b]">{error}</p> : null}
        <Button type="submit">{t("submit")}</Button>
        <p className="bn text-xs text-ink/60">{t("hint")}</p>
      </form>
    </main>
  );
}
