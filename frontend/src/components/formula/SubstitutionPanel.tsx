"use client";

import { useState } from "react";
import { useLocale } from "@/components/i18n/LocaleProvider";
import { fetchSubstitutions, type SubstitutionSuggestion } from "@/lib/formulations";
import type { StructuredBrief, StructuredFormulationView } from "@/types/chat";

interface SubstitutionPanelProps {
  formulation: StructuredFormulationView;
  brief?: StructuredBrief;
}

export function SubstitutionPanel({ formulation, brief }: SubstitutionPanelProps) {
  const { t } = useLocale();
  const [selected, setSelected] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [suggestions, setSuggestions] = useState<SubstitutionSuggestion[]>([]);
  const [error, setError] = useState<string | null>(null);

  const loadSuggestions = async (ingredient: string) => {
    setSelected(ingredient);
    setLoading(true);
    setError(null);
    try {
      const result = await fetchSubstitutions(
        formulation.formulation_id,
        ingredient,
        brief,
      );
      setSuggestions(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed");
      setSuggestions([]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="mt-4 rounded-xl border border-border bg-surface-sunken p-3">
      <p className="text-xs font-bold text-text-primary">{t("substitution.title")}</p>
      <p className="mt-1 text-[11px] text-text-secondary">{t("substitution.hint")}</p>
      <div className="mt-2 flex flex-wrap gap-1.5">
        {formulation.ingredients.map((ing) => (
          <button
            key={ing.raw_name}
            type="button"
            onClick={() => void loadSuggestions(ing.raw_name)}
            className={`rounded-lg border px-2 py-1 text-[11px] font-medium transition ${
              selected === ing.raw_name
                ? "border-secondary bg-secondary/15 text-secondary"
                : "border-border text-text-secondary hover:border-secondary/40"
            }`}
          >
            {ing.raw_name}
          </button>
        ))}
      </div>
      {loading ? (
        <p className="mt-2 text-[11px] text-text-tertiary">{t("substitution.loading")}</p>
      ) : null}
      {error ? (
        <p className="mt-2 text-[11px] text-error">{error}</p>
      ) : null}
      {suggestions.length > 0 ? (
        <ul className="mt-3 space-y-2">
          {suggestions.map((s) => (
            <li
              key={s.substitute}
              className="rounded-lg border border-border/70 bg-surface-raised px-3 py-2 text-xs"
            >
              <div className="flex items-center justify-between gap-2">
                <span className="font-semibold text-text-primary">{s.substitute}</span>
                <span className="font-mono text-[10px] text-text-tertiary">
                  {(s.confidence * 100).toFixed(0)}%
                </span>
              </div>
              <p className="mt-1 text-text-secondary">{s.reason}</p>
            </li>
          ))}
        </ul>
      ) : null}
      {!loading && selected && suggestions.length === 0 && !error ? (
        <p className="mt-2 text-[11px] text-text-tertiary">{t("substitution.empty")}</p>
      ) : null}
    </div>
  );
}
