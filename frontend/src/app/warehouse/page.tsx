"use client";

import Link from "next/link";
import { useCallback, useState } from "react";
import { AppHeader } from "@/components/ui/AppHeader";
import { Spinner } from "@/components/ui/Spinner";
import { useLocale } from "@/components/i18n/LocaleProvider";
import { discoverProducts, resolveWarehouse, setMaterialAlias, uploadWarehouseFile } from "@/lib/warehouse";
import { sourcePdfUrl } from "@/lib/sources";
import type { DiscoverProductResult, ResolveResponse, UploadResponse } from "@/types/warehouse";

type Step = 1 | 2 | 3;

const STEP_KEYS = ["warehouse.stepUpload", "warehouse.stepResolve", "warehouse.stepDiscover"] as const;

function tierStyle(tier: string) {
  if (tier === "makeable") return "text-success border-success/30 bg-success/10";
  if (tier === "partial") return "text-warning border-warning/30 bg-warning/10";
  return "text-text-secondary border-border bg-background";
}

function MaterialAliasEditor({
  materialId,
  initial,
  onSaved,
}: {
  materialId: number;
  initial: string;
  onSaved: (canonical: string) => void;
}) {
  const { t } = useLocale();
  const [value, setValue] = useState(initial);
  const [busy, setBusy] = useState(false);

  return (
    <form
      className="mt-1 flex flex-wrap gap-1"
      onSubmit={(e) => {
        e.preventDefault();
        if (!value.trim()) return;
        setBusy(true);
        setMaterialAlias(materialId, value.trim())
          .then((row) => {
            onSaved(row.canonical_name ?? value.trim());
          })
          .catch(() => {})
          .finally(() => setBusy(false));
      }}
    >
      <input
        type="text"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        className="field min-w-[8rem] flex-1 px-2 py-1 text-xs"
        placeholder={t("warehouse.overrideAlias")}
      />
      <button
        type="submit"
        disabled={busy}
        className="rounded-md border border-secondary/40 bg-secondary/10 px-2 py-1 text-[10px] font-semibold text-secondary transition hover:bg-secondary/20 disabled:opacity-50"
      >
        {t("warehouse.saveAlias")}
      </button>
    </form>
  );
}

