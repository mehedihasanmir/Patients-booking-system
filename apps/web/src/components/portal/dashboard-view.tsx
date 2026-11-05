"use client";

import { useTranslations } from "next-intl";
import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { Stats } from "@bytevoice/shared";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { usePortal } from "./use-portal";

export function DashboardView() {
  const t = useTranslations("dash");
  const { data, error, loading } = usePortal<Stats>("stats");
  if (loading) return <p className="text-sm text-ink/60">…</p>;
  if (error || !data) return <p className="text-sm text-red-800">{error || t("empty")}</p>;
  const minutes = Math.floor(data.avg_duration_s / 60);
  const seconds = Math.round(data.avg_duration_s % 60);
  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-4">
        <Tile label={t("calls")} value={String(data.total_calls)} />
        <Tile label={t("booked")} value={`${data.booked_percent}%`} />
        <Tile label={t("duration")} value={`${minutes}:${seconds.toString().padStart(2, "0")}`} />
        <Tile label={t("callbacks")} value={String(data.open_callbacks)} />
      </div>
      <Card className="p-4">
        <h2 className="bn mb-4 font-semibold">{t("chart")}</h2>
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data.calls_per_day}>
              <XAxis dataKey="date" tick={{ fontSize: 11 }} />
              <YAxis allowDecimals={false} width={28} />
              <Tooltip />
              <Bar dataKey="count" fill="#0f6e68" radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </Card>
      <div className="flex flex-wrap gap-2">
        {Object.entries(data.status_breakdown).map(([status, count]) => (
          <span key={status} className="inline-flex items-center gap-2">
            <Badge value={status} />
            <span className="text-sm">{count}</span>
          </span>
        ))}
      </div>
    </div>
  );
}

function Tile({ label, value }: { label: string; value: string }) {
  return (
    <Card className="p-4">
      <p className="bn text-sm text-ink/60">{label}</p>
      <p className="mt-2 font-display text-3xl text-deep">{value}</p>
    </Card>
  );
}
