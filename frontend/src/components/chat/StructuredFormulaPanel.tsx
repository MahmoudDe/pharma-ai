"use client";

import { useState } from "react";
import { BatchCalculator } from "@/components/formula/BatchCalculator";
import { useLocale } from "@/components/i18n/LocaleProvider";
import { downloadTextFile, formulaToCsv } from "@/lib/formulaExport";
import { formulaToMarkdown } from "@/lib/formulaMarkdown";
import type { StructuredFormulationView } from "@/types/chat";

interface StructuredFormulaPanelProps {
  formulation: StructuredFormulationView | null;
  formulations?: StructuredFormulationView[];
}

export function StructuredFormulaPanel({
  formulation,
  formulations,
}: StructuredFormulaPanelProps) {
  const list =
    formulations && formulations.length > 0
      ? formulations
      : formulation
        ? [formulation]
        : [];

  const visible = list.filter((f) => f.ingredients.length > 0);
  if (visible.length === 0) {
    return null;
  }

  return (
    <div className="stagger-children flex flex-col gap-4">
      {visible.map((item) => (
        <FormulaCard key={item.formulation_id} formulation={item} />
      ))}
    </div>
  );
}

function FormulaCard({ formulation }: { formulation: StructuredFormulationView }) {
  const { t } = useLocale();

  return (
    <section className="surface-card hover-lift p-4">
      <PanelHeader formulation={formulation} />
      <div className="mt-3 overflow-x-auto rounded-xl border border-border">
        <table className="w-full min-w-[280px] text-start text-sm">
          <thead>
            <tr className="border-b border-border bg-surface-sunken text-xs uppercase tracking-wide text-text-secondary">
              <th className="px-3 py-2.5 font-semibold">{t("formula.colIngredient")}</th>
              <th className="px-3 py-2.5 font-semibold">{t("formula.colAmount")}</th>
              <th className="px-3 py-2.5 font-semibold">{t("formula.colPhase")}</th>
            </tr>
          </thead>
          <tbody>
            {formulation.ingredients.map((ing, index) => (
              <tr
                key={`${ing.raw_name}-${index}`}
                className="border-b border-border/40 transition-colors hover:bg-secondary/5"
              >
                <td className="px-3 py-2 text-text-primary">{ing.raw_name}</td>
                <td className="px-3 py-2 font-mono text-text-secondary">
                  {ing.amount != null ? `${ing.amount}${ing.unit ?? ""}` : "—"}
                </td>
                <td className="px-3 py-2 text-text-secondary">{ing.phase ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <BatchCalculator formulation={formulation} />
      {formulation.procedure && formulation.procedure.length > 0 ? (
        <div className="mt-3 rounded-xl bg-surface/50 p-3 text-xs text-text-secondary">
          <p className="font-semibold text-text-primary">{t("formula.procedure")}</p>
          <ol className="mt-1 list-decimal space-y-1 pl-4">
            {formulation.procedure.slice(0, 5).map((step, i) => (
              <li key={i}>{step}</li>
            ))}
          </ol>
        </div>
      ) : null}
    </section>
  );
}

function PanelHeader({ formulation }: { formulation: StructuredFormulationView }) {
  const { t } = useLocale();
  const [copied, setCopied] = useState(false);

  const onCopy = async () => {
    await navigator.clipboard.writeText(formulaToMarkdown(formulation));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const onExportCsv = () => {
    const safeName = formulation.name.replace(/[^\w.-]+/g, "_").slice(0, 40);
    downloadTextFile(formulaToCsv(formulation), `${safeName}.csv`, "text/csv;charset=utf-8");
  };

  return (
    <div>
      <div className="flex items-start justify-between gap-2">
        <h2 className="flex items-center gap-2 text-sm font-bold text-text-primary">
          <span
            aria-hidden
            className="flex h-6 w-6 items-center justify-center rounded-lg text-secondary"
            style={{ background: "color-mix(in srgb, var(--secondary) 12%, transparent)" }}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round">
              <path d="M9 3h6M10 3v6.5L4.5 19a2 2 0 0 0 1.8 3h11.4a2 2 0 0 0 1.8-3L14 9.5V3" />
            </svg>
          </span>
          {t("formula.title")}
        </h2>
        <div className="flex shrink-0 gap-1">
          <button
            type="button"
            onClick={onExportCsv}
            className="rounded-lg border border-border px-2 py-1 text-xs font-semibold text-text-secondary transition hover:border-secondary/50 hover:bg-secondary/10 hover:text-secondary"
          >
            {t("formula.exportCsv")}
          </button>
          <button
            type="button"
            onClick={() => void onCopy()}
            className={`rounded-lg border px-2 py-1 text-xs font-semibold transition ${
              copied
                ? "border-success/40 bg-success/10 text-success"
                : "border-border text-secondary hover:border-secondary/50 hover:bg-secondary/10"
            }`}
          >
            {copied ? `✓ ${t("formula.copied")}` : t("formula.copy")}
          </button>
        </div>
      </div>
      <p className="mt-2 text-sm font-semibold text-text-primary">{formulation.name}</p>
      <div className="mt-2 flex flex-wrap items-center gap-1.5">
        <span className="rounded-md border border-border bg-surface-sunken px-2 py-0.5 text-[10px] font-semibold text-text-secondary">
          {(formulation.confidence * 100).toFixed(0)}% confidence
        </span>
        <span className="rounded-md border border-secondary/30 bg-secondary/10 px-2 py-0.5 font-mono text-[10px] font-semibold text-secondary">
          PDF p.{formulation.pdf_page}
        </span>
        {formulation.printed_page != null ? (
          <span className="rounded-md border border-border bg-surface-sunken px-2 py-0.5 font-mono text-[10px] text-text-secondary">
            Book p.{formulation.printed_page}
          </span>
        ) : null}
        <span className="rounded-md border border-border bg-[var(--panel-muted)] px-2 py-0.5 text-[10px] font-semibold text-text-secondary">
          {formulation.product_types.join(", ") || "general"}
        </span>
      </div>
    </div>
  );
}
