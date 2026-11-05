"use client";

import { useEffect, useMemo, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import type { CallListItem, Page } from "@bytevoice/shared";
import { Link } from "@/i18n/navigation";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { formatDuration, formatWhen } from "@/lib/utils";

const statuses = ["", "in_progress", "booked", "rescheduled", "cancelled", "enquiry", "follow_up_needed", "incomplete", "failed"];

export function CallsView() {
  const t = useTranslations("calls");
  const locale = useLocale();
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<Page<CallListItem> | null>(null);

  const query = useMemo(() => {
    const params = new URLSearchParams({ page: String(page), page_size: "20" });
    if (q.trim()) params.set("q", q.trim());
    if (status) params.set("status", status);
    if (from) params.set("date_from", from);
    if (to) params.set("date_to", to);
    return `calls?${params.toString()}`;
  }, [q, status, from, to, page]);

  async function load() {
    const response = await fetch(`/api/proxy/${query}`);
    if (response.ok) setData(await response.json());
  }

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query]);

  useEffect(() => {
    const source = new EventSource("/api/calls/stream");
    source.onmessage = () => void load();
    return () => source.close();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query]);

  return (
    <div className="space-y-4">
      <div className="grid gap-3 md:grid-cols-4">
        <Input placeholder={t("search")} value={q} onChange={(event) => { setPage(1); setQ(event.target.value); }} />
        <select className="min-h-12 rounded-2xl border border-line bg-white px-3 text-sm" value={status} onChange={(event) => { setPage(1); setStatus(event.target.value); }}>
          {statuses.map((item) => (
            <option key={item || "all"} value={item}>
              {item ? item.replaceAll("_", " ") : t("all")}
            </option>
          ))}
        </select>
        <Input type="date" aria-label={t("from")} value={from} onChange={(event) => setFrom(event.target.value)} />
        <Input type="date" aria-label={t("to")} value={to} onChange={(event) => setTo(event.target.value)} />
      </div>
      <div className="overflow-x-auto rounded-3xl border border-line bg-white">
        <table className="w-full min-w-[720px] text-left text-sm">
          <tbody>
            {(data?.items ?? []).map((call) => (
              <tr key={call.id} className="border-t border-line">
                <td className="px-4 py-3">{formatWhen(call.started_at, locale)}</td>
                <td className="bn px-4 py-3">{call.caller_name || call.caller_name_en || "—"}</td>
                <td className="px-4 py-3">{call.phone || "—"}</td>
                <td className="px-4 py-3">{formatDuration(call.duration_s)}</td>
                <td className="px-4 py-3">
                  <Badge value={call.status} />
                  {call.needs_review ? <span className="bn ml-2 text-xs text-gold">{t("review")}</span> : null}
                </td>
                <td className="px-4 py-3">
                  <Link href={`/portal/calls/${call.id}`} className="font-semibold text-tide">
                    Open
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="flex items-center justify-between text-sm">
        <button disabled={page <= 1} className="min-h-10 px-2" onClick={() => setPage((value) => value - 1)}>
          {t("prev")}
        </button>
        <span>
          {page} / {Math.max(1, Math.ceil((data?.total ?? 0) / 20))}
        </span>
        <button
          disabled={!data || page * 20 >= data.total}
          className="min-h-10 px-2"
          onClick={() => setPage((value) => value + 1)}
        >
          {t("next")}
        </button>
      </div>
    </div>
  );
}
