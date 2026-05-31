"use client";

import { useState } from "react";
import { AppColors } from "@/constants/AppColors";
import { formulaToMarkdown } from "@/lib/formulaMarkdown";
import { t } from "@/lib/i18n";
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
    <div className="flex flex-col gap-4">
      {visible.map((item) => (
        <FormulaCard key={item.formulation_id} formulation={item} />
      ))}
    </div>
  );
}

function FormulaCard({ formulation }: { formulation: StructuredFormulationView }) {
  return (
    <section className="rounded-xl border border-border bg-background p-4">
      <PanelHeader formulation={formulation} />
      <div className="mt-3 overflow-x-auto">
        <table className="w-full min-w-[280px] text-left text-sm">
          <thead>
            <tr className="border-b border-border text-xs uppercase tracking-wide text-text-secondary">
              <th className="py-2 pr-3 font-medium">Ingredient</th>
              <th className="py-2 pr-3 font-medium">Amount</th>
              <th className="py-2 font-medium">Phase</th>
            </tr>
          </thead>
          <tbody>
            {formulation.ingredients.map((ing, index) => (
              <tr key={`${ing.raw_name}-${index}`} className="border-b border-border/60">
                <td className="py-2 pr-3 text-text-primary">{ing.raw_name}</td>
                <td className="py-2 pr-3 font-mono text-text-secondary">
                  {ing.amount != null ? `${ing.amount}${ing.unit ?? ""}` : "—"}
                </td>
                <td className="py-2 text-text-secondary">{ing.phase ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {formulation.procedure && formulation.procedure.length > 0 ? (
        <div className="mt-3 text-xs text-text-secondary">
          <p className="font-medium text-text-primary">Procedure</p>
          <ol className="mt-1 list-decimal pl-4">
            {formulation.procedure.slice(0, 5).map((step, i) => (
              <li key={i} className="mt-0.5">
                {step}
              </li>
            ))}
          </ol>
        </div>
      ) : null}
    </section>
  );
}

function PanelHeader({ formulation }: { formulation: StructuredFormulationView }) {
  const [copied, setCopied] = useState(false);

  const onCopy = async () => {
    await navigator.clipboard.writeText(formulaToMarkdown(formulation));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div>
      <div className="flex items-start justify-between gap-2">
        <h2 className="text-sm font-semibold text-text-primary">Structured formula</h2>
        <button
          type="button"
          onClick={() => void onCopy()}
          className="shrink-0 text-xs font-medium text-secondary hover:underline"
        >
          {copied ? t("formula.copied") : t("formula.copy")}
        </button>
      </div>
      <p className="mt-1 text-xs text-text-secondary">{formulation.name}</p>
      <p className="mt-1 text-[10px] text-text-secondary">
        Extracted · confidence {(formulation.confidence * 100).toFixed(0)}% · PDF p.
        {formulation.pdf_page}
        {formulation.printed_page != null ? ` · Book p.${formulation.printed_page}` : ""}
      </p>
      <span
        className="mt-2 inline-block rounded-full px-2 py-0.5 text-[10px] font-medium text-white"
        style={{ background: AppColors.softGradient, color: AppColors.primary }}
      >
        {formulation.product_types.join(", ") || "general"}
      </span>
    </div>
  );
}
