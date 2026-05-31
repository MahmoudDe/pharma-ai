"use client";

import { useLocale } from "@/components/i18n/LocaleProvider";
import { sourcePdfUrl } from "@/lib/sources";
import type { CitedEvidence } from "@/types/chat";

interface EvidencePanelProps {
  evidence: CitedEvidence[];
}

const CONFIDENCE_STYLES: Record<string, string> = {
  high: "border-success/30 bg-success/10 text-success",
  medium: "border-warning/30 bg-warning/10 text-warning",
  low: "border-error/30 bg-error/10 text-error",
  unknown: "border-border bg-background text-text-secondary",
};

function ConfidenceBadge({ value, label }: { value?: CitedEvidence["confidence"]; label: string }) {
  const key = value ?? "unknown";
  const className = CONFIDENCE_STYLES[key] ?? CONFIDENCE_STYLES.unknown;
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${className}`}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-current" />
      {label}
    </span>
  );
}

function PageBadges({
  item,
  openLabel,
}: {
  item: CitedEvidence;
  openLabel: string;
}) {
  const pdfPage = item.pdf_page ?? item.page;
  const bookPage = item.printed_page;
  const href = pdfPage ? sourcePdfUrl(item.document_id, pdfPage) : sourcePdfUrl(item.document_id);

  return (
    <div className="flex shrink-0 flex-col items-end gap-1">
      {pdfPage ? (
        <a
          href={href}
          target="_blank"
          rel="noopener noreferrer"
          className="rounded-md border border-secondary/40 bg-secondary/10 px-1.5 py-0.5 font-mono text-[10px] font-semibold text-secondary transition hover:underline"
        >
          {openLabel} {pdfPage}
        </a>
      ) : null}
      {bookPage ? (
        <span className="rounded-md border border-secondary/30 bg-secondary/10 px-1.5 py-0.5 font-mono text-[10px] text-text-primary">
          Book p.{bookPage}
        </span>
      ) : null}
    </div>
  );
}

export function EvidencePanel({ evidence }: EvidencePanelProps) {
  const { t } = useLocale();

  return (
    <section className="flex min-h-0 flex-col rounded-2xl border border-border bg-surface p-4 shadow-sm">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-bold text-text-primary">{t("evidence.title")}</h2>
        {evidence.length > 0 ? (
          <span className="rounded-full border border-border bg-surface px-2.5 py-0.5 text-[10px] font-semibold text-text-secondary">
            {evidence.length}
          </span>
        ) : null}
      </div>

      {evidence.length === 0 ? (
        <p className="mt-3 text-sm leading-relaxed text-text-secondary">{t("evidence.empty")}</p>
      ) : (
        <ul className="stagger-children mt-3 flex-1 space-y-3 overflow-y-auto pr-1">
          {evidence.map((item, index) => (
            <li
              key={`${item.document_id}-${item.pdf_page ?? item.page ?? "na"}-${index}`}
              className={`hover-lift rounded-xl border bg-surface/90 p-3 text-sm ${
                item.quote_verified === false ? "border-warning/40" : "border-border/80"
              }`}
            >
              <div className="flex items-start justify-between gap-2">
                <p className="line-clamp-2 flex-1 text-xs font-semibold uppercase tracking-wide text-text-secondary">
                  {item.document_id}
                </p>
                <PageBadges item={item} openLabel={t("evidence.openPdf")} />
              </div>
              <p className="mt-2 line-clamp-5 whitespace-pre-wrap leading-relaxed text-text-primary">
                “{item.quote}”
              </p>
              <div className="mt-3 flex flex-wrap items-center gap-2">
                <ConfidenceBadge value={item.confidence} label={item.confidence ?? "unknown"} />
                {item.quote_verified === true ? (
                  <span className="rounded-md border border-success/30 bg-success/10 px-2 py-0.5 text-[10px] font-medium text-success">
                    {t("evidence.verified")}
                  </span>
                ) : item.quote_verified === false ? (
                  <span
                    className="rounded-md border border-warning/30 bg-warning/10 px-2 py-0.5 text-[10px] font-medium text-warning"
                    title={t("evidence.unverifiedHint")}
                  >
                    {t("evidence.unverified")}
                  </span>
                ) : null}
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
