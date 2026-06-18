"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { FormulaComparePanel } from "@/components/formula/FormulaComparePanel";
import { StructuredFormulaPanel } from "@/components/chat/StructuredFormulaPanel";
import { useLocale } from "@/components/i18n/LocaleProvider";
import { AppHeader } from "@/components/ui/AppHeader";
import { Spinner } from "@/components/ui/Spinner";
import {
  fetchFormulationDetail,
  fetchFormulationSummaries,
  type FormulationSummary,
} from "@/lib/formulations";
import { sourcePdfUrl } from "@/lib/sources";
import type { StructuredFormulationView } from "@/types/chat";

export default function FormulationsPage() {
  const { t } = useLocale();
  const [filterType, setFilterType] = useState("");
  const [filterIngredient, setFilterIngredient] = useState("");
  const [summaries, setSummaries] = useState<FormulationSummary[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<StructuredFormulationView | null>(null);
  const [comparePool, setComparePool] = useState<StructuredFormulationView[]>([]);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadList = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const rows = await fetchFormulationSummaries({
        product_type: filterType.trim() || undefined,
        ingredient: filterIngredient.trim() || undefined,
        limit: 30,
      });
      setSummaries(rows);
      setSelectedId((prev) => prev ?? rows[0]?.formulation_id ?? null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }, [filterIngredient, filterType]);

  useEffect(() => {
    void loadList();
  }, [loadList]);

  useEffect(() => {
    if (!selectedId) {
      setDetail(null);
      return;
    }
    setDetailLoading(true);
    fetchFormulationDetail(selectedId)
      .then((rec) => {
        setDetail(rec);
        setComparePool((prev) => {
          const next = prev.filter((f) => f.formulation_id !== rec.formulation_id);
          return [...next, rec].slice(-4);
        });
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load detail"))
      .finally(() => setDetailLoading(false));
  }, [selectedId]);

  const selectedSummary = summaries.find((s) => s.formulation_id === selectedId);

  return (
    <div className="app-mesh-bg min-h-screen">
      <div className="relative z-10 mx-auto max-w-5xl px-4 py-6 lg:px-8 lg:py-10">
        <div className="panel-solid animate-scale-in overflow-hidden rounded-3xl">
          <AppHeader active="formulations" />

          <div className="space-y-6 px-6 py-8 lg:px-8">
            <div>
              <p className="eyebrow">{t("nav.formulations")}</p>
              <h2 className="mt-1.5 text-2xl font-extrabold tracking-tight text-text-primary">{t("library.title")}</h2>
              <p className="mt-1.5 text-sm text-text-secondary">{t("library.subtitle")}</p>
            </div>

            <div className="flex flex-wrap gap-2">
              <input
                type="text"
                value={filterType}
                onChange={(e) => setFilterType(e.target.value)}
                placeholder={t("library.filterProduct")}
                className="field min-w-[140px] flex-1"
              />
              <input
                type="text"
                value={filterIngredient}
                onChange={(e) => setFilterIngredient(e.target.value)}
                placeholder={t("library.filterIngredient")}
                className="field min-w-[140px] flex-1"
              />
              <button
                type="button"
                onClick={() => void loadList()}
                className="btn-primary rounded-xl px-5 py-2 text-sm font-semibold"
              >
                {t("library.search")}
              </button>
            </div>

            {error ? (
              <p className="rounded-2xl border border-error/30 bg-error/10 px-4 py-3 text-sm text-error">
                {error}
              </p>
            ) : null}

            <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
              <div className="surface-inset max-h-[28rem] overflow-y-auto">
                {loading ? (
                  <div className="flex justify-center py-12">
                    <Spinner className="h-8 w-8" />
                  </div>
                ) : summaries.length === 0 ? (
                  <p className="p-6 text-sm text-text-secondary">{t("library.empty")}</p>
                ) : (
                  <ul className="divide-y divide-border">
                    {summaries.map((item) => {
                      const isSelected = selectedId === item.formulation_id;
                      return (
                        <li key={item.formulation_id}>
                          <button
                            type="button"
                            onClick={() => setSelectedId(item.formulation_id)}
                            className={`relative w-full px-4 py-3 text-start transition-colors hover:bg-secondary/5 ${
                              isSelected ? "bg-secondary/10" : ""
                            }`}
                          >
                            {isSelected ? (
                              <span
                                aria-hidden
                                className="absolute inset-y-2 start-0 w-1 rounded-e-full"
                                style={{ background: "var(--brand-gradient-vivid)" }}
                              />
                            ) : null}
                            <p className="text-sm font-semibold text-text-primary">{item.name}</p>
                            <p className="mt-0.5 text-xs text-text-secondary">
                              {item.product_types.join(", ") || "—"} · {item.ingredient_count}{" "}
                              {t("library.ingredients")}
                            </p>
                          </button>
                        </li>
                      );
                    })}
                  </ul>
                )}
              </div>

              <div className="space-y-4">
                {detailLoading ? (
                  <div className="flex justify-center py-12">
                    <Spinner className="h-8 w-8" />
                  </div>
                ) : null}
                {selectedSummary && detail ? (
                  <>
                    <div className="flex flex-wrap items-center gap-2 text-xs text-text-secondary">
                      <Link
                        href={sourcePdfUrl(detail.doc_id, detail.pdf_page)}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="font-semibold text-secondary hover:underline"
                      >
                        {t("evidence.openPdf")}
                        {detail.pdf_page}
                      </Link>
                      <span>
                        {(detail.confidence * 100).toFixed(0)}% · {detail.doc_id}
                      </span>
                    </div>
                    <StructuredFormulaPanel formulation={detail} />
                  </>
                ) : !detailLoading && !detail ? (
                  <p className="text-sm text-text-secondary">{t("library.selectHint")}</p>
                ) : null}
              </div>
            </div>

            {comparePool.length >= 2 ? <FormulaComparePanel formulations={comparePool} /> : null}
          </div>
        </div>
      </div>
    </div>
  );
}
