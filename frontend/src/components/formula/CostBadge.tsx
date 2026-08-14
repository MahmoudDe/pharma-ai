"use client";

import { useEffect, useState } from "react";
import { useLocale } from "@/components/i18n/LocaleProvider";
import { fetchFormulationCost, type FormulationCost } from "@/lib/formulations";

interface CostBadgeProps {
  formulationId: string;
}

export function CostBadge({ formulationId }: CostBadgeProps) {
  const { t } = useLocale();
  const [cost, setCost] = useState<FormulationCost | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchFormulationCost(formulationId)
      .then((data) => {
        if (!cancelled) setCost(data);
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof Error ? e.message : "Failed");
      });
    return () => {
      cancelled = true;
    };
  }, [formulationId]);

  if (error) {
    return <p className="mt-2 text-[11px] text-text-tertiary">{t("cost.unavailable")}</p>;
  }

  if (!cost || cost.cost_per_kg == null) {
    return <p className="mt-2 text-[11px] text-text-tertiary">{t("cost.partial")}</p>;
  }

  return (
    <div className="mt-3 rounded-xl border border-border/80 bg-[var(--panel-muted)] p-3 text-xs">
      <p className="font-bold text-text-primary">{t("cost.title")}</p>
      <p className="mt-1 font-mono text-sm text-text-primary">
        ${cost.cost_per_kg.toFixed(2)} / kg
      </p>
      <p className="mt-1 text-[11px] text-text-secondary">
        {t("cost.coverage", { pct: Math.round(cost.covered_percent * 100) })}
      </p>
      {cost.missing_ingredients.length > 0 ? (
        <p className="mt-1 text-[10px] text-text-tertiary">
          {t("cost.missing")}: {cost.missing_ingredients.slice(0, 4).join(", ")}
        </p>
      ) : null}
    </div>
  );
}
