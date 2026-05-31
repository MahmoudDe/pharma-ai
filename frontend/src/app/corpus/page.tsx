"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AppHeader } from "@/components/ui/AppHeader";
import { Spinner } from "@/components/ui/Spinner";
import { useLocale } from "@/components/i18n/LocaleProvider";
import { AppColors } from "@/constants/AppColors";
import { fetchCorpusStats, type CorpusStats } from "@/lib/corpus";
import { sourcePdfUrl } from "@/lib/sources";

export default function CorpusPage() {
  const { t } = useLocale();
  const [stats, setStats] = useState<CorpusStats | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchCorpusStats()
      .then(setStats)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load"))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="app-mesh-bg min-h-screen">
      <div className="relative z-10 mx-auto max-w-3xl px-4 py-6 lg:px-8 lg:py-10">
        <div className="panel-solid animate-scale-in overflow-hidden rounded-3xl">
          <AppHeader active="corpus" />

          <div className="space-y-6 px-6 py-8 lg:px-8">
            <div>
              <h2 className="text-2xl font-bold text-text-primary">{t("corpus.title")}</h2>
              <p className="mt-1 text-sm text-text-secondary">{t("corpus.subtitle")}</p>
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
                  className="flex items-center gap-3 rounded-2xl border border-border/80 bg-background/50 p-4"
                  style={stats.ready ? { borderColor: "rgba(34,197,94,0.3)" } : undefined}
                >
                  <span
                    className={`h-3 w-3 rounded-full ${stats.ready ? "bg-success" : "bg-warning animate-pulse"}`}
                  />
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
                      className="rounded-2xl border border-border/80 bg-surface/90 p-4 text-center"
                    >
                      <p className="text-2xl font-bold text-text-primary">{card.value}</p>
                      <p className="mt-1 text-xs text-text-secondary">{card.label}</p>
                    </div>
                  ))}
                </div>

                <section className="rounded-2xl border border-border/80 bg-background/50 p-4">
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

                <section className="rounded-2xl border border-border/80 bg-background/50 p-4">
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
                  className="btn-primary inline-flex rounded-xl px-5 py-2.5 text-sm font-semibold text-white"
                  style={{ background: AppColors.buttonGradient }}
                >
                  {t("home.openChat")}
                </Link>
              </>
            ) : null}
          </div>
        </div>
      </div>
    </div>
  );
}
