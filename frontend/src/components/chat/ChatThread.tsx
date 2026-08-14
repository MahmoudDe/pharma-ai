"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useLocale } from "@/components/i18n/LocaleProvider";
import { Logo } from "@/components/ui/Logo";
import type { TranslationKey } from "@/lib/i18n";
import type { ChatMessage } from "@/types/chat";
import { MessageContent } from "@/components/chat/MessageContent";

const SHOW_DEBUG = process.env.NEXT_PUBLIC_SHOW_DEBUG === "true";

interface ChatThreadProps {
  messages: ChatMessage[];
  isLoading: boolean;
  /** Id of the assistant message currently being streamed, if any. */
  streamingMessageId?: string | null;
  onSuggestionClick?: (suggestion: string) => void;
  onFeedback?: (messageId: string, rating: 1 | -1, userMessage?: string) => void;
}

const EMPTY_STATE_KEYS: TranslationKey[] = [
  "prompts.sulfateFree",
  "prompts.compareBaby",
  "prompts.capbVsSls",
  "prompts.handCream",
];

function toLocalTime(isoValue: string) {
  const parsedDate = new Date(isoValue);
  if (Number.isNaN(parsedDate.valueOf())) {
    return "";
  }
  return parsedDate.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function AssistantAvatar({ active = false }: { active?: boolean }) {
  return <Logo size="sm" alt="" active={active} className="shrink-0 self-start" />;
}

function TypingDots() {
  return (
    <span className="inline-flex items-center gap-1.5" aria-label="Assistant is typing">
      <span className="typing-dot h-2 w-2 rounded-full bg-secondary [animation-delay:-0.32s]" />
      <span className="typing-dot h-2 w-2 rounded-full bg-accent [animation-delay:-0.16s]" />
      <span className="typing-dot h-2 w-2 rounded-full bg-secondary" />
    </span>
  );
}

function CopyButton({ text }: { text: string }) {
  const { t } = useLocale();
  const [copied, setCopied] = useState(false);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(
    () => () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    },
    [],
  );

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
      timeoutRef.current = setTimeout(() => setCopied(false), 1600);
    } catch {
      /* clipboard unavailable — silently ignore */
    }
  };

  return (
    <button
      type="button"
      onClick={handleCopy}
      aria-label={copied ? t("chat.copied") : t("chat.copy")}
      className="copy-chip absolute -top-2.5 end-2 inline-flex items-center gap-1 rounded-full border border-border bg-surface px-2 py-1 text-[10px] font-semibold text-text-secondary shadow-sm"
    >
      {copied ? (
        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round">
          <path d="M20 6 9 17l-5-5" />
        </svg>
      ) : (
        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
          <rect x="9" y="9" width="13" height="13" rx="2" />
          <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
        </svg>
      )}
      <span>{copied ? t("chat.copied") : t("chat.copy")}</span>
    </button>
  );
}

