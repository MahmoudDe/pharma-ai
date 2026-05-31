"use client";

import { AppColors } from "@/constants/AppColors";
import { useLocale } from "@/components/i18n/LocaleProvider";
import type { ChatThreadSummary } from "@/types/chat";

interface ChatHistorySidebarProps {
  threads: ChatThreadSummary[];
  activeThreadId: string | null;
  isLoadingThreads: boolean;
  onSelectThread: (threadId: string) => void;
  onNewChat: () => void;
  onDeleteThread?: (threadId: string) => void;
  onRenameThread?: (threadId: string, title: string) => void;
}

function formatRelativeTime(iso: string | null): string {
  if (!iso) return "";
  const date = new Date(iso);
  const diffMins = Math.floor((Date.now() - date.getTime()) / 60000);
  if (diffMins < 1) return "Just now";
  if (diffMins < 60) return `${diffMins}m`;
  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}h`;
  const diffDays = Math.floor(diffHours / 24);
  if (diffDays < 7) return `${diffDays}d`;
  return date.toLocaleDateString();
}

export function ChatHistorySidebar({
  threads,
  activeThreadId,
  isLoadingThreads,
  onSelectThread,
  onNewChat,
  onDeleteThread,
  onRenameThread,
}: ChatHistorySidebarProps) {
  const { t } = useLocale();

  return (
    <aside className="flex h-full min-h-0 w-full flex-col">
      <div className="border-b border-border/60 px-4 py-4">
        <h2 className="text-sm font-bold text-text-primary">{t("history.title")}</h2>
        <p className="text-xs text-text-secondary">{t("history.subtitle")}</p>
      </div>
      <button
        type="button"
        onClick={onNewChat}
        className="btn-primary mx-3 mb-3 mt-3 rounded-xl px-4 py-2.5 text-sm font-semibold text-white shadow-md"
        style={{ background: AppColors.buttonGradient }}
      >
        + {t("thread.newChat")}
      </button>
      <div className="min-h-0 flex-1 overflow-y-auto px-2 pb-4">
        {isLoadingThreads ? (
          <p className="animate-pulse px-3 py-2 text-xs text-text-secondary">
            {t("history.loading")}
          </p>
        ) : threads.length === 0 ? (
          <p className="px-3 py-2 text-xs text-text-secondary">{t("history.empty")}</p>
        ) : (
          <ul className="space-y-1.5">
            {threads.map((thread, index) => {
              const isActive = thread.id === activeThreadId;
              return (
                <li
                  key={thread.id}
                  className="group relative animate-fade-in-up"
                  style={{ animationDelay: `${Math.min(index, 8) * 40}ms` }}
                >
                  <button
                    type="button"
                    onClick={() => onSelectThread(thread.id)}
                    className={`w-full rounded-xl px-3 py-3 pr-14 text-left transition-all duration-300 ${
                      isActive
                        ? "border border-secondary/40 bg-background shadow-md"
                        : "border border-transparent hover:border-border/60 hover:bg-background/70"
                    }`}
                    style={
                      isActive
                        ? {
                            boxShadow: "var(--shadow-glow)",
                          }
                        : undefined
                    }
                  >
                    {isActive ? (
                      <span
                        className="absolute left-0 top-3 bottom-3 w-1 rounded-r-full"
                        style={{ background: AppColors.buttonGradient }}
                      />
                    ) : null}
                    <p className="truncate text-sm font-semibold text-text-primary">
                      {thread.title}
                    </p>
                    {thread.preview ? (
                      <p className="mt-0.5 truncate text-xs text-text-secondary">
                        {thread.preview}
                      </p>
                    ) : null}
                    <p className="mt-1.5 text-[10px] font-medium text-text-secondary/80">
                      {formatRelativeTime(thread.updated_at)}
                    </p>
                  </button>
                  <div className="absolute right-2 top-2.5 flex gap-0.5 opacity-0 transition-opacity duration-200 group-hover:opacity-100">
                    {onRenameThread ? (
                      <button
                        type="button"
                        title={t("thread.rename")}
                        className="rounded-lg px-1.5 py-1 text-[10px] text-text-secondary transition hover:bg-background hover:text-secondary"
                        onClick={(e) => {
                          e.stopPropagation();
                          const next = window.prompt("Thread title", thread.title);
                          if (next?.trim()) onRenameThread(thread.id, next.trim());
                        }}
                      >
                        ✎
                      </button>
                    ) : null}
                    {onDeleteThread ? (
                      <button
                        type="button"
                        title={t("thread.delete")}
                        className="rounded-lg px-1.5 py-1 text-[10px] text-error transition hover:bg-error/10"
                        onClick={(e) => {
                          e.stopPropagation();
                          if (window.confirm(t("thread.deleteConfirm"))) {
                            onDeleteThread(thread.id);
                          }
                        }}
                      >
                        ×
                      </button>
                    ) : null}
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </aside>
  );
}
