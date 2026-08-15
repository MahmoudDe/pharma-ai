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
        <div className="flex flex-col gap-3 lg:grid lg:h-[calc(100vh-3rem)] lg:min-h-0 lg:grid-cols-[4.5rem_minmax(0,1.55fr)_minmax(340px,1fr)] lg:gap-5">
          {/* History rail — opacity-only enter so transform does not clip overflow children */}
          <div className="animate-fade-in h-[3.25rem] min-h-0 lg:h-full">{rail}</div>

          {/* Conversation */}
          <section className="panel-solid animate-fade-in flex h-[min(100dvh-1.5rem,52rem)] min-h-0 flex-col overflow-hidden rounded-2xl lg:h-full">
            {chat}
          </section>

          {/* Worksheet — height locked on desktop so accordion sections scroll inside */}
          <aside className="panel-solid animate-fade-in flex max-h-[70dvh] min-h-[22rem] flex-col overflow-hidden rounded-2xl lg:h-full lg:max-h-none lg:min-h-0">
            {worksheet}
          </aside>
        </div>
      </div>
    </div>
  );
}
