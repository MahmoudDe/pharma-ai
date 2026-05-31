import type { ReactNode } from "react";

interface ChatLayoutProps {
  historyPanel?: ReactNode;
  leftPanel: ReactNode;
  rightPanel: ReactNode;
}

export function ChatLayout({ historyPanel, leftPanel, rightPanel }: ChatLayoutProps) {
  const hasHistory = Boolean(historyPanel);

  return (
    <div className="min-h-screen bg-background p-3 lg:p-6">
      <div
        className={`mx-auto grid w-full max-w-[1600px] grid-cols-1 gap-4 lg:gap-6 ${
          hasHistory
            ? "lg:grid-cols-[minmax(220px,260px)_minmax(0,2fr)_minmax(360px,1fr)]"
            : "lg:grid-cols-[minmax(0,2fr)_minmax(360px,1fr)]"
        }`}
      >
        {hasHistory ? (
          <section className="hidden h-[calc(100vh-1.5rem)] overflow-hidden rounded-2xl border border-border bg-surface shadow-[0_8px_24px_rgba(15,23,42,0.06)] lg:flex lg:h-[calc(100vh-3rem)] lg:flex-col">
            {historyPanel}
          </section>
        ) : null}
        <section className="flex h-[calc(100vh-1.5rem)] flex-col overflow-hidden rounded-2xl border border-border bg-surface shadow-[0_8px_24px_rgba(15,23,42,0.06)] lg:h-[calc(100vh-3rem)]">
          {leftPanel}
        </section>
        <aside className="flex h-[calc(100vh-1.5rem)] flex-col overflow-hidden rounded-2xl border border-border bg-surface shadow-[0_8px_24px_rgba(15,23,42,0.06)] lg:h-[calc(100vh-3rem)]">
          {rightPanel}
        </aside>
      </div>
    </div>
  );
}