export function ChatThread({
  messages,
  isLoading,
  streamingMessageId = null,
  onSuggestionClick,
  onFeedback,
}: ChatThreadProps) {
  const { t } = useLocale();
  const containerRef = useRef<HTMLDivElement>(null);
  const pinnedRef = useRef(true);
  const [showJump, setShowJump] = useState(false);
  const hasMessages = messages.length > 0;

  const sortedMessages = useMemo(
    () =>
      [...messages].sort(
        (a, b) => new Date(a.createdAt).valueOf() - new Date(b.createdAt).valueOf(),
      ),
    [messages],
  );

  const streamingId = streamingMessageId;

  const scrollToBottom = useCallback((behavior: ScrollBehavior = "smooth") => {
    const el = containerRef.current;
    if (!el) return;
    el.scrollTo({ top: el.scrollHeight, behavior });
    pinnedRef.current = true;
    setShowJump(false);
  }, []);

  // Track whether the viewer is pinned to the bottom so streaming never yanks
  // them away while they're reading earlier messages.
  const handleScroll = useCallback(() => {
    const el = containerRef.current;
    if (!el) return;
    const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    const pinned = distanceFromBottom < 120;
    pinnedRef.current = pinned;
    setShowJump(!pinned);
  }, []);

  // Auto-follow new content only while pinned to the bottom.
  useEffect(() => {
    if (pinnedRef.current) {
      scrollToBottom("smooth");
    }
  }, [sortedMessages, isLoading, scrollToBottom]);

  if (!hasMessages) {
    return (
      <div className="flex h-full min-h-0 flex-1 flex-col items-center justify-center gap-8 p-8 text-center">
        <div className="animate-float relative">
          <span
            aria-hidden
            className="absolute inset-0 -z-10 scale-150 rounded-full opacity-70 blur-2xl"
            style={{ background: "var(--brand-gradient-soft)" }}
          />
          <Logo size="lg" alt="" ring />
        </div>
        <div className="animate-fade-in-up max-w-md" style={{ animationDelay: "80ms" }}>
          <h2 className="text-2xl font-bold tracking-tight text-text-primary">
            {t("chat.emptyTitle")}
          </h2>
          <p className="mt-2.5 text-sm leading-relaxed text-text-secondary">
            {t("chat.emptySubtitle")}
          </p>
        </div>
        {onSuggestionClick ? (
          <div className="stagger-children grid w-full max-w-xl gap-3 sm:grid-cols-2">
            {EMPTY_STATE_KEYS.map((key) => {
              const suggestion = t(key);
              return (
                <button
                  key={key}
                  type="button"
                  onClick={() => onSuggestionClick(suggestion)}
                  className="hover-lift group flex items-start gap-3 rounded-2xl border border-border bg-surface px-4 py-3.5 text-start text-sm text-text-primary shadow-sm"
                >
                  <span
                    aria-hidden
                    className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-lg text-secondary transition-colors group-hover:text-white"
                    style={{ background: "color-mix(in srgb, var(--secondary) 12%, transparent)" }}
                  >
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="m9 18 6-6-6-6" />
                    </svg>
                  </span>
                  <span className="flex-1">
                    <span className="mb-1 block text-[10px] font-semibold uppercase tracking-wider text-text-tertiary">
                      {t("chat.tryPrompt")}
                    </span>
                    {suggestion}
                  </span>
                </button>
              );
            })}
          </div>
        ) : null}
      </div>
    );
  }

  return (
    <div className="relative min-h-0 flex-1">
      <div
        ref={containerRef}
        onScroll={handleScroll}
        className="h-full overflow-y-auto px-4 py-6 lg:px-6"
        role="log"
        aria-live="polite"
      >
        <div className="mx-auto max-w-3xl space-y-5">
          {sortedMessages.map((message, index) => {
            const isUser = message.role === "user";
            const priorUser =
              !isUser
                ? [...sortedMessages.slice(0, index)].reverse().find((m) => m.role === "user")
                : null;

            if (isUser) {
              return (
                <div key={message.id} className="message-enter-user flex justify-end">
                  <div
                    className="max-w-[88%] rounded-2xl rounded-ee-md px-4 py-3 text-sm text-white shadow-[0_8px_24px_-8px_rgba(124,74,220,0.5)] lg:max-w-[78%]"
                    style={{ background: "var(--brand-gradient-vivid)" }}
                  >
                    <p className="whitespace-pre-wrap leading-relaxed">{message.content}</p>
                    <p className="mt-2 text-[10px] font-medium uppercase tracking-wider text-white/65">
                      {toLocalTime(message.createdAt)}
                    </p>
                  </div>
                </div>
              );
            }

            const isStreaming = message.id === streamingId;
            const hasContent = message.content.length > 0;

            // Empty assistant placeholder while waiting for the first token.
            if (!hasContent && isStreaming) {
              return (
                <div key={message.id} className="animate-fade-in flex justify-start gap-3">
                  <AssistantAvatar active />
                  <div className="flex items-center gap-3 rounded-2xl rounded-es-sm border border-border bg-surface px-4 py-3 text-sm text-text-secondary shadow-sm">
                    <TypingDots />
                    <span className="shimmer-text font-medium">{t("chat.thinking")}</span>
                  </div>
                </div>
              );
            }

            return (
              <div key={message.id} className="message-enter-assistant flex justify-start gap-3">
                <AssistantAvatar active={isStreaming} />
                <div className="group relative max-w-[88%] rounded-2xl rounded-es-md border border-border bg-surface px-4 py-3 text-sm text-text-primary shadow-sm lg:max-w-[78%]">
                  {!isStreaming && hasContent ? <CopyButton text={message.content} /> : null}
                  <MessageContent content={message.content} />
                  {isStreaming ? <span aria-hidden className="stream-caret" /> : null}
                  {SHOW_DEBUG && message.route ? (
                    <p className="mt-2 rounded-lg bg-background/80 px-2 py-1 font-mono text-[10px] text-text-secondary">
                      route={message.route} · llm={String(message.llmUsed)} · conf=
                      {message.searchConfidence ?? "—"}
                    </p>
                  ) : null}
                  {!isStreaming ? (
                    <p className="mt-2 text-[10px] font-medium uppercase tracking-wider text-text-secondary">
                      {toLocalTime(message.createdAt)}
                    </p>
                  ) : null}
                  {!isStreaming && onFeedback ? (
                    <div className="mt-2 flex items-center gap-2">
                      <button
                        type="button"
                        aria-label={t("chat.feedbackUp")}
                        onClick={() => onFeedback(message.id, 1, priorUser?.content)}
                        className={`rounded-md border px-2 py-1 text-[10px] font-semibold ${
                          message.feedback_rating === 1
                            ? "border-success/40 bg-success/10 text-success"
                            : "border-border text-text-secondary hover:bg-secondary/10"
                        }`}
                      >
                        {t("chat.feedbackUp")}
                      </button>
                      <button
                        type="button"
                        aria-label={t("chat.feedbackDown")}
                        onClick={() => onFeedback(message.id, -1, priorUser?.content)}
                        className={`rounded-md border px-2 py-1 text-[10px] font-semibold ${
                          message.feedback_rating === -1
                            ? "border-error/40 bg-error/10 text-error"
                            : "border-border text-text-secondary hover:bg-secondary/10"
                        }`}
                      >
                        {t("chat.feedbackDown")}
                      </button>
                    </div>
                  ) : null}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <button
        type="button"
        onClick={() => scrollToBottom("smooth")}
        aria-label={t("chat.jumpToLatest")}
        className={`jump-latest absolute bottom-4 left-1/2 inline-flex -translate-x-1/2 items-center gap-1.5 rounded-full border border-border bg-surface px-3.5 py-2 text-xs font-semibold text-text-primary shadow-soft${showJump ? " jump-latest--visible" : ""}`}
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
          <path d="M12 5v14M19 12l-7 7-7-7" />
        </svg>
        {t("chat.jumpToLatest")}
      </button>
    </div>
  );
}
