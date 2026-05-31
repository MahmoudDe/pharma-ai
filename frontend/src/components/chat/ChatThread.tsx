"use client";

import { useEffect, useMemo, useRef } from "react";
import Image from "next/image";
import { AppColors } from "@/constants/AppColors";
import type { ChatMessage } from "@/types/chat";

const LOGO_CONTAINER_CLASS = "flex items-center justify-center rounded-full";

interface ChatThreadProps {
  messages: ChatMessage[];
  isLoading: boolean;
  onSuggestionClick?: (suggestion: string) => void;
}

const EMPTY_STATE_SUGGESTIONS = [
  "Give me a basic sulfate-free shampoo formula.",
  "What surfactants are typical in a baby shampoo?",
  "Suggest a lightweight hand cream for oily skin.",
  "Compare cocamidopropyl betaine vs decyl glucoside.",
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
    <div className={`${LOGO_CONTAINER_CLASS} h-8 w-8 shrink-0`} aria-hidden>
      <Image
        src="/logo.png"
        alt=""
        width={24}
        height={24}
        className="h-5 w-5 object-contain"
      />
    </div>
  );
}

function TypingDots() {
  return (
    <span className="inline-flex items-center gap-1" aria-label="Assistant is typing">
      <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-secondary [animation-delay:-0.3s]" />
      <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-secondary [animation-delay:-0.15s]" />
      <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-secondary" />
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
    if (!containerRef.current) {
      return;
    }
    containerRef.current.scrollTop = containerRef.current.scrollHeight;
  }, [sortedMessages, isLoading]);

  if (!hasMessages) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-6 p-6 text-center">
        <div className="flex h-14 w-14 items-center justify-center rounded-2xl">
          <Image
            src="/logo.png"
            alt=""
            width={40}
            height={40}
            className="h-9 w-9 object-contain"
          />
        </div>
        <div>
          <h2 className="text-lg font-semibold text-text-primary">
            Ask about a cosmetic formulation
          </h2>
          <p className="mt-1 max-w-md text-sm text-text-secondary">
            Answers are grounded in the indexed formulation books and include page-level citations.
          </p>
        </div>
        {onSuggestionClick ? (
          <div className="grid w-full max-w-lg gap-2 sm:grid-cols-2">
            {EMPTY_STATE_SUGGESTIONS.map((suggestion) => (
              <button
                key={suggestion}
                type="button"
                onClick={() => onSuggestionClick(suggestion)}
                className="rounded-xl border border-border bg-surface px-4 py-3 text-left text-sm text-text-primary transition hover:border-secondary/60 hover:bg-secondary/5"
              >
                {suggestion}
              </button>
            ))}
          </div>
        ) : null}
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className="min-h-0 flex-1 overflow-y-auto bg-background/40 px-4 py-5 lg:px-6"
    >
      <div className="space-y-4">
        {sortedMessages.map((message) => {
          const isUser = message.role === "user";

          if (isUser) {
            return (
              <div key={message.id} className="flex justify-end">
                <div
                  className="max-w-[85%] rounded-2xl rounded-br-md px-4 py-3 text-sm text-white shadow-sm lg:max-w-[75%]"
                  style={{ background: AppColors.buttonGradient }}
                >
                  <p className="whitespace-pre-wrap">{message.content}</p>
                  <p className="mt-2 text-[11px] uppercase tracking-wide text-white/70">
                    {toLocalTime(message.createdAt)}
                  </p>
                </div>
              </div>
            );
          }

          return (
            <div key={message.id} className="flex justify-start gap-2">
              <AssistantAvatar />
              <div className="max-w-[85%] rounded-2xl rounded-bl-md border border-border bg-surface px-4 py-3 text-sm text-text-primary shadow-sm lg:max-w-[75%]">
                <p className="whitespace-pre-wrap">{message.content}</p>
                <p className="mt-2 text-[11px] uppercase tracking-wide text-text-secondary">
                  {toLocalTime(message.createdAt)}
                </p>
              </div>
            </div>
          );
        })}
        {isLoading ? (
          <div className="flex justify-start gap-2">
            <AssistantAvatar />
            <div className="flex items-center gap-2 rounded-2xl rounded-bl-md border border-border bg-surface px-4 py-3 text-sm text-text-secondary shadow-sm">
              <TypingDots />
              <span>Thinking…</span>
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}
