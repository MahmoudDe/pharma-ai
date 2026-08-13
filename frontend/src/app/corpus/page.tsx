"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { AppHeader } from "@/components/ui/AppHeader";
import { Spinner } from "@/components/ui/Spinner";
import { useLocale } from "@/components/i18n/LocaleProvider";
import {
  fetchCorpusStats,
  fetchIngestJobs,
  fetchIngestQuality,
  startIngestJob,
  type CorpusStats,
  type IngestJob,
  type IngestQualityReport,
} from "@/lib/corpus";
import { sourcePdfUrl } from "@/lib/sources";

export default function CorpusPage() {
  const { t } = useLocale();
  const [stats, setStats] = useState<CorpusStats | null>(null);
  const [quality, setQuality] = useState<IngestQualityReport | null>(null);
  const [jobs, setJobs] = useState<IngestJob[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [ingestBusy, setIngestBusy] = useState(false);

  const refresh = useCallback(async () => {
    const [s, q, j] = await Promise.all([
      fetchCorpusStats(),
      fetchIngestQuality(),
      fetchIngestJobs(),
    ]);
    setStats(s);
    setQuality(q);
    setJobs(j);
  }, []);

  useEffect(() => {
    refresh()
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load"))
      .finally(() => setLoading(false));
  }, [refresh]);

  useEffect(() => {
    const hasActive = jobs.some((j) => j.status === "queued" || j.status === "running");
    if (!hasActive) return;
    const timer = window.setInterval(() => {
      void refresh().catch(() => undefined);
    }, 3000);
    return () => window.clearInterval(timer);
  }, [jobs, refresh]);

  const runIngest = async (force: boolean) => {
    setIngestBusy(true);
    setError(null);
    try {
      await startIngestJob({ force });
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ingest failed");
    } finally {
      setIngestBusy(false);
    }
  };

  const manifest = stats?.ingest_manifest ? Object.values(stats.ingest_manifest) : [];

  return (
    <div className="app-mesh-bg min-h-screen">
      <div className="relative z-10 mx-auto max-w-3xl px-4 py-6 lg:px-8 lg:py-10">
        <div className="panel-solid animate-scale-in overflow-hidden rounded-3xl">
          <AppHeader active="corpus" />

          <div className="space-y-6 px-6 py-8 lg:px-8">
            <div>
              <p className="eyebrow">{t("nav.corpus")}</p>
              <h2 className="mt-1.5 text-2xl font-extrabold tracking-tight text-text-primary">{t("corpus.title")}</h2>
              <p className="mt-1.5 text-sm text-text-secondary">{t("corpus.subtitle")}</p>
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

            {stats ? (
              <>
                <div
                  className={`flex items-center gap-3 rounded-2xl border p-4 ${
                    stats.ready
                      ? "border-success/30 bg-success/5"
                      : "border-warning/30 bg-warning/5"
                  }`}
                >
                  <span className="relative flex h-3 w-3">
                    {stats.ready ? (
                      <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-success opacity-50" />
                    ) : null}
                    <span
                      className={`relative inline-flex h-3 w-3 rounded-full ${stats.ready ? "bg-success" : "bg-warning animate-pulse"}`}
                    />
                  </span>
                  <p className="font-semibold text-text-primary">
                    {stats.ready ? t("corpus.ready") : t("corpus.notReady")}
                  </p>
                </div>

                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                  {[
                    { label: t("corpus.formulations"), value: stats.formulation_count },
                    { label: t("corpus.ingredients"), value: stats.ingredient_count },
                    { label: t("corpus.vectorChunks"), value: stats.qdrant_points },
                    {
                      label: t("corpus.bm25Chunks"),
                      value: stats.bm25_documents ?? 0,
                    },
                  ].map((card) => (
                    <div
                      key={card.label}
                      className="surface-card hover-lift p-5 text-center"
                    >
                      <p className="gradient-text text-3xl font-extrabold tabular-nums">{card.value}</p>
                      <p className="mt-1.5 text-xs font-medium text-text-secondary">{card.label}</p>
                    </div>
                  ))}
                </div>

                {stats.formulation_store ? (
                  <p className="text-xs text-text-secondary">
                    {t("corpus.storeBackend")}: <span className="font-semibold">{stats.formulation_store}</span>
                    {(stats.ocr_pages_total ?? 0) > 0 ? (
                      <span className="ms-2">
                        · {t("corpus.ocrTotal")}: {stats.ocr_pages_total}
                      </span>
                    ) : null}
                  </p>
                ) : null}

                {quality ? (
                  <section className="surface-inset p-4">
                    <h3 className="text-sm font-bold text-text-primary">{t("corpus.qualityTitle")}</h3>
                    <p
                      className={`mt-2 text-xs font-semibold ${
                        quality.passed ? "text-success" : "text-warning"
                      }`}
                    >
                      {quality.passed ? t("corpus.qualityPassed") : t("corpus.qualityFailed")}
                    </p>
                    <div className="mt-3 grid gap-2 text-xs text-text-secondary sm:grid-cols-2">
                      <span>
                        {t("corpus.qualityMedianIngredients")}:{" "}
                        {quality.ingest_quality.median_ingredients.toFixed(1)}
                      </span>
                      <span>
                        {t("corpus.qualityWithAmounts")}:{" "}
                        {(quality.ingest_quality.share_with_amounts * 100).toFixed(0)}%
                      </span>
                    </div>
                    {quality.ingest_quality.failures.length > 0 ? (
                      <ul className="mt-2 space-y-1 text-xs text-warning">
                        {quality.ingest_quality.failures.map((f) => (
                          <li key={f}>{f}</li>
                        ))}
                      </ul>
                    ) : null}
                    <Link
                      href="/formulations/review"
                      className="mt-3 inline-block text-xs font-semibold text-secondary hover:underline"
                    >
                      {t("corpus.reviewLink")} →
                    </Link>
                  </section>
                ) : null}

                <section className="surface-inset p-4">
                  <h3 className="text-sm font-bold text-text-primary">{t("corpus.ingestTitle")}</h3>
                  <p className="mt-1 text-xs text-text-secondary">{t("corpus.ingestSubtitle")}</p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <button
                      type="button"
                      disabled={ingestBusy}
                      onClick={() => void runIngest(false)}
                      className="btn-primary rounded-xl px-4 py-2 text-xs font-semibold disabled:opacity-60"
                    >
                      {ingestBusy ? t("corpus.ingestRunning") : t("corpus.startIngest")}
                    </button>
                    <button
                      type="button"
                      disabled={ingestBusy}
                      onClick={() => void runIngest(true)}
                      className="rounded-xl border border-border px-4 py-2 text-xs font-semibold text-text-secondary hover:border-secondary/40"
                    >
                      {t("corpus.forceIngest")}
                    </button>
                  </div>
                  {jobs.length > 0 ? (
                    <ul className="mt-3 space-y-2 text-xs">
                      {jobs.slice(0, 5).map((job) => (
                        <li
                          key={job.id}
                          className="flex items-center justify-between gap-2 rounded-lg border border-border/60 px-3 py-2"
                        >
                          <span className="font-mono text-text-secondary">{job.id.slice(0, 8)}</span>
                          <span
                            className={
                              job.status === "done"
                                ? "text-success"
                                : job.status === "failed"
                                  ? "text-error"
                                  : "text-warning"
                            }
                          >
                            {job.status === "running"
                              ? t("corpus.ingestRunning")
                              : job.status === "done"
                                ? t("corpus.ingestDone")
                                : job.status === "failed"
                                  ? t("corpus.ingestFailed")
                                  : job.status}
                          </span>
                        </li>
                      ))}
                    </ul>
                  ) : null}
                </section>

                <section className="surface-inset p-4">
                  <h3 className="text-sm font-bold text-text-primary">{t("corpus.dependencies")}</h3>
                  <ul className="mt-3 space-y-2 text-xs">
                    {stats.dependencies.map((d) => (
                      <li
                        key={d.name}
                        className="flex justify-between gap-2 rounded-lg border border-border/60 px-3 py-2"
                      >
                        <span className="font-semibold text-text-primary">{d.name}</span>
                        <span className={d.ok ? "text-success" : "text-warning"}>
                          {d.ok ? "✓" : "✗"} {d.detail}
                        </span>
                      </li>
                    ))}
                  </ul>
                </section>

                {manifest.length > 0 ? (
                  <section className="surface-inset p-4">
                    <h3 className="text-sm font-bold text-text-primary">{t("corpus.manifestTitle")}</h3>
                    <ul className="mt-3 space-y-2 text-xs">
                      {manifest.map((doc) => (
                        <li
                          key={doc.doc_id}
                          className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border/60 px-3 py-2"
                        >
                          <span className="text-text-primary">{doc.filename}</span>
                          <span className="text-text-secondary">
                            {doc.formulations} formulas · {doc.chunks} chunks
                            {(doc.ocr_pages_count ?? 0) > 0
                              ? ` · ${doc.ocr_pages_count} ${t("corpus.ocrPages")}`
                              : ""}
                          </span>
                        </li>
                      ))}
                    </ul>
                  </section>
                ) : null}

                <section className="surface-inset p-4">
                  <h3 className="text-sm font-bold text-text-primary">{t("corpus.sources")}</h3>
                  <ul className="mt-3 space-y-2 text-xs">
                    {stats.source_documents.map((doc) => (
                      <li key={doc.doc_id} className="flex flex-wrap items-center justify-between gap-2">
                        <span className="text-text-secondary">{doc.filename}</span>
                        <a
                          href={sourcePdfUrl(doc.doc_id)}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="font-semibold text-secondary hover:underline"
                        >
                          {doc.doc_id}
                        </a>
                      </li>
                    ))}
                  </ul>
                </section>

                <Link
                  href="/chat"
                  className="btn-primary inline-flex items-center gap-2 rounded-xl px-5 py-2.5 text-sm font-semibold"
                >
                  {t("home.openChat")}
                  <span aria-hidden className="rtl:rotate-180">→</span>
                </Link>
              </>
            ) : null}
          </div>
        </div>
      </div>
    </div>
  );
}
