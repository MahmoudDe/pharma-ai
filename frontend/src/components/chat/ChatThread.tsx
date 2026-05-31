"use client";

import { useEffect, useMemo, useRef } from "react";
import Image from "next/image";
import { AppColors } from "@/constants/AppColors";
import { t } from "@/lib/i18n";
import type { ChatMessage } from "@/types/chat";

const SHOW_DEBUG = process.env.NEXT_PUBLIC_SHOW_DEBUG === "true";

interface ChatThreadProps {
  messages: ChatMessage[];
  isLoading: boolean;
  onSuggestionClick?: (suggestion: string) => void;
}

const EMPTY_STATE_SUGGESTIONS = [
  () => t("prompts.sulfateFree"),
  () => t("prompts.compareBaby"),
  () => t("prompts.capbVsSls"),
  () => t("prompts.handCream"),
];

function toLocalTime(isoValue: string) {
  const parsedDate = new Date(isoValue);
  if (Number.isNaN(parsedDate.valueOf())) {
    return "";
  }
  return parsedDate.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function AssistantAvatar() {
  return (
    <div
      className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl shadow-sm"
      style={{ background: AppColors.softGradient }}
      aria-hidden
    >
      <Image src="/logo.png" alt="" width={24} height={24} className="h-5 w-5 object-contain" />
    </div>
  );
}

function TypingDots() {
  return (
    <span className="inline-flex items-center gap-1.5" aria-label="Assistant is typing">
      <span className="h-2 w-2 animate-bounce rounded-full bg-secondary [animation-delay:-0.3s]" />
      <span className="h-2 w-2 animate-bounce rounded-full bg-accent [animation-delay:-0.15s]" />
      <span className="h-2 w-2 animate-bounce rounded-full bg-secondary" />
    </span>
  );
}

export function ChatThread({ messages, isLoading, onSuggestionClick }: ChatThreadProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const hasMessages = messages.length > 0;

  const sortedMessages = useMemo(
    () =>
      [...messages].sort(
        (a, b) => new Date(a.createdAt).valueOf() - new Date(b.createdAt).valueOf(),
      ),
    [messages],
  );

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
  }, [sortedMessages, isLoading]);

  if (!hasMessages) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-8 p-8 text-center">
        <div
          className="animate-float flex h-20 w-20 items-center justify-center rounded-3xl shadow-lg"
          style={{ background: AppColors.softGradient, boxShadow: "var(--shadow-glow)" }}
        >
          <Image src="/logo.png" alt="" width={48} height={48} className="h-11 w-11 object-contain" />
        </div>
        <div className="animate-fade-in-up max-w-md" style={{ animationDelay: "80ms" }}>
          <h2 className="text-xl font-bold tracking-tight text-text-primary">
            {t("chat.emptyTitle")}
          </h2>
          <p className="mt-2 text-sm leading-relaxed text-text-secondary">
            {t("chat.emptySubtitle")}
          </p>
        </div>
        {onSuggestionClick ? (
          <div className="stagger-children grid w-full max-w-xl gap-3 sm:grid-cols-2">
            {EMPTY_STATE_SUGGESTIONS.map((labelFn) => {
              const suggestion = labelFn();
              return (
                <button
                  key={suggestion}
                  type="button"
                  onClick={() => onSuggestionClick(suggestion)}
                  className="hover-lift group rounded-2xl border border-border/80 bg-surface/90 px-4 py-3.5 text-left text-sm text-text-primary"
                >
                  <span className="mb-1 block text-[10px] font-semibold uppercase tracking-wider text-secondary opacity-80">
                    {t("chat.tryPrompt")}
                  </span>
                  {suggestion}
                </button>
              );
            })}
          </div>
        ) : null}
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className="min-h-0 flex-1 overflow-y-auto scroll-smooth px-4 py-6 lg:px-6"
    >
      <div className="mx-auto max-w-3xl space-y-5">
        {sortedMessages.map((message) => {
          const isUser = message.role === "user";

          if (isUser) {
            return (
              <div key={message.id} className="message-enter-user flex justify-end">
                <div
                  className="max-w-[88%] rounded-2xl rounded-br-sm px-4 py-3 text-sm text-white shadow-md lg:max-w-[78%]"
                  style={{ background: AppColors.buttonGradient }}
                >
                  <p className="whitespace-pre-wrap leading-relaxed">{message.content}</p>
                  <p className="mt-2 text-[10px] font-medium uppercase tracking-wider text-white/60">
                    {toLocalTime(message.createdAt)}
                  </p>
                </div>
              </div>
            );
          }

          return (
            <div key={message.id} className="message-enter-assistant flex justify-start gap-3">
              <AssistantAvatar />
              <div className="max-w-[88%] rounded-2xl rounded-bl-sm border border-border/80 bg-surface/95 px-4 py-3 text-sm text-text-primary shadow-sm backdrop-blur-sm lg:max-w-[78%]">
                <p className="whitespace-pre-wrap leading-relaxed">{message.content}</p>
                {SHOW_DEBUG && message.route ? (
                  <p className="mt-2 rounded-lg bg-background/80 px-2 py-1 font-mono text-[10px] text-text-secondary">
                    route={message.route} · llm={String(message.llmUsed)} · conf=
                    {message.searchConfidence ?? "—"}
                  </p>
                ) : null}
                <p className="mt-2 text-[10px] font-medium uppercase tracking-wider text-text-secondary">
                  {toLocalTime(message.createdAt)}
                </p>
              </div>
            </div>
          );
        })}
        {isLoading ? (
          <div className="animate-fade-in flex justify-start gap-3">
            <AssistantAvatar />
            <div className="flex items-center gap-3 rounded-2xl rounded-bl-sm border border-border/80 bg-surface/95 px-4 py-3 text-sm text-text-secondary shadow-sm">
              <TypingDots />
              <span className="font-medium">{t("chat.thinking")}</span>
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}
