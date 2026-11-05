"use client";

import { useEffect, useState } from "react";
import { useLocale } from "next-intl";

export function usePortal<T>(path: string) {
  const locale = useLocale();
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  async function reload() {
    setLoading(true);
    const response = await fetch(`/api/proxy/${path}`);
    if (response.status === 401) {
      window.location.href = `/${locale}/portal/login`;
      return;
    }
    if (!response.ok) {
      setError(await response.text());
      setLoading(false);
      return;
    }
    setData((await response.json()) as T);
    setError("");
    setLoading(false);
  }

  useEffect(() => {
    void reload();
    // path is the cache key for this screen
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path]);

  return { data, error, loading, reload };
}
