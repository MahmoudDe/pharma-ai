"use client";

import Link from "next/link";
import { useCallback, useState } from "react";
import { AppHeader } from "@/components/ui/AppHeader";
import { Spinner } from "@/components/ui/Spinner";
import { AppColors } from "@/constants/AppColors";
import { t } from "@/lib/i18n";
import { discoverProducts, resolveWarehouse, uploadWarehouseFile } from "@/lib/warehouse";
import type { DiscoverProductResult, ResolveResponse, UploadResponse } from "@/types/warehouse";

type Step = 1 | 2 | 3;

const STEPS: { n: Step; label: string }[] = [
  { n: 1, label: "Upload" },
  { n: 2, label: "Resolve" },
  { n: 3, label: "Discover" },
];

function tierStyle(tier: string) {
  if (tier === "makeable") return "text-success border-success/30 bg-success/10";
  if (tier === "partial") return "text-warning border-warning/30 bg-warning/10";
  return "text-text-secondary border-border bg-background";
}

export default function WarehousePage() {
  const [step, setStep] = useState<Step>(1);
  const [upload, setUpload] = useState<UploadResponse | null>(null);
  const [resolve, setResolve] = useState<ResolveResponse | null>(null);
  const [products, setProducts] = useState<DiscoverProductResult[]>([]);
  const [minCoverage, setMinCoverage] = useState(50);
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

  const onDiscover = async () => {
    if (!upload) return;
    setBusy(true);
    setError(null);
    try {
      const res = await discoverProducts(upload.upload_id, minCoverage);
      setProducts(res.products);
      setStep(3);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Discover failed");
    } finally {
      setBusy(false);
    }
  };

  const exportCsv = () => {
    const header = "name,coverage_pct,tier,doc_id,pdf_page,missing\n";
    const rows = products.map(
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
        <div className="glass-panel animate-scale-in overflow-hidden rounded-3xl">
          <AppHeader active="warehouse" />

          <div className="border-b border-border/60 px-6 py-6 lg:px-8">
            <h2 className="animate-fade-in-up text-2xl font-bold tracking-tight text-text-primary">
              {t("warehouse.title")}
            </h2>
            <p className="animate-fade-in-up mt-1 text-sm text-text-secondary" style={{ animationDelay: "60ms" }}>
              {t("warehouse.subtitle")}
            </p>

            <ol className="mt-6 flex flex-wrap gap-2">
              {STEPS.map(({ n, label }) => {
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
                      style={active && !done ? { background: AppColors.buttonGradient } : undefined}
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

            <section className="animate-fade-in-up rounded-2xl border border-border/80 bg-background/50 p-6">
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
                    <span className="text-3xl opacity-40">📦</span>
                    <p className="mt-3 text-sm font-medium text-text-primary">
                      {t("warehouse.dropHint")}
                    </p>
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
                  className="btn-primary inline-flex items-center gap-2 rounded-xl px-5 py-2.5 text-sm font-semibold text-white shadow-md disabled:opacity-40"
                  style={{ background: AppColors.buttonGradient }}
                >
                  {busy ? <Spinner className="h-4 w-4 text-white" /> : null}
                  {t("warehouse.analyze")}
                </button>
                <button
                  type="button"
                  disabled={!resolve || busy}
                  onClick={() => void onDiscover()}
                  className="hover-lift rounded-xl border border-border px-5 py-2.5 text-sm font-semibold text-text-primary disabled:opacity-40"
                >
                  {t("warehouse.discover")}
                </button>
                <label className="flex items-center gap-2 text-xs text-text-secondary">
                  Min coverage
                  <input
                    type="number"
                    min={0}
                    max={100}
                    value={minCoverage}
                    onChange={(e) => setMinCoverage(Number(e.target.value))}
                    className="w-16 rounded-lg border border-border bg-surface px-2 py-1"
                  />
                  %
                </label>
              </div>
            </section>

            {resolve ? (
              <section className="animate-fade-in-up rounded-2xl border border-border/80 bg-background/50 p-6">
                <h3 className="text-sm font-bold text-text-primary">{t("warehouse.materials")}</h3>
                <p className="mt-1 text-xs text-text-secondary">
                  Resolved {resolve.resolved} · Review {resolve.needs_review}
                </p>
                <div className="mt-4 max-h-56 overflow-auto rounded-xl border border-border/60">
                  <table className="w-full text-left text-xs">
                    <thead className="sticky top-0 bg-surface/95 text-text-secondary">
                      <tr>
                        <th className="px-3 py-2 font-semibold">Raw</th>
                        <th className="px-3 py-2 font-semibold">Canonical</th>
                        <th className="px-3 py-2 font-semibold">Conf.</th>
                      </tr>
                    </thead>
                    <tbody>
                      {resolve.materials.map((m) => (
                        <tr key={m.id} className="border-t border-border/40 hover:bg-secondary/5">
                          <td className="px-3 py-2 text-text-primary">{m.raw_name}</td>
                          <td className="px-3 py-2 text-text-secondary">
                            {m.canonical_name ?? "—"}
                            {m.needs_review ? " ⚠" : ""}
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

            {products.length > 0 ? (
              <section className="animate-fade-in-up rounded-2xl border border-border/80 bg-background/50 p-6">
                <div className="flex items-center justify-between gap-3">
                  <h3 className="text-sm font-bold text-text-primary">{t("warehouse.products")}</h3>
                  <button
                    type="button"
                    onClick={exportCsv}
                    className="text-xs font-semibold text-secondary underline-offset-2 hover:underline"
                  >
                    {t("warehouse.export")}
                  </button>
                </div>
                <ul className="stagger-children mt-4 space-y-3">
                  {products.map((p) => (
                    <li
                      key={p.formulation_id}
                      className="hover-lift rounded-2xl border border-border/80 bg-surface/90 p-4"
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
                        {p.doc_id} · PDF p.{p.pdf_page}
                        {p.printed_page != null ? ` · Book p.${p.printed_page}` : ""}
                      </p>
                      {p.missing_ingredients.length > 0 ? (
                        <p className="mt-2 text-xs text-warning">
                          Missing: {p.missing_ingredients.slice(0, 5).join(", ")}
                          {p.missing_ingredients.length > 5 ? "…" : ""}
                        </p>
                      ) : null}
                      <Link
                        href={`/chat?prompt=${encodeURIComponent(`Explain the formula: ${p.name}`)}`}
                        className="mt-3 inline-block text-xs font-semibold text-secondary transition hover:underline"
                      >
                        {t("warehouse.openChat")} →
                      </Link>
                    </li>
                  ))}
                </ul>
              </section>
            ) : null}
          </div>
        </div>
      </div>
    </div>
  );
}
