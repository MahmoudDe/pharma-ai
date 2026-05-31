"use client";

import Link from "next/link";
import { useCallback, useState } from "react";
import { AppColors } from "@/constants/AppColors";
import { t } from "@/lib/i18n";
import { discoverProducts, resolveWarehouse, uploadWarehouseFile } from "@/lib/warehouse";
import type { DiscoverProductResult, ResolveResponse, UploadResponse } from "@/types/warehouse";

type Step = "upload" | "materials" | "products";

export default function WarehousePage() {
  const [step, setStep] = useState<Step>("upload");
  const [upload, setUpload] = useState<UploadResponse | null>(null);
  const [resolve, setResolve] = useState<ResolveResponse | null>(null);
  const [products, setProducts] = useState<DiscoverProductResult[]>([]);
  const [minCoverage, setMinCoverage] = useState(50);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const onFile = useCallback(async (file: File) => {
    setBusy(true);
    setError(null);
    try {
      const res = await uploadWarehouseFile(file);
      setUpload(res);
      setResolve(null);
      setProducts([]);
      setStep("upload");
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
      setStep("materials");
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
      setStep("products");
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
    <div className="min-h-screen bg-background p-4 lg:p-8">
      <div className="mx-auto max-w-5xl">
        <header className="mb-6 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-xl font-semibold text-text-primary">{t("warehouse.title")}</h1>
            <p className="text-sm text-text-secondary">
              Upload inventory, resolve ingredient names, discover formulas from references.
            </p>
          </div>
          <nav className="flex gap-2 text-sm">
            <Link href="/chat" className="rounded-lg border border-border px-3 py-1.5 text-text-primary">
              {t("nav.chat")}
            </Link>
            <span
              className="rounded-lg px-3 py-1.5 font-medium text-white"
              style={{ background: AppColors.buttonGradient }}
            >
              {t("nav.warehouse")}
            </span>
          </nav>
        </header>

        {error ? (
          <p className="mb-4 rounded-lg border border-error/30 bg-error/10 px-3 py-2 text-sm text-error">
            {error}
          </p>
        ) : null}

        <section className="rounded-2xl border border-border bg-surface p-6 shadow-sm">
          <h2 className="text-sm font-semibold text-text-primary">{t("warehouse.upload")}</h2>
          <label className="mt-4 flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed border-border bg-background px-6 py-10 text-center">
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
            <span className="text-sm text-text-secondary">
              Drop CSV or Excel (material name column required)
            </span>
          </label>
          {upload ? (
            <p className="mt-3 text-xs text-text-secondary">
              {upload.filename} — {upload.row_count} materials
            </p>
          ) : null}
          <div className="mt-4 flex flex-wrap gap-2">
            <button
              type="button"
              disabled={!upload || busy}
              onClick={() => void onAnalyze()}
              className="rounded-lg px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
              style={{ background: AppColors.buttonGradient }}
            >
              {t("warehouse.analyze")}
            </button>
            <button
              type="button"
              disabled={!resolve || busy}
              onClick={() => void onDiscover()}
              className="rounded-lg border border-border px-4 py-2 text-sm font-medium text-text-primary disabled:opacity-50"
            >
              {t("warehouse.discover")}
            </button>
            <label className="flex items-center gap-2 text-xs text-text-secondary">
              Min coverage %
              <input
                type="number"
                min={0}
                max={100}
                value={minCoverage}
                onChange={(e) => setMinCoverage(Number(e.target.value))}
                className="w-16 rounded border border-border bg-background px-2 py-1"
              />
            </label>
          </div>
        </section>

        {resolve && step !== "upload" ? (
          <section className="mt-6 rounded-2xl border border-border bg-surface p-4">
            <h2 className="text-sm font-semibold text-text-primary">Materials</h2>
            <p className="text-xs text-text-secondary">
              Resolved {resolve.resolved} · Needs review {resolve.needs_review}
            </p>
            <div className="mt-3 max-h-64 overflow-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="text-text-secondary">
                    <th className="py-1 pr-2">Raw</th>
                    <th className="py-1 pr-2">Canonical</th>
                    <th className="py-1">Conf.</th>
                  </tr>
                </thead>
                <tbody>
                  {resolve.materials.map((m) => (
                    <tr key={m.id} className="border-t border-border/60">
                      <td className="py-1 pr-2 text-text-primary">{m.raw_name}</td>
                      <td className="py-1 pr-2 text-text-secondary">
                        {m.canonical_name ?? "—"}
                        {m.needs_review ? " ⚠" : ""}
                      </td>
                      <td className="py-1">
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
          <section className="mt-6 rounded-2xl border border-border bg-surface p-4">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold text-text-primary">Products from references</h2>
              <button
                type="button"
                onClick={exportCsv}
                className="text-xs font-medium text-secondary underline"
              >
                Export CSV
              </button>
            </div>
            <ul className="mt-3 space-y-3">
              {products.map((p) => (
                <li
                  key={p.formulation_id}
                  className="rounded-xl border border-border bg-background p-3 text-sm"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="font-medium text-text-primary">{p.name}</span>
                    <span
                      className="rounded-full px-2 py-0.5 text-[10px] font-medium"
                      style={{
                        background: AppColors.softGradient,
                        color: AppColors.primary,
                      }}
                    >
                      {p.coverage_pct}% · {p.tier}
                    </span>
                  </div>
                  <p className="mt-1 text-xs text-text-secondary">
                    {p.doc_id} · PDF p.{p.pdf_page}
                    {p.printed_page != null ? ` · Book p.${p.printed_page}` : ""}
                  </p>
                  {p.missing_ingredients.length > 0 ? (
                    <p className="mt-1 text-xs text-warning">
                      Missing: {p.missing_ingredients.slice(0, 6).join(", ")}
                      {p.missing_ingredients.length > 6 ? "…" : ""}
                    </p>
                  ) : null}
                  <Link
                    href={`/chat?formula=${encodeURIComponent(p.name)}`}
                    className="mt-2 inline-block text-xs font-medium text-secondary"
                  >
                    Open in chat →
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        ) : null}
      </div>
    </div>
  );
}
