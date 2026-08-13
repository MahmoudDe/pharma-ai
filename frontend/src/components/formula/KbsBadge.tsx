"use client";

import { useLocale } from "@/components/i18n/LocaleProvider";
import type { KbsReport } from "@/lib/formulations";

const STATUS_STYLES: Record<string, string> = {
  verified: "bg-success/10 text-success border-success/30",
  review: "bg-warning/10 text-warning border-warning/30",
  low_precision: "bg-error/10 text-error border-error/30",
};

export function KbsBadge({
  status,
  score,
  className = "",
}: {
  status?: string | null;
  score?: number | null;
  className?: string;
}) {
  const { t } = useLocale();
  if (!status) return null;
  const style = STATUS_STYLES[status] ?? STATUS_STYLES.review;
  const label =
    status === "verified"
      ? t("kbs.verified")
      : status === "low_precision"
        ? t("kbs.lowPrecision")
        : t("kbs.review");
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-semibold ${style} ${className}`}
      title={t("kbs.badgeTitle")}
    >
      {label}
      {typeof score === "number" ? <span className="opacity-75">{score.toFixed(2)}</span> : null}
    </span>
  );
}

export function KbsReportPanel({ report }: { report: KbsReport }) {
  const { t } = useLocale();
  const severityRank: Record<string, number> = { error: 0, warning: 1, info: 2 };
  const dotColor: Record<string, string> = {
    error: "bg-error",
    warning: "bg-warning",
    info: "bg-text-secondary/40",
  };
  const shown = report.findings
    .filter((f) => f.family !== "regulatory")
    .sort((a, b) => (severityRank[a.severity] ?? 3) - (severityRank[b.severity] ?? 3))
    .slice(0, 5);

  return (
    <div className="surface-inset rounded-2xl px-4 py-3">
      <div className="flex flex-wrap items-center gap-2">
        <p className="text-xs font-bold uppercase tracking-wide text-text-secondary">
          {t("kbs.panelTitle")}
        </p>
        <KbsBadge status={report.status} score={report.precision_score} />
        {report.compliance_status !== "skipped" ? (
          <span className="text-[11px] text-text-secondary">
            {t("kbs.compliance")}: {report.compliance_status}
          </span>
        ) : null}
      </div>
      {shown.length > 0 ? (
        <ul className="mt-2 space-y-1">
          {shown.map((f, i) => (
            <li key={i} className="flex items-start gap-1.5 text-xs text-text-secondary">
              <span
                aria-hidden
                className={`mt-1 h-1.5 w-1.5 shrink-0 rounded-full ${
                  dotColor[f.severity] ?? "bg-warning"
                }`}
              />
              <span>{f.message}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-2 text-xs text-text-secondary">{t("kbs.noFindings")}</p>
      )}
    </div>
  );
}
