"use client";

import { useLocale } from "@/components/i18n/LocaleProvider";
import type { SuggestedNextAction } from "@/types/chat";

interface SuggestedActionsPanelProps {
  actions: SuggestedNextAction[];
  onActionClick: (action: SuggestedNextAction) => void;
}

function ArrowIcon() {
  return (
    <svg
      width="14"
      height="14"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      <path d="M5 12h14" />
      <path d="m12 5 7 7-7 7" />
    </svg>
  );
}

export function SuggestedActionsPanel({ actions, onActionClick }: SuggestedActionsPanelProps) {
  const { t } = useLocale();

  if (actions.length === 0) {
    return null;
  }

  return (
    <section className="animate-fade-in-up rounded-2xl border border-border bg-surface p-4 shadow-sm">
      <h2 className="text-sm font-bold text-text-primary">{t("actions.title")}</h2>
      <div className="mt-3 flex flex-col gap-2">
        {actions.map((action, index) => (
          <button
            key={`${action.type}-${index}`}
            type="button"
            onClick={() => onActionClick(action)}
            className="hover-lift group flex items-center justify-between gap-3 rounded-xl border border-border bg-[var(--panel-muted)] px-3 py-2.5 text-start text-sm text-text-primary"
            style={{ animationDelay: `${index * 50}ms` }}
          >
            <span className="font-medium">{action.label}</span>
            <span className="text-text-secondary transition-transform duration-300 group-hover:translate-x-1 group-hover:text-secondary">
              <ArrowIcon />
            </span>
          </button>
        ))}
      </div>
    </section>
  );
}
