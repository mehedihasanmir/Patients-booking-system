"use client";

import { useMemo, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { Link } from "@/i18n/navigation";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { formatWhen } from "@/lib/utils";
import { usePortal } from "./use-portal";

type Appointment = {
  id: string;
  status: string;
  slot_start: string;
  label_bn: string;
  label_en: string;
  doctor_name_bn: string;
  doctor_name_en: string;
  patient_name_bn: string;
  patient_name_en: string;
  phone: string;
  patient_id: string;
  call_id: string | null;
  service_name_en: string | null;
};

function saturdayStart(date: Date) {
  const copy = new Date(date);
  const sinceSaturday = (copy.getDay() + 1) % 7;
  copy.setDate(copy.getDate() - sinceSaturday);
  copy.setHours(0, 0, 0, 0);
  return copy;
}

export function AppointmentsView() {
  const locale = useLocale();
  const [cursor, setCursor] = useState(() => saturdayStart(new Date()));
  const [mode, setMode] = useState<"week" | "day">("week");
  const days = useMemo(() => {
    const count = mode === "week" ? 7 : 1;
    return Array.from({ length: count }, (_, index) => {
      const day = new Date(cursor);
      day.setDate(cursor.getDate() + index);
      return day;
    });
  }, [cursor, mode]);
  const start = dhakaDate(days[0]);
  const end = dhakaDate(days[days.length - 1]);
  const { data } = usePortal<{ items: Appointment[] }>(`appointments?start=${start}&end=${end}`);
  const labels = locale === "bn" ? ["শনি", "রবি", "সোম", "মঙ্গল", "বুধ", "বৃহ", "শুক্র"] : ["Sat", "Sun", "Mon", "Tue", "Wed", "Thu", "Fri"];

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <Button size="sm" variant="ghost" onClick={() => setCursor(new Date(cursor.getFullYear(), cursor.getMonth(), cursor.getDate() - (mode === "week" ? 7 : 1)))}>
          ←
        </Button>
        <Button size="sm" variant="ghost" onClick={() => setCursor(saturdayStart(new Date()))}>
          Today
        </Button>
        <Button size="sm" variant="ghost" onClick={() => setCursor(new Date(cursor.getFullYear(), cursor.getMonth(), cursor.getDate() + (mode === "week" ? 7 : 1)))}>
          →
        </Button>
        <Button size="sm" variant={mode === "week" ? "primary" : "ghost"} onClick={() => setMode("week")}>
          Week
        </Button>
        <Button size="sm" variant={mode === "day" ? "primary" : "ghost"} onClick={() => setMode("day")}>
          Day
        </Button>
      </div>
      <div className={`grid gap-3 ${mode === "week" ? "md:grid-cols-7" : ""}`}>
        {days.map((day, index) => {
          const key = dhakaDate(day);
          const items = (data?.items ?? []).filter((item) => sameDhakaDay(item.slot_start, day));
          const friday = day.getDay() === 5;
          return (
            <Card key={key} className={`p-3 ${friday ? "bg-[#f6f1ea]" : ""}`}>
              <p className="text-xs font-semibold text-ink/50">{labels[mode === "week" ? index : (day.getDay() + 1) % 7]}</p>
              <p className="font-display text-2xl">{day.getDate()}</p>
              <div className="mt-3 space-y-2">
                {items.map((item) => (
                  <div key={item.id} className="rounded-2xl bg-foam p-2 text-xs">
                    <Badge value={item.status} />
                    <p className="bn mt-1">{locale === "bn" ? item.label_bn : item.label_en}</p>
                    <p className="bn">{locale === "bn" ? item.patient_name_bn : item.patient_name_en}</p>
                    <p>{locale === "bn" ? item.doctor_name_bn : item.doctor_name_en}</p>
                  </div>
                ))}
              </div>
            </Card>
          );
        })}
      </div>
    </div>
  );
}

function dhakaDate(day: Date) {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Dhaka",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(day);
}

