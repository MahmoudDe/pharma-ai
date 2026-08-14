"use client";

import { useEffect, useMemo, useState } from "react";
import { useLocale } from "@/components/i18n/LocaleProvider";
import type { StructuredFormulationView } from "@/types/chat";

interface BatchCalculatorProps {
  formulation: StructuredFormulationView;
  defaultBatchKg?: number;
}

function parseBaseTotal(ingredients: StructuredFormulationView["ingredients"]): number | null {
  let sum = 0;
  let hasAny = false;
  for (const ing of ingredients) {
    if (ing.amount == null || ing.unit !== "%") continue;
    sum += ing.amount;
    hasAny = true;
  }
  if (!hasAny || sum <= 0) return null;
  return sum;
}

export function BatchCalculator({ formulation, defaultBatchKg }: BatchCalculatorProps) {
  const { t } = useLocale();
  const [batchKg, setBatchKg] = useState(
    defaultBatchKg != null && defaultBatchKg > 0 ? String(defaultBatchKg) : "1",
  );

  useEffect(() => {
    if (defaultBatchKg != null && defaultBatchKg > 0) {
      setBatchKg(String(defaultBatchKg));
    }
  }, [defaultBatchKg, formulation.formulation_id]);

  const baseTotal = useMemo(() => parseBaseTotal(formulation.ingredients), [formulation]);

  const scaled = useMemo(() => {
    const batch = parseFloat(batchKg);
    if (!baseTotal || !Number.isFinite(batch) || batch <= 0) return null;
    const factor = batch / baseTotal;
    return formulation.ingredients.map((ing) => {
      if (ing.amount == null) {
        return { ing, scaledAmount: null as number | null, scaledUnit: "" };
      }
      const scaledAmount =
        ing.unit === "%" ? (ing.amount / 100) * batch * 1000 : ing.amount * factor;
      const scaledUnit = ing.unit === "%" ? "g" : ing.unit ?? "";
      return { ing, scaledAmount, scaledUnit };
    });
  }, [batchKg, baseTotal, formulation.ingredients]);

  if (!baseTotal) return null;

  return (
    <div className="mt-3 rounded-xl border border-border/80 bg-[var(--panel-muted)] p-3">
      <p className="text-xs font-bold text-text-primary">{t("tools.batchTitle")}</p>
      <label className="mt-2 flex items-center gap-2 text-xs text-text-secondary">
        {t("tools.batchSize")}
        <input
          type="number"
          min={0.001}
          step={0.1}
          value={batchKg}
          onChange={(e) => setBatchKg(e.target.value)}
          className="w-24 rounded-lg border border-border bg-surface px-2 py-1 text-text-primary"
        />
        <span>kg</span>
        <span className="text-[10px]">({t("tools.batchBasis", { total: baseTotal.toFixed(1) })})</span>
      </label>
      {scaled ? (
        <ul className="mt-2 max-h-32 space-y-1 overflow-y-auto text-xs text-text-secondary">
          {scaled.map((row, i) => (
            <li key={i} className="flex justify-between gap-2">
              <span className="truncate text-text-primary">{row.ing.raw_name}</span>
              <span className="shrink-0 font-mono">
                {row.scaledAmount != null
                  ? `${row.scaledAmount.toFixed(2)} ${row.scaledUnit}`
                  : "—"}
              </span>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
