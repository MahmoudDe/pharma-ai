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
  if (actions.length === 0) {
    return null;
  }

  return (
    <section className="rounded-xl border border-border bg-background p-4">
      <h2 className="text-sm font-semibold text-text-primary">Suggested next steps</h2>
      <div className="mt-3 flex flex-col gap-2">
        {actions.map((action, index) => (
          <button
            key={`${action.type}-${index}`}
            type="button"
            onClick={() => onActionClick(action)}
            className="group flex items-center justify-between gap-3 rounded-lg border border-border bg-surface px-3 py-2.5 text-left text-sm text-text-primary shadow-sm transition hover:border-secondary/60 hover:bg-secondary/5"
          >
            <span className="font-medium">{action.label}</span>
            <span className="text-text-secondary transition group-hover:translate-x-0.5 group-hover:text-secondary">
              <ArrowIcon />
            </span>
          </button>
        ))}
      </div>
    </section>
  );
}
