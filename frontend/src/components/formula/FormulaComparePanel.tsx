"use client";

import { useMemo, useState } from "react";
import { useLocale } from "@/components/i18n/LocaleProvider";
import type { StructuredFormulationView } from "@/types/chat";

interface FormulaComparePanelProps {
  formulations: StructuredFormulationView[];
}

function ingredientKey(ing: StructuredFormulationView["ingredients"][0]): string {
  return (ing.normalized_name ?? ing.raw_name).toLowerCase();
}

export function FormulaComparePanel({ formulations }: FormulaComparePanelProps) {
  const { t } = useLocale();
  const options = formulations.filter((f) => f.ingredients.length > 0);

  const [leftId, setLeftId] = useState(options[0]?.formulation_id ?? "");
  const [rightId, setRightId] = useState(options[1]?.formulation_id ?? "");

  const left = options.find((f) => f.formulation_id === leftId);
  const right = options.find((f) => f.formulation_id === rightId);

  const rows = useMemo(() => {
    if (!left || !right) return [];
    const mapA = new Map(left.ingredients.map((i) => [ingredientKey(i), i]));
    const mapB = new Map(right.ingredients.map((i) => [ingredientKey(i), i]));
    const keys = new Set([...mapA.keys(), ...mapB.keys()]);
    return [...keys].sort().map((key) => ({
      key,
      a: mapA.get(key),
      b: mapB.get(key),
    }));
  }, [left, right]);

  if (options.length < 2) return null;

  return (
    <section className="rounded-2xl border border-border bg-surface p-4 shadow-sm">
      <h2 className="text-sm font-bold text-text-primary">{t("tools.compareTitle")}</h2>
      <p className="mt-1 text-xs text-text-secondary">{t("tools.compareSubtitle")}</p>

      <div className="mt-3 grid gap-2 sm:grid-cols-2">
        <select
          value={leftId}
          onChange={(e) => setLeftId(e.target.value)}
          className="rounded-lg border border-border bg-background px-2 py-1.5 text-xs"
        >
          {options.map((f) => (
            <option key={f.formulation_id} value={f.formulation_id}>
              {f.name}
            </option>
          ))}
        </select>
        <select
          value={rightId}
          onChange={(e) => setRightId(e.target.value)}
          className="rounded-lg border border-border bg-background px-2 py-1.5 text-xs"
        >
          {options.map((f) => (
            <option key={f.formulation_id} value={f.formulation_id}>
              {f.name}
            </option>
          ))}
        </select>
      </div>

      <div className="mt-3 max-h-64 overflow-auto rounded-xl border border-border/60">
        <table className="w-full text-start text-xs">
          <thead className="sticky top-0 bg-surface text-text-secondary">
            <tr>
              <th className="px-2 py-2 font-semibold">{t("tools.compareIngredient")}</th>
              <th className="px-2 py-2 font-semibold">{left?.name.slice(0, 12)}…</th>
              <th className="px-2 py-2 font-semibold">{right?.name.slice(0, 12)}…</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(({ key, a, b }) => (
              <tr key={key} className="border-t border-border/40">
                <td className="px-2 py-1.5 text-text-primary">{a?.raw_name ?? b?.raw_name ?? key}</td>
                <td className="px-2 py-1.5 font-mono text-text-secondary">
                  {a?.amount != null ? `${a.amount}${a.unit ?? ""}` : "—"}
                </td>
                <td className="px-2 py-1.5 font-mono text-text-secondary">
                  {b?.amount != null ? `${b.amount}${b.unit ?? ""}` : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
