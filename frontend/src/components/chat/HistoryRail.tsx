"use client";

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { ChatHistorySidebar } from "@/components/chat/ChatHistorySidebar";
import { useLocale } from "@/components/i18n/LocaleProvider";
import type { ChatThreadSummary } from "@/types/chat";

interface HistoryRailProps {
  threads: ChatThreadSummary[];
  activeThreadId: string | null;
  isLoadingThreads: boolean;
  onSelectThread: (threadId: string) => void;
  onNewChat: () => void;
  onDeleteThread?: (threadId: string) => void;
  onRenameThread?: (threadId: string, title: string) => void;
}

function initialOf(title: string): string {
  const trimmed = title.trim();
  if (!trimmed) return "#";
  const ch = [...trimmed][0];
  return ch.toUpperCase();
}

export function HistoryRail(props: HistoryRailProps) {
  const { threads, activeThreadId, onSelectThread, onNewChat } = props;
  const { t } = useLocale();
  const [expanded, setExpanded] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => setMounted(true), []);

  const close = () => setExpanded(false);

  useEffect(() => {
    if (!expanded) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setExpanded(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [expanded]);

  return (
    <div className="relative h-full">
      {/* Slim rail — horizontal on mobile, vertical column on lg+ */}
      <div className="panel-solid flex h-full items-center gap-2 overflow-hidden rounded-2xl p-2 lg:flex-col lg:items-stretch lg:py-3">
        <button
          type="button"
          onClick={onNewChat}
          title={t("thread.newChat")}
          aria-label={t("thread.newChat")}
          className="btn-primary flex h-11 w-11 shrink-0 items-center justify-center rounded-xl lg:mx-auto"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
            <path d="M12 5v14M5 12h14" />
          </svg>
        </button>

        <div className="my-0 hidden h-px w-full bg-border lg:block" />

        {/* Thread chips */}
        <div className="flex min-w-0 flex-1 items-center gap-2 overflow-x-auto lg:flex-col lg:overflow-y-auto lg:overflow-x-hidden">
          {threads.slice(0, 12).map((thread) => {
            const isActive = thread.id === activeThreadId;
            return (
              <button
                key={thread.id}
                type="button"
                onClick={() => onSelectThread(thread.id)}
                title={thread.title}
                aria-label={thread.title}
                aria-current={isActive ? "true" : undefined}
                className={`relative flex h-10 w-10 shrink-0 items-center justify-center rounded-xl text-sm font-bold transition-all duration-300 lg:mx-auto ${
                  isActive
                    ? "text-white shadow-[var(--shadow-glow)]"
                    : "border border-border bg-surface-sunken text-text-secondary hover:border-secondary/40 hover:text-secondary"
                }`}
                style={isActive ? { background: "var(--brand-gradient-vivid)" } : undefined}
              >
                {isActive ? (
                  <span
                    aria-hidden
                    className="absolute -start-2 top-1/2 h-5 w-1 -translate-y-1/2 rounded-e-full lg:start-1/2 lg:top-auto lg:-bottom-2 lg:h-1 lg:w-5 lg:-translate-x-1/2 lg:translate-y-0"
                    style={{ background: "var(--brand-gradient-vivid)" }}
                  />
                ) : null}
                {initialOf(thread.title)}
              </button>
            );
          })}
        </div>

        <div className="hidden h-px w-full bg-border lg:block" />

        <button
          type="button"
          onClick={() => setExpanded(true)}
          title={t("history.expand")}
          aria-label={t("history.expand")}
          className="btn-ghost flex h-10 w-10 shrink-0 items-center justify-center rounded-xl lg:mx-auto"
        >
          <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
            <path d="M3 6h18M3 12h18M3 18h18" />
          </svg>
        </button>
      </div>

      {/* Expanded overlay — portaled to body so `fixed` resolves against the
          viewport (ancestor cells in ChatLayout carry animation transforms,
          which would otherwise become the containing block). */}
      {mounted && expanded
        ? createPortal(
            <div className="fixed inset-0 z-[100]">
              <button
                type="button"
                aria-label={t("history.collapse")}
                onClick={close}
                className="animate-fade-in absolute inset-0 bg-[rgba(5,7,15,0.45)] backdrop-blur-sm"
              />
              <div className="animate-slide-in-left panel-solid absolute inset-y-0 start-0 m-3 flex w-[280px] max-w-[80vw] flex-col overflow-hidden rounded-2xl shadow-[var(--shadow-panel)] lg:m-6">
                <ChatHistorySidebar
                  {...props}
                  onSelectThread={(id) => {
                    onSelectThread(id);
                    close();
                  }}
                  onNewChat={() => {
                    onNewChat();
                    close();
                  }}
                />
                <button
                  type="button"
                  onClick={close}
                  aria-label={t("history.collapse")}
                  className="absolute end-2 top-2 flex h-8 w-8 items-center justify-center rounded-lg text-text-secondary transition hover:bg-surface-sunken hover:text-text-primary"
                >
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                    <path d="M18 6 6 18M6 6l12 12" />
                  </svg>
                </button>
              </div>
            </div>,
            document.body,
          )
        : null}
    </div>
  );
}
