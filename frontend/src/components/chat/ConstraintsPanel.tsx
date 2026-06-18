"use client";

import { useState } from "react";
import { useLocale } from "@/components/i18n/LocaleProvider";
import type { StructuredBrief } from "@/types/chat";

interface ConstraintsPanelProps {
  brief: StructuredBrief;
  onChange: (brief: StructuredBrief) => void;
}

function splitList(value: string): string[] | undefined {
  const items = value
    .split(/[,;]+/)
    .map((s) => s.trim())
    .filter(Boolean);
  return items.length > 0 ? items : undefined;
}

export function ConstraintsPanel({ brief, onChange }: ConstraintsPanelProps) {
  const { t } = useLocale();
  const [open, setOpen] = useState(false);
  const hasValues =
    Boolean(brief.product_type) ||
    (brief.banned_ingredients?.length ?? 0) > 0 ||
    (brief.preferred_ingredients?.length ?? 0) > 0;

  return (
    <section className="panel-muted-band relative z-10 shrink-0 px-4 py-2 lg:px-6">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between rounded-lg px-1 py-1 text-xs font-semibold text-text-secondary transition-colors hover:text-text-primary"
      >
        <span className="flex items-center gap-2">
          {t("constraints.title")}
          {hasValues ? (
            <span className="rounded-full bg-secondary/15 px-2 py-0.5 text-[10px] font-medium text-secondary">
              active
            </span>
          ) : null}
        </span>
        <svg
          width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
          strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden
          className={`transition-transform duration-300 ${open ? "rotate-180" : ""}`}
        >
          <path d="m6 9 6 6 6-6" />
        </svg>
      </button>
      <div className={`constraints-expand ${open ? "open" : ""}`}>
        <div>
          <div className="grid gap-2 pb-3 pt-2 sm:grid-cols-3">
            <label className="flex flex-col gap-1 text-xs text-text-secondary">
              {t("constraints.productType")}
              <input
                type="text"
                value={brief.product_type ?? ""}
                onChange={(e) =>
                  onChange({ ...brief, product_type: e.target.value || undefined })
                }
                placeholder={t("constraints.productTypePlaceholder")}
                className="field"
              />
            </label>
            <label className="flex flex-col gap-1 text-xs text-text-secondary">
              {t("constraints.banned")}
              <input
                type="text"
                value={(brief.banned_ingredients ?? []).join(", ")}
                onChange={(e) =>
                  onChange({ ...brief, banned_ingredients: splitList(e.target.value) })
                }
                placeholder={t("constraints.bannedPlaceholder")}
                className="field"
              />
            </label>
            <label className="flex flex-col gap-1 text-xs text-text-secondary">
              {t("constraints.preferred")}
              <input
                type="text"
                value={(brief.preferred_ingredients ?? []).join(", ")}
                onChange={(e) =>
                  onChange({ ...brief, preferred_ingredients: splitList(e.target.value) })
                }
                placeholder={t("constraints.preferredPlaceholder")}
                className="field"
              />
            </label>
          </div>
        </div>
      </div>
    </section>
  );
}
