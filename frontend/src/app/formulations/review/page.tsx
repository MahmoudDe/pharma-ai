"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { AppHeader } from "@/components/ui/AppHeader";
import { Spinner } from "@/components/ui/Spinner";
import { useLocale } from "@/components/i18n/LocaleProvider";
import {
  fetchReviewQueue,
  patchFormulation,
  type FormulationSummary,
} from "@/lib/formulations";

export default function FormulationReviewPage() {
  const { t } = useLocale();
  const [items, setItems] = useState<FormulationSummary[]>([]);
  const [names, setNames] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [savedId, setSavedId] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    const queue = await fetchReviewQueue(50);
    setItems(queue);
    setNames(Object.fromEntries(queue.map((q) => [q.formulation_id, q.name])));
  }, []);

  useEffect(() => {
    refresh()
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load"))
      .finally(() => setLoading(false));
  }, [refresh]);

  const saveName = async (id: string) => {
    setError(null);
    try {
      await patchFormulation(id, { name: names[id] });
      setSavedId(id);
      window.setTimeout(() => setSavedId(null), 2000);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Save failed");
    }
  };

  return (
    <div className="app-mesh-bg min-h-screen">
      <div className="relative z-10 mx-auto max-w-3xl px-4 py-6 lg:px-8 lg:py-10">
        <div className="panel-solid animate-scale-in overflow-hidden rounded-3xl">
          <AppHeader active="corpus" />
          <div className="space-y-6 px-6 py-8 lg:px-8">
            <div>
              <p className="eyebrow">{t("nav.corpus")}</p>
              <h2 className="mt-1.5 text-2xl font-extrabold tracking-tight text-text-primary">
                {t("review.title")}
              </h2>
              <p className="mt-1.5 text-sm text-text-secondary">{t("review.subtitle")}</p>
            </div>

            {loading ? (
              <div className="flex justify-center py-12">
                <Spinner className="h-8 w-8" />
              </div>
            ) : null}

            {error ? (
              <p className="rounded-2xl border border-error/30 bg-error/10 px-4 py-3 text-sm text-error">
                {error}
              </p>
            ) : null}

            {!loading && items.length === 0 ? (
              <p className="text-sm text-text-secondary">{t("review.empty")}</p>
            ) : null}

            <ul className="space-y-3">
              {items.map((item) => (
                <li
                  key={item.formulation_id}
                  className="surface-inset flex flex-col gap-2 rounded-2xl border border-border/60 p-4 sm:flex-row sm:items-center"
                >
                  <div className="min-w-0 flex-1">
                    <p className="text-xs text-text-secondary">
                      conf {item.confidence.toFixed(2)}
                      {item.kbs_status ? ` · KBS ${item.kbs_status}` : ""}
                      {item.precision_score != null
                        ? ` · precision ${item.precision_score.toFixed(2)}`
                        : ""}
                    </p>
                    <input
                      type="text"
                      className="field mt-1 w-full text-sm"
                      value={names[item.formulation_id] ?? item.name}
                      onChange={(e) =>
                        setNames((prev) => ({
                          ...prev,
                          [item.formulation_id]: e.target.value,
                        }))
                      }
                    />
                  </div>
                  <div className="flex shrink-0 gap-2">
                    <button
                      type="button"
                      onClick={() => void saveName(item.formulation_id)}
                      className="btn-primary rounded-xl px-3 py-2 text-xs font-semibold"
                    >
                      {savedId === item.formulation_id ? t("review.saved") : t("review.save")}
                    </button>
                    <Link
                      href={`/formulations`}
                      className="rounded-xl border border-border px-3 py-2 text-xs font-semibold text-text-secondary"
                    >
                      Library
                    </Link>
                  </div>
                </li>
              ))}
            </ul>

            <Link
              href="/corpus"
              className="text-sm font-semibold text-secondary hover:underline"
            >
              ← {t("nav.corpus")}
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
