"use client";

import { useState, type ReactNode } from "react";
import { MotionConfig, motion } from "framer-motion";
import { useTranslations } from "next-intl";
import { Link } from "@/i18n/navigation";
import { Button } from "@/components/ui/button";
import { CallWidget } from "@/components/call/call-widget";
import { LanguageToggle } from "@/components/language-toggle";

export function Landing() {
  const t = useTranslations();
  const [talk, setTalk] = useState(false);
  const [sent, setSent] = useState(false);

  const problems = t.raw("problem.items") as { title: string; body: string }[];
  const steps = t.raw("how.steps") as { title: string; body: string }[];
  const features = t.raw("features.items") as { title: string; body: string }[];
  const cases = t.raw("usecases.items") as string[];
  const stats = t.raw("stats.items") as { value: string; label: string }[];
  const faqs = t.raw("faq.items") as { q: string; a: string }[];

  return (
    <MotionConfig reducedMotion="user">
      <div className="min-h-screen">
        <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:bg-white focus:px-3 focus:py-2">
          Skip
        </a>
        <header className="mx-auto flex max-w-6xl items-center justify-between px-4 py-5">
          <Link href="/" className="font-display text-xl text-deep">
            {t("nav.brand")}
          </Link>
          <nav className="flex items-center gap-3 text-sm">
            <a href="#contact" className="hidden min-h-12 items-center px-2 sm:flex">
              {t("nav.contact")}
            </a>
            <Link href="/portal/login" className="inline-flex min-h-12 items-center font-semibold text-tide">
              {t("nav.portal")}
            </Link>
            <LanguageToggle />
          </nav>
        </header>
        <main id="main">
          <section className="mx-auto grid max-w-6xl items-center gap-8 px-4 pb-16 pt-4 lg:grid-cols-[0.9fr_1.1fr]">
            <div>
              <p className="bn text-sm font-semibold uppercase tracking-[0.18em] text-gold">{t("hero.kicker")}</p>
              <h1 className="bn mt-4 max-w-xl text-4xl font-semibold leading-tight text-deep sm:text-5xl">{t("hero.title")}</h1>
              <p className="mt-4 max-w-lg font-display text-2xl leading-snug text-ink/80">{t("hero.sub")}</p>
              <p className="bn mt-4 max-w-xl text-base leading-7 text-ink/80">{t("hero.body")}</p>
              <div className="mt-8 flex flex-col gap-3 sm:flex-row">
                <Button
                  onClick={() => {
                    setTalk(true);
                    document.getElementById("talk")?.scrollIntoView({ behavior: "smooth", block: "center" });
                  }}
                >
                  {t("hero.cta")}
                </Button>
                <a href="#how" className="inline-flex min-h-12 items-center justify-center rounded-full border border-line px-5 text-sm font-semibold">
                  {t("hero.secondary")}
                </a>
              </div>
            </div>
            <CallWidget active={talk} />
          </section>

          <Section title={t("problem.title")}>
            <div className="grid gap-4 md:grid-cols-5">
              {problems.map((item, index) => (
                <motion.article key={item.title} initial={{ opacity: 0, y: 12 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} className="rounded-3xl border border-line bg-white p-4">
                  <p className="font-display text-gold">0{index + 1}</p>
                  <h3 className="bn mt-2 font-semibold">{item.title}</h3>
                  <p className="bn mt-2 text-sm leading-6 text-ink/75">{item.body}</p>
                </motion.article>
              ))}
            </div>
          </Section>

          <Section id="how" title={t("how.title")}>
            <ol className="grid gap-4 md:grid-cols-3">
              {steps.map((step, index) => (
                <li key={step.title} className="rounded-3xl bg-deep p-6 text-white">
                  <p className="font-display text-3xl text-[#c4a574]">0{index + 1}</p>
                  <h3 className="bn mt-3 text-xl">{step.title}</h3>
                  <p className="bn mt-2 text-sm leading-6 text-white/80">{step.body}</p>
                </li>
              ))}
            </ol>
          </Section>

          <Section title={t("features.title")}>
            <div className="grid gap-4 md:grid-cols-3">
              {features.map((item) => (
                <article key={item.title} className="rounded-3xl border border-line bg-white/80 p-5">
                  <h3 className="bn font-semibold text-deep">{item.title}</h3>
                  <p className="bn mt-2 text-sm leading-6 text-ink/75">{item.body}</p>
                </article>
              ))}
            </div>
          </Section>

          <Section title={t("usecases.title")}>
            <div className="flex flex-wrap gap-3">
              {cases.map((item) => (
                <span key={item} className="bn rounded-full border border-line bg-white px-4 py-3 text-sm">
                  {item}
                </span>
              ))}
            </div>
            <dl className="mt-8 grid gap-4 sm:grid-cols-4">
              {stats.map((item) => (
                <div key={item.label} className="rounded-3xl bg-[#e7f4f2] p-4">
                  <dt className="font-display text-3xl text-deep">{item.value}</dt>
                  <dd className="bn mt-1 text-sm text-ink/70">{item.label}</dd>
                </div>
              ))}
            </dl>
          </Section>

          <Section title={t("faq.title")}>
            <div className="space-y-3">
              {faqs.map((item) => (
                <details key={item.q} className="rounded-2xl border border-line bg-white px-4 py-3">
                  <summary className="bn cursor-pointer font-semibold">{item.q}</summary>
                  <p className="bn mt-2 text-sm leading-6 text-ink/75">{item.a}</p>
                </details>
              ))}
            </div>
          </Section>

          <Section id="contact" title={t("contact.title")}>
            {sent ? (
              <p className="bn rounded-3xl bg-white p-6">{t("contact.success")}</p>
            ) : (
              <form
                className="grid gap-3 rounded-[28px] bg-white p-6 shadow-card md:grid-cols-2"
                onSubmit={async (event) => {
                  event.preventDefault();
                  const form = new FormData(event.currentTarget);
                  const response = await fetch("/api/demo-requests", {
                    method: "POST",
                    headers: { "content-type": "application/json" },
                    body: JSON.stringify({
                      name: form.get("name"),
                      email: form.get("email"),
                      phone: form.get("phone"),
                      clinic_name: form.get("clinic"),
                      message: form.get("message"),
                    }),
                  });
                  if (response.ok) setSent(true);
                }}
              >
                <label className="bn text-sm">
                  {t("contact.name")}
                  <input required name="name" className="mt-1 min-h-12 w-full rounded-2xl border border-line px-3" />
                </label>
                <label className="bn text-sm">
                  {t("contact.email")}
                  <input required type="email" name="email" className="mt-1 min-h-12 w-full rounded-2xl border border-line px-3" />
                </label>
                <label className="bn text-sm">
                  {t("contact.phone")}
                  <input name="phone" className="mt-1 min-h-12 w-full rounded-2xl border border-line px-3" />
                </label>
                <label className="bn text-sm">
                  {t("contact.clinic")}
                  <input name="clinic" className="mt-1 min-h-12 w-full rounded-2xl border border-line px-3" />
                </label>
                <label className="bn text-sm md:col-span-2">
                  {t("contact.message")}
                  <textarea name="message" rows={4} className="mt-1 w-full rounded-2xl border border-line px-3 py-2" />
                </label>
                <Button type="submit" className="md:col-span-2 md:w-fit">
                  {t("contact.submit")}
                </Button>
              </form>
            )}
          </Section>
        </main>
        <footer className="border-t border-line px-4 py-8">
          <div className="mx-auto flex max-w-6xl flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <p className="bn max-w-xl text-sm text-ink/70">{t("footer.blurb")}</p>
            <Link href="/portal/login" className="text-sm font-semibold text-tide">
              {t("nav.portal")}
            </Link>
          </div>
        </footer>
      </div>
    </MotionConfig>
  );
}

function Section({ id, title, children }: { id?: string; title: string; children: ReactNode }) {
  return (
    <section id={id} className="mx-auto max-w-6xl px-4 py-12">
      <h2 className="bn mb-6 text-3xl font-semibold text-deep">{title}</h2>
      {children}
    </section>
  );
}
