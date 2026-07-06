"use client";

import { useEffect, useState } from "react";
import { useLocale } from "@/components/i18n/LocaleProvider";
import { fetchComplianceReport, type ComplianceReport } from "@/lib/formulations";
import type { StructuredFormulationView } from "@/types/chat";

interface ComplianceBadgeProps {
  formulation: StructuredFormulationView;
  markets?: string[];
}

const STATUS_STYLES: Record<string, string> = {
  pass: "border-success/40 bg-success/10 text-success",
  warn: "border-warning/40 bg-warning/10 text-warning",
  fail: "border-error/40 bg-error/10 text-error",
};

export function ComplianceBadge({ formulation, markets }: ComplianceBadgeProps) {
  const { t } = useLocale();
  const [report, setReport] = useState<ComplianceReport | null>(null);
  const [open, setOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const activeMarkets = (markets ?? ["EU"]).filter(Boolean);

  useEffect(() => {
    if (!formulation.formulation_id || activeMarkets.length === 0) return;
    setError(null);
    fetchComplianceReport(formulation.formulation_id, activeMarkets)
      .then(setReport)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed"));
  }, [formulation.formulation_id, activeMarkets.join(",")]);

  if (error) {
    return (
      <span className="rounded-md border border-warning/30 bg-warning/10 px-2 py-0.5 text-[10px] text-warning">
        {t("compliance.error")}
      </span>
    );
  }

  if (!report) {
    return (
      <span className="rounded-md border border-border bg-surface-sunken px-2 py-0.5 text-[10px] text-text-tertiary">
        {t("compliance.checking")}
      </span>
    );
  }

  const style = STATUS_STYLES[report.status] ?? STATUS_STYLES.pass;

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className={`rounded-md border px-2 py-0.5 text-[10px] font-bold uppercase ${style}`}
      >
        {t(`compliance.status.${report.status}`)}
      </button>
      {open && report.findings.length > 0 ? (
        <div className="absolute left-0 top-full z-20 mt-1 w-72 rounded-xl border border-border bg-surface-raised p-3 text-xs shadow-lg">
          <p className="font-semibold text-text-primary">{t("compliance.findings")}</p>
          <ul className="mt-2 space-y-2">
            {report.findings.map((f, i) => (
              <li key={`${f.ingredient}-${i}`} className="text-text-secondary">
                <span className="font-medium text-text-primary">{f.ingredient}</span>
                <span className="block">{f.message}</span>
                <span className="text-[10px] text-text-tertiary">{f.source_ref}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}
