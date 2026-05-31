"use client";

import { FormEvent, KeyboardEvent } from "react";
import { AppColors } from "@/constants/AppColors";

interface ChatComposerProps {
  value: string;
  onChange: (nextValue: string) => void;
  onSubmit: () => void;
  disabled?: boolean;
  errorMessage?: string | null;
  onRetry?: () => void;
}

function SendIcon() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      <path d="M22 2 11 13" />
      <path d="M22 2l-7 20-4-9-9-4 20-7Z" />
    </svg>
  );
}

export function ChatComposer({
  value,
  onChange,
  onSubmit,
  disabled = false,
  errorMessage,
  onRetry,
}: ChatComposerProps) {
  const submitDisabled = disabled || !value.trim();

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (submitDisabled) {
      return;
    }
    onSubmit();
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      if (!submitDisabled) {
        onSubmit();
      }
    }
  };

  return (
    <div className="border-t border-border bg-surface p-3 lg:p-4">
      {errorMessage ? (
        <div className="mb-3 rounded-xl border border-error/30 bg-error/10 p-3 text-sm text-error">
          <div className="flex items-start justify-between gap-3">
            <p className="flex-1">{errorMessage}</p>
            {onRetry ? (
              <button
                type="button"
                onClick={onRetry}
                className="shrink-0 rounded-md border border-error/40 px-2.5 py-1 text-xs font-medium hover:bg-error/10"
              >
                Retry
              </button>
            ) : null}
          </div>
        </div>
      ) : null}
      <form onSubmit={handleSubmit}>
        <div className="flex items-end gap-2 rounded-2xl border border-border bg-surface px-3 py-2 transition focus-within:border-secondary/60 focus-within:ring-2 focus-within:ring-accent/30">
          <textarea
            value={value}
            onChange={(event) => onChange(event.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask for a formula, an ingredient comparison, or a process step…"
            rows={1}
            className="max-h-40 min-h-[40px] flex-1 resize-none border-0 bg-transparent py-2 text-sm text-text-primary outline-none placeholder:text-text-secondary"
            disabled={disabled}
          />
          <button
            type="submit"
            disabled={submitDisabled}
            aria-label="Send message"
            className="flex h-9 shrink-0 items-center gap-1.5 rounded-xl px-3 text-sm font-medium text-white shadow-sm transition disabled:cursor-not-allowed disabled:opacity-40"
            style={{
              background: submitDisabled ? AppColors.textSecondary : AppColors.buttonGradient,
            }}
          >
            <SendIcon />
            <span className="hidden sm:inline">Send</span>
          </button>
        </div>
        <p className="mt-2 px-1 text-[11px] text-text-secondary">
          Press <kbd className="rounded border border-border bg-background px-1 py-0.5 font-mono text-[10px]">Enter</kbd> to send,
          <span> </span>
          <kbd className="rounded border border-border bg-background px-1 py-0.5 font-mono text-[10px]">Shift</kbd>
          <span>+</span>
          <kbd className="rounded border border-border bg-background px-1 py-0.5 font-mono text-[10px]">Enter</kbd>
          <span> for a new line.</span>
        </p>
      </form>
    </div>
  );
}
