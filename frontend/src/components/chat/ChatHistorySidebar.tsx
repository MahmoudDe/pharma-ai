"use client";

import { AppColors } from "@/constants/AppColors";
import { t } from "@/lib/i18n";
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
  if (!iso) {
    return "";
  }
  const date = new Date(iso);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  if (diffMins < 1) {
    return "Just now";
  }
  if (diffMins < 60) {
    return `${diffMins}m ago`;
  }
  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) {
    return `${diffHours}h ago`;
  }
  const diffDays = Math.floor(diffHours / 24);
  if (diffDays < 7) {
    return `${diffDays}d ago`;
  }
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
  return (
    <aside className="flex h-full min-h-0 w-full flex-col border-r border-border bg-surface">
      <SidebarHeader />
      <button
        type="button"
        onClick={onNewChat}
        className="mx-3 mb-3 rounded-xl px-3 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:opacity-95"
        style={{ background: AppColors.buttonGradient }}
      >
        {t("thread.newChat")}
      </button>
      <div className="min-h-0 flex-1 overflow-y-auto px-2 pb-3">
        {isLoadingThreads ? (
          <p className="px-2 py-2 text-xs text-text-secondary">Loading history…</p>
        ) : threads.length === 0 ? (
          <p className="px-2 py-2 text-xs text-text-secondary">No past chats yet.</p>
        ) : (
          <ul className="space-y-1">
            {threads.map((thread) => {
              const isActive = thread.id === activeThreadId;
              return (
                <li key={thread.id} className="group relative">
                  <button
                    type="button"
                    onClick={() => onSelectThread(thread.id)}
                    className={`w-full rounded-lg px-3 py-2.5 pr-16 text-left transition ${
                      isActive
                        ? "border border-border bg-background shadow-sm"
                        : "hover:bg-background/80"
                    }`}
                    style={
                      isActive
                        ? {
                            borderColor: AppColors.secondary,
                            boxShadow: `0 0 0 1px ${AppColors.secondary}22`,
                          }
                        : undefined
                    }
                  >
                    <p
                      className={`truncate text-sm font-medium ${
                        isActive ? "text-text-primary" : "text-text-primary/90"
                      }`}
                    >
                      {thread.title}
                    </p>
                    {thread.preview ? (
                      <p className="mt-0.5 truncate text-xs text-text-secondary">{thread.preview}</p>
                    ) : null}
                    <p className="mt-1 text-[10px] text-text-secondary">
                      {formatRelativeTime(thread.updated_at)}
                    </p>
                  </button>
                  <div className="absolute right-1 top-2 flex gap-0.5 opacity-0 transition group-hover:opacity-100">
                    {onRenameThread ? (
                      <button
                        type="button"
                        title={t("thread.rename")}
                        className="rounded px-1.5 py-0.5 text-[10px] text-text-secondary hover:bg-background"
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
                        className="rounded px-1.5 py-0.5 text-[10px] text-error hover:bg-background"
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

function SidebarHeader() {
  return (
    <div className="border-b border-border px-4 py-3">
      <h2 className="text-sm font-semibold text-text-primary">History</h2>
      <p className="text-xs text-text-secondary">Past conversations</p>
    </div>
  );
}
