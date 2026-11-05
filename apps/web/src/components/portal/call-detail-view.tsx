"use client";

import { useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import type { CallDetail } from "@bytevoice/shared";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { formatClock, formatWhen } from "@/lib/utils";
import { usePortal } from "./use-portal";

export function CallDetailView({ id }: { id: string }) {
  const t = useTranslations("detail");
  const locale = useLocale();
  const { data, error, loading, reload } = usePortal<CallDetail>(`calls/${id}`);
  const [lang, setLang] = useState<"bn" | "en">("bn");
  const [saved, setSaved] = useState(false);

  if (loading) return <p>…</p>;
  if (error || !data) return <p className="text-sm text-red-800">{error}</p>;
  const extraction = data.extraction;

  async function save(form: FormData) {
    const response = await fetch(`/api/proxy/calls/${id}/extraction`, {
      method: "PATCH",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        full_name_bn: form.get("full_name_bn"),
        full_name_en: form.get("full_name_en"),
        phone: form.get("phone"),
        reason_for_visit: form.get("reason"),
        preferred_date: form.get("date") || null,
        preferred_time_window: form.get("window"),
        needs_review: false,
      }),
    });
    if (response.ok) {
      setSaved(true);
      await reload();
    }
  }

  return (
    <div className="grid gap-4 lg:grid-cols-[0.9fr_1.1fr]">
      <div className="space-y-4">
        <Card className="p-5">
          <div className="flex items-center justify-between gap-3">
            <h1 className="font-display text-2xl">{formatWhen(data.started_at, locale)}</h1>
            <Badge value={data.status} />
          </div>
          {extraction?.needs_review ? <p className="bn mt-3 text-sm text-[#8a4b08]">{t("review")}</p> : null}
          {data.error_reason ? <p className="mt-2 text-sm text-[#8d2b2b]">{data.error_reason}</p> : null}
          <p className="bn mt-4 text-sm leading-6">{data.summary_bn}</p>
          <p className="mt-2 text-sm leading-6 text-ink/70">{data.summary_en}</p>
          {data.recording_url ? <audio className="mt-4 w-full" controls src={data.recording_url} /> : null}
        </Card>
        <Card className="p-5">
          <h2 className="bn font-semibold">{t("fields")}</h2>
          <form
            className="mt-3 grid gap-3"
            onSubmit={(event) => {
              event.preventDefault();
              void save(new FormData(event.currentTarget));
            }}
          >
            <Field label={t("nameBn")} name="full_name_bn" defaultValue={extraction?.full_name_bn} confidence={extraction?.field_confidence.name} />
            <Field label={t("nameEn")} name="full_name_en" defaultValue={extraction?.full_name_en} />
            <Field label={t("phone")} name="phone" defaultValue={extraction?.phone} confidence={extraction?.field_confidence.phone} />
            <Field label={t("reason")} name="reason" defaultValue={extraction?.reason_for_visit ?? ""} confidence={extraction?.field_confidence.reason} />
            <label className="text-sm">
              {t("date")}
              <Input type="date" name="date" defaultValue={extraction?.preferred_date ?? ""} />
            </label>
            <Field label={t("window")} name="window" defaultValue={extraction?.preferred_time_window ?? ""} confidence={extraction?.field_confidence.datetime} />
            <p className="bn text-xs text-ink/60">{extraction?.doctor_name_bn || "—"}</p>
            <Button type="submit" className="w-fit">
              {saved ? t("saved") : t("save")}
            </Button>
          </form>
        </Card>
        <Card className="p-5">
          <h2 className="bn font-semibold">{t("appointment")}</h2>
          {data.appointment ? (
            <div className="bn mt-3 text-sm leading-6">
              <Badge value={data.appointment.status} />
              <p className="mt-2">{data.appointment.label_bn}</p>
              <p>{data.appointment.doctor_name_bn}</p>
              <p>{data.appointment.service_name_en}</p>
            </div>
          ) : (
            <p className="bn mt-2 text-sm text-ink/60">{t("none")}</p>
          )}
        </Card>
      </div>
      <Card className="p-5">
        <div className="mb-3 flex gap-2">
          <Button size="sm" variant={lang === "bn" ? "primary" : "ghost"} onClick={() => setLang("bn")}>
            {t("bangla")}
          </Button>
          <Button size="sm" variant={lang === "en" ? "primary" : "ghost"} onClick={() => setLang("en")}>
            {t("english")}
          </Button>
        </div>
        <ol className="max-h-[70vh] space-y-3 overflow-auto">
            {data.turns.map((turn) => (
              <li key={turn.id} className={`rounded-2xl px-3 py-2 text-sm ${turn.speaker === "agent" ? "bg-[#e7f4f2]" : "bg-[#f7f4ef]"}`}>
                <div className="mb-1 text-xs text-ink/50">
                  <span>{turn.speaker === "agent" ? "নুসরাত" : locale === "bn" ? "রোগী" : "Patient"} · {formatClock(turn.started_ms)}</span>
                </div>
                <p className="bn leading-6">{lang === "en" ? turn.text_en || turn.text_bn : turn.text_bn}</p>
              </li>
            ))}
          </ol>
      </Card>
    </div>
  );
}

function Field({
  label,
  name,
  defaultValue,
  confidence,
}: {
  label: string;
  name: string;
  defaultValue?: string | null;
  confidence?: { confidence: number };
}) {
  return (
    <label className="text-sm">
      <span className="flex justify-between">
        {label}
        {confidence ? <span className="text-xs text-ink/50">{Math.round(confidence.confidence * 100)}%</span> : null}
      </span>
      <Input name={name} defaultValue={defaultValue ?? ""} />
    </label>
  );
}
