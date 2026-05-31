"use client";

import { useState } from "react";
import { t } from "@/lib/i18n";
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
  const [open, setOpen] = useState(false);

  return (
    <section className="border-b border-border bg-background px-4 py-2 lg:px-6">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between text-xs font-medium text-text-secondary"
      >
        {t("constraints.title")}
        <span className="text-text-primary">{open ? "−" : "+"}</span>
      </button>
      {open ? (
        <div className="mt-3 grid gap-2 sm:grid-cols-3">
          <label className="flex flex-col gap-1 text-xs text-text-secondary">
            {t("constraints.productType")}
            <input
              type="text"
              value={brief.product_type ?? ""}
              onChange={(e) =>
                onChange({ ...brief, product_type: e.target.value || undefined })
              }
              placeholder={t("constraints.productTypePlaceholder")}
              className="rounded-lg border border-border bg-surface px-2 py-1.5 text-sm text-text-primary"
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
              className="rounded-lg border border-border bg-surface px-2 py-1.5 text-sm text-text-primary"
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
              className="rounded-lg border border-border bg-surface px-2 py-1.5 text-sm text-text-primary"
            />
          </label>
        </div>
      ) : null}
    </section>
  );
}