export default function WarehousePage() {
  const { t } = useLocale();
  const [step, setStep] = useState<Step>(1);
  const [upload, setUpload] = useState<UploadResponse | null>(null);
  const [resolve, setResolve] = useState<ResolveResponse | null>(null);
  const [products, setProducts] = useState<DiscoverProductResult[]>([]);
  const [minCoverage, setMinCoverage] = useState(70);
  const [bannedInput, setBannedInput] = useState("");
  const [marketsInput, setMarketsInput] = useState("");
  const [maxCost, setMaxCost] = useState("");
  const [tierFilter, setTierFilter] = useState<"all" | "makeable" | "partial">("all");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [dragOver, setDragOver] = useState(false);

  const onFile = useCallback(async (file: File) => {
    setBusy(true);
    setError(null);
    try {
      const res = await uploadWarehouseFile(file);
      setUpload(res);
      setResolve(null);
      setProducts([]);
      setStep(1);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setBusy(false);
    }
  }, []);

  const onAnalyze = async () => {
    if (!upload) return;
    setBusy(true);
    setError(null);
    try {
      const res = await resolveWarehouse(upload.upload_id);
      setResolve(res);
      setStep(2);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Resolve failed");
    } finally {
      setBusy(false);
    }
  };

  const splitList = (raw: string) =>
    raw
      .split(/[,;]+/)
      .map((s) => s.trim())
      .filter(Boolean);

  const onDiscover = async () => {
    if (!upload) return;
    setBusy(true);
    setError(null);
    try {
      const res = await discoverProducts(upload.upload_id, {
        minCoverage,
        bannedIngredients: splitList(bannedInput),
        markets: splitList(marketsInput),
        maxCost: maxCost.trim() ? parseFloat(maxCost) : undefined,
      });
      setProducts(res.products);
      setStep(3);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Discover failed");
    } finally {
      setBusy(false);
    }
  };

  const filteredProducts = products.filter((p) => {
    if (tierFilter === "makeable") return p.tier === "makeable";
    if (tierFilter === "partial") return p.tier === "makeable" || p.tier === "partial";
    return true;
  });

  const exportCsv = () => {
    const header = "name,coverage_pct,tier,doc_id,pdf_page,missing\n";
    const rows = filteredProducts.map(
      (p) =>
        `"${p.name.replace(/"/g, '""')}",${p.coverage_pct},${p.tier},${p.doc_id},${p.pdf_page},"${p.missing_ingredients.join("; ")}"`,
    );
    const blob = new Blob([header + rows.join("\n")], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "warehouse_products.csv";
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="app-mesh-bg min-h-screen">
      <div className="relative z-10 mx-auto max-w-5xl px-4 py-6 lg:px-8 lg:py-10">
        <div className="panel-solid animate-scale-in overflow-hidden rounded-3xl">
          <AppHeader active="warehouse" />

          <div className="border-b border-border px-6 py-6 lg:px-8">
            <p className="eyebrow animate-fade-in-up">{t("nav.warehouse")}</p>
            <h2 className="animate-fade-in-up mt-1.5 text-2xl font-extrabold tracking-tight text-text-primary">
              {t("warehouse.title")}
            </h2>
            <p className="animate-fade-in-up mt-1.5 text-sm text-text-secondary" style={{ animationDelay: "60ms" }}>
              {t("warehouse.subtitle")}
            </p>

            <ol className="mt-6 flex flex-wrap gap-2">
              {STEP_KEYS.map((key, idx) => {
                const n = (idx + 1) as Step;
                const label = t(key);
                const done = step > n;
                const active = step === n;
                return (
                  <li
                    key={n}
                    className={`flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-semibold transition-all duration-500 ${
                      active
                        ? "border-secondary/50 text-text-primary"
                        : done
                          ? "border-success/40 bg-success/10 text-success"
                          : "border-border text-text-secondary"
                    }`}
                    style={active ? { boxShadow: "var(--shadow-glow)" } : undefined}
                  >
                    <span
                      className={`flex h-5 w-5 items-center justify-center rounded-full text-[10px] ${
                        done ? "bg-success text-white" : active ? "text-white" : "bg-background"
                      }`}
                      style={active && !done ? { background: "var(--brand-gradient-vivid)" } : undefined}
                    >
                      {done ? "✓" : n}
                    </span>
                    {label}
                  </li>
                );
              })}
            </ol>
          </div>

          <div className="space-y-6 px-6 py-6 lg:px-8 lg:py-8">
            {error ? (
              <p className="animate-fade-in-down rounded-2xl border border-error/30 bg-error/10 px-4 py-3 text-sm text-error">
                {error}
              </p>
            ) : null}

            <section className="surface-inset animate-fade-in-up p-6">
              <h3 className="text-sm font-bold text-text-primary">{t("warehouse.upload")}</h3>
              <label
                className={`upload-zone mt-4 flex cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed px-6 py-14 text-center ${
                  dragOver ? "border-secondary bg-secondary/10" : "border-border"
                } ${busy ? "animate-shimmer pointer-events-none opacity-70" : ""}`}
                onDragOver={(e) => {
                  e.preventDefault();
                  setDragOver(true);
                }}
                onDragLeave={() => setDragOver(false)}
                onDrop={(e) => {
                  e.preventDefault();
                  setDragOver(false);
                  const f = e.dataTransfer.files[0];
                  if (f) void onFile(f);
                }}
              >
                <input
                  type="file"
                  accept=".csv,.xlsx,.xls,text/csv"
                  className="hidden"
                  disabled={busy}
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (f) void onFile(f);
                  }}
                />
                {busy ? (
                  <Spinner className="h-8 w-8" />
                ) : (
                  <>
                    <span
                      className="flex h-14 w-14 items-center justify-center rounded-2xl text-secondary"
                      style={{ background: "color-mix(in srgb, var(--secondary) 12%, transparent)" }}
                    >
                      <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                        <path d="M7 10l5-5 5 5" />
                        <path d="M12 5v12" />
                      </svg>
                    </span>
                    <p className="mt-4 text-sm font-semibold text-text-primary">
                      {t("warehouse.dropHint")}
                    </p>
                    <p className="mt-1.5 max-w-md text-xs leading-relaxed text-text-secondary">{t("warehouse.arabicHint")}</p>
                  </>
                )}
              </label>
              {upload ? (
                <p className="mt-3 text-xs font-medium text-text-secondary">
                  {upload.filename} · {upload.row_count} materials loaded
                </p>
              ) : null}
              <div className="mt-5 flex flex-wrap items-center gap-3">
                <button
                  type="button"
                  disabled={!upload || busy}
                  onClick={() => void onAnalyze()}
                  className="btn-primary inline-flex items-center gap-2 rounded-xl px-5 py-2.5 text-sm font-semibold disabled:opacity-50"
                >
                  {busy ? <Spinner className="h-4 w-4 text-white" /> : null}
                  {t("warehouse.analyze")}
                </button>
                <button
                  type="button"
                  disabled={!resolve || busy}
                  onClick={() => void onDiscover()}
                  className="btn-ghost rounded-xl px-5 py-2.5 text-sm font-semibold disabled:opacity-50"
                >
                  {t("warehouse.discover")}
                </button>
                <label className="flex items-center gap-2 text-xs text-text-secondary">
                  {t("warehouse.minCoverage")}
                  <input
                    type="number"
                    min={0}
                    max={100}
                    value={minCoverage}
                    onChange={(e) => setMinCoverage(Number(e.target.value))}
                    className="field w-16 px-2 py-1.5 text-center"
                  />
                  %
                </label>
                <label className="flex flex-col gap-1 text-xs text-text-secondary">
                  {t("warehouse.banned")}
                  <input
                    type="text"
                    value={bannedInput}
                    onChange={(e) => setBannedInput(e.target.value)}
                    placeholder={t("warehouse.bannedPlaceholder")}
                    className="field min-w-[10rem] px-2 py-1.5"
                  />
                </label>
                <label className="flex flex-col gap-1 text-xs text-text-secondary">
                  {t("warehouse.markets")}
                  <input
                    type="text"
                    value={marketsInput}
                    onChange={(e) => setMarketsInput(e.target.value)}
                    placeholder={t("warehouse.marketsPlaceholder")}
                    className="field min-w-[8rem] px-2 py-1.5"
                  />
                </label>
                <label className="flex flex-col gap-1 text-xs text-text-secondary">
                  {t("warehouse.maxCost")}
                  <input
                    type="number"
                    min={0}
                    step={0.1}
                    value={maxCost}
                    onChange={(e) => setMaxCost(e.target.value)}
                    placeholder={t("warehouse.maxCostPlaceholder")}
                    className="field w-24 px-2 py-1.5"
                  />
                </label>
              </div>
            </section>

            {resolve ? (
              <section className="surface-inset animate-fade-in-up p-6">
                <h3 className="text-sm font-bold text-text-primary">{t("warehouse.materials")}</h3>
                <p className="mt-1 text-xs text-text-secondary">
                  {t("warehouse.resolvedSummary", {
                    resolved: resolve.resolved,
                    review: resolve.needs_review,
                  })}
                </p>
                <div className="mt-4 max-h-72 overflow-auto rounded-xl border border-border">
                  <table className="w-full text-start text-xs">
                    <thead className="sticky top-0 bg-surface text-text-secondary">
                      <tr>
                        <th className="px-3 py-2 font-semibold">{t("warehouse.tableRaw")}</th>
                        <th className="px-3 py-2 font-semibold">{t("warehouse.tableCanonical")}</th>
                        <th className="px-3 py-2 font-semibold">{t("warehouse.tableConfidence")}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {resolve.materials.map((m) => (
                        <tr key={m.id} className="border-t border-border/40 hover:bg-secondary/5">
                          <td className="px-3 py-2 text-text-primary">{m.raw_name}</td>
                          <td className="px-3 py-2 text-text-secondary">
                            {m.canonical_name ?? "—"}
                            {m.needs_review ? " ⚠" : ""}
                            {m.needs_review ? (
                              <MaterialAliasEditor
                                materialId={m.id}
                                initial={m.canonical_name ?? m.raw_name}
                                onSaved={(canonical) => {
                                  setProducts([]);
                                  setResolve((prev) =>
                                    prev
                                      ? {
                                          ...prev,
                                          materials: prev.materials.map((row) =>
                                            row.id === m.id
                                              ? {
                                                  ...row,
                                                  canonical_name: canonical,
                                                  needs_review: false,
                                                  confidence: 1,
                                                  alias_source: "manual",
                                                }
                                              : row,
                                          ),
                                          needs_review: Math.max(0, prev.needs_review - 1),
                                        }
                                      : prev,
                                  );
                                }}
                              />
                            ) : null}
                          </td>
                          <td className="px-3 py-2">
                            {m.confidence != null ? `${(m.confidence * 100).toFixed(0)}%` : "—"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>
            ) : null}

            {resolve && products.length === 0 && step >= 2 && !busy ? (
              <p className="surface-inset px-4 py-3 text-sm text-text-secondary">
                {t("warehouse.noProducts")}
              </p>
            ) : null}

            {products.length > 0 ? (
              <section className="surface-inset animate-fade-in-up p-6">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <h3 className="text-sm font-bold text-text-primary">
                    {t("warehouse.products")} ({filteredProducts.length})
                  </h3>
                  <div className="flex flex-wrap items-center gap-2">
                    {(["all", "makeable", "partial"] as const).map((key) => (
                      <button
                        key={key}
                        type="button"
                        onClick={() => setTierFilter(key)}
                        className={`rounded-lg border px-2.5 py-1 text-[10px] font-semibold ${
                          tierFilter === key
                            ? "border-secondary/50 bg-secondary/10 text-text-primary"
                            : "border-border text-text-secondary"
                        }`}
                      >
                        {t(
                          key === "all"
                            ? "warehouse.filterAll"
                            : key === "makeable"
                              ? "warehouse.filterMakeable"
                              : "warehouse.filterPartial",
                        )}
                      </button>
                    ))}
                    <button
                      type="button"
                      onClick={exportCsv}
                      className="text-xs font-semibold text-secondary underline-offset-2 hover:underline"
                    >
                      {t("warehouse.export")}
                    </button>
                  </div>
                </div>
                <ul className="stagger-children mt-4 space-y-3">
                  {filteredProducts.map((p) => {
                    const matched = p.matched_ingredients.filter((i) => i.matched).length;
                    const total = p.matched_ingredients.length;
                    return (
                    <li
                      key={p.formulation_id}
                      className="surface-card hover-lift p-4"
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <span className="font-semibold text-text-primary">{p.name}</span>
                        <span
                          className={`rounded-full border px-2.5 py-0.5 text-[10px] font-bold uppercase ${tierStyle(p.tier)}`}
                        >
                          {p.coverage_pct}% · {p.tier}
                        </span>
                      </div>
                      <p className="mt-1 text-xs text-text-secondary">
                        <a
                          href={sourcePdfUrl(p.doc_id, p.pdf_page)}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="font-semibold text-secondary hover:underline"
                        >
                          {p.doc_id} · {t("evidence.openPdf")}
                          {p.pdf_page}
                        </a>
                        {p.printed_page != null ? ` · Book p.${p.printed_page}` : ""}
                      </p>
                      <p className="mt-1 text-xs text-text-secondary">
                        {t("warehouse.matchedIngredients", { matched, total })}
                        {p.product_types.length > 0 ? ` · ${p.product_types.join(", ")}` : ""}
                        {p.estimated_cost_per_kg != null
                          ? ` · $${p.estimated_cost_per_kg.toFixed(2)}/kg`
                          : ""}
                      </p>
                      {p.missing_ingredients.length > 0 ? (
                        <p className="mt-2 text-xs text-warning">
                          Missing: {p.missing_ingredients.slice(0, 6).join(", ")}
                          {p.missing_ingredients.length > 6 ? "…" : ""}
                        </p>
                      ) : null}
                      <Link
                        href={`/chat?prompt=${encodeURIComponent(`Explain the formula: ${p.name}`)}`}
                        className="mt-3 inline-block text-xs font-semibold text-secondary transition hover:underline"
                      >
                        {t("warehouse.openChat")} →
                      </Link>
                    </li>
                    );
                  })}
                </ul>
              </section>
            ) : null}
          </div>
        </div>
      </div>
    </div>
  );
}
