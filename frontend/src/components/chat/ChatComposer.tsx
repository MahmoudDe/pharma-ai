"use client";

import { FormEvent, KeyboardEvent } from "react";
import { AppColors } from "@/constants/AppColors";
import { t } from "@/lib/i18n";

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
    if (submitDisabled) return;
    onSubmit();
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      if (!submitDisabled) onSubmit();
    }
  };

  return (
    <div className="relative z-10 border-t border-border/60 bg-surface/80 p-3 backdrop-blur-md lg:p-4">
      {errorMessage ? (
        <div className="animate-fade-in-down mb-3 rounded-2xl border border-error/30 bg-error/10 p-3 text-sm text-error">
          <div className="flex items-start justify-between gap-3">
            <p className="flex-1">{errorMessage}</p>
            {onRetry ? (
              <button
                type="button"
                onClick={onRetry}
                className="shrink-0 rounded-lg border border-error/40 px-3 py-1 text-xs font-semibold transition hover:bg-error/15"
              >
                {t("composer.retry")}
              </button>
            ) : null}
          </div>
        </div>
      ) : null}
      <form onSubmit={handleSubmit}>
        <div className="flex items-end gap-2 rounded-2xl border border-border/80 bg-background/60 px-3 py-2 shadow-sm transition-all duration-300 focus-within:border-secondary/50 focus-within:shadow-[var(--shadow-glow)] focus-within:ring-2 focus-within:ring-accent/20">
          <textarea
            value={value}
            onChange={(event) => onChange(event.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={t("composer.placeholder")}
            rows={1}
            className="max-h-40 min-h-[44px] flex-1 resize-none border-0 bg-transparent py-2.5 text-sm leading-relaxed text-text-primary outline-none placeholder:text-text-secondary"
            disabled={disabled}
          />
          <button
            type="submit"
            disabled={submitDisabled}
            aria-label={t("composer.send")}
            className="btn-primary flex h-10 shrink-0 items-center gap-1.5 rounded-xl px-4 text-sm font-semibold text-white shadow-md disabled:cursor-not-allowed disabled:opacity-40"
            style={{
              background: submitDisabled ? AppColors.textSecondary : AppColors.buttonGradient,
            }}
          >
            <SendIcon />
            <span className="hidden sm:inline">{t("composer.send")}</span>
          </button>
        </div>
        <p className="mt-2 px-1 text-[11px] text-text-secondary">
          <kbd className="rounded-md border border-border bg-surface px-1.5 py-0.5 font-mono text-[10px]">
            Enter
          </kbd>
          <span> send · </span>
          <kbd className="rounded-md border border-border bg-surface px-1.5 py-0.5 font-mono text-[10px]">
            Shift+Enter
          </kbd>
          <span> new line</span>
        </p>
      </form>
    </div>
  );
}
