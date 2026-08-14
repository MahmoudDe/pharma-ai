import type { ReactNode } from "react";

interface ChatLayoutProps {
  rail: ReactNode;
  chat: ReactNode;
  worksheet: ReactNode;
}

export function ChatLayout({ rail, chat, worksheet }: ChatLayoutProps) {
  return (
    <div className="app-mesh-bg relative min-h-screen p-3 lg:p-6">
      <div className="relative z-10 mx-auto w-full max-w-[1720px]">
        <div className="flex flex-col gap-3 lg:grid lg:gap-5 lg:grid-cols-[4.5rem_minmax(0,1.55fr)_minmax(340px,1fr)]">
          {/* History rail */}
          <div className="animate-fade-in-down h-[3.25rem] lg:h-[calc(100vh-3rem)]">{rail}</div>

          {/* Conversation */}
          <section className="panel-solid animate-scale-in flex h-[calc(100vh-1.5rem)] min-h-0 flex-col overflow-hidden rounded-2xl lg:h-[calc(100vh-3rem)]">
            {chat}
          </section>

          {/* Worksheet */}
          <aside className="panel-solid animate-slide-in-right flex h-[calc(100vh-1.5rem)] min-h-0 flex-col overflow-hidden rounded-2xl lg:h-[calc(100vh-3rem)]">
            {worksheet}
          </aside>
        </div>
      </div>
    </div>
  );
}