function sameDhakaDay(iso: string, day: Date) {
  const local = new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Dhaka", year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date(iso));
  const target = new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Dhaka", year: "numeric", month: "2-digit", day: "2-digit" }).format(day);
  return local === target;
}

export function PatientsView() {
  const t = useTranslations("calls");
  const [q, setQ] = useState("");
  const { data } = usePortal<{ items: { id: string; full_name_bn: string; full_name_en: string; phone_e164: string }[] }>(
    q ? `patients?q=${encodeURIComponent(q)}` : "patients",
  );
  return (
    <div className="space-y-3">
      <input className="min-h-12 w-full max-w-sm rounded-2xl border border-line px-3" value={q} onChange={(event) => setQ(event.target.value)} placeholder={t("search")} aria-label={t("search")} />
      <div className="overflow-hidden rounded-3xl border border-line bg-white">
        {(data?.items ?? []).map((patient) => (
          <Link key={patient.id} href={`/portal/patients/${patient.id}`} className="bn flex items-center justify-between border-t border-line px-4 py-3 text-sm">
            <span>{patient.full_name_bn || patient.full_name_en}</span>
            <span className="text-ink/60">{patient.phone_e164}</span>
          </Link>
        ))}
      </div>
    </div>
  );
}

export function PatientDetailView({ id }: { id: string }) {
  const locale = useLocale();
  const { data } = usePortal<{
    full_name_bn: string;
    full_name_en: string;
    phone_e164: string;
    calls: { id: string; started_at: string; status: string; summary_bn: string | null }[];
    appointments: { id: string; label_bn: string; label_en: string; status: string; call_id: string | null }[];
  }>(`patients/${id}`);
  if (!data) return <p>…</p>;
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card className="p-5">
        <h1 className="bn text-2xl font-semibold">{data.full_name_bn}</h1>
        <p>{data.full_name_en}</p>
        <p className="mt-2 text-sm">{data.phone_e164}</p>
        <h2 className="bn mt-6 font-semibold">Calls</h2>
        <ul className="mt-2 space-y-2 text-sm">
          {data.calls.map((call) => (
            <li key={call.id}>
              <Link href={`/portal/calls/${call.id}`} className="text-tide">
                {formatWhen(call.started_at, locale)}
              </Link>{" "}
              <Badge value={call.status} />
              <p className="bn text-ink/70">{call.summary_bn}</p>
            </li>
          ))}
        </ul>
      </Card>
      <Card className="p-5">
        <h2 className="bn font-semibold">Appointments</h2>
        <ul className="mt-3 space-y-3 text-sm">
          {data.appointments.map((item) => (
            <li key={item.id}>
              <Badge value={item.status} />
              <p className="bn mt-1">{locale === "bn" ? item.label_bn : item.label_en}</p>
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}

export function CallbacksView() {
  const { data, reload } = usePortal<{
    items: { id: string; reason: string; urgency: string; status: string; patient_name_bn: string; phone: string; call_id: string | null }[];
  }>("callbacks?status=open");
  return (
    <div className="space-y-3">
      {(data?.items ?? []).map((item) => (
        <Card key={item.id} className="flex flex-wrap items-center justify-between gap-3 p-4">
          <div>
            <div className="flex gap-2">
              <Badge value={item.urgency} />
              <Badge value={item.status} />
            </div>
            <p className="bn mt-2 text-sm">{item.patient_name_bn} · {item.phone}</p>
            <p className="bn text-sm text-ink/70">{item.reason}</p>
            {item.call_id ? (
              <Link href={`/portal/calls/${item.call_id}`} className="text-sm text-tide">
                Call
              </Link>
            ) : null}
          </div>
          <Button
            size="sm"
            onClick={async () => {
              await fetch(`/api/proxy/callbacks/${item.id}/done`, { method: "POST" });
              await reload();
            }}
          >
            Done
          </Button>
        </Card>
      ))}
    </div>
  );
}
