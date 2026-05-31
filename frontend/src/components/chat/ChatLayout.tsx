import type { ReactNode } from "react";

interface ChatLayoutProps {
  historyPanel?: ReactNode;
  leftPanel: ReactNode;
  rightPanel: ReactNode;
}

export function ChatLayout({ historyPanel, leftPanel, rightPanel }: ChatLayoutProps) {
  const hasHistory = Boolean(historyPanel);

  return (
    <div className="app-mesh-bg relative min-h-screen p-3 lg:p-6">
      <div className="relative z-10 mx-auto grid w-full max-w-[1680px] grid-cols-1 gap-4 lg:gap-5">
        <div
          className={`grid grid-cols-1 gap-4 lg:gap-5 ${
            hasHistory
              ? "lg:grid-cols-[minmax(240px,280px)_minmax(0,1.35fr)_minmax(340px,1fr)]"
              : "lg:grid-cols-[minmax(0,1.6fr)_minmax(360px,1fr)]"
          }`}
        >
          {hasHistory ? (
            <section className="panel-solid animate-slide-in-left hidden h-[calc(100vh-1.5rem)] overflow-hidden rounded-2xl lg:flex lg:h-[calc(100vh-3rem)] lg:flex-col">
              {historyPanel}
            </section>
          ) : null}
          <section className="panel-solid animate-scale-in flex h-[calc(100vh-1.5rem)] min-h-0 flex-col overflow-hidden rounded-2xl lg:h-[calc(100vh-3rem)]">
            {leftPanel}
          </section>
          <aside className="panel-solid animate-slide-in-right flex h-[calc(100vh-1.5rem)] min-h-0 flex-col overflow-hidden rounded-2xl lg:h-[calc(100vh-3rem)]">
            {rightPanel}
          </aside>
        </div>
      </div>
    </div>
  );
}
