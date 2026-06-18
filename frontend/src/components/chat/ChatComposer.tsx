"use client";

import { FormEvent, KeyboardEvent, useEffect, useRef } from "react";
import { useLocale } from "@/components/i18n/LocaleProvider";

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
  const { t } = useLocale();
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const submitDisabled = disabled || !value.trim();

  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  }, [value]);

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
    <div className="chat-composer-bar relative z-10 shrink-0 p-3 lg:p-4">
      {errorMessage ? (
        <div className="mb-3 rounded-xl border border-error/30 bg-error/10 p-3 text-sm text-error">
          <div className="flex items-start justify-between gap-3">
            <p className="flex-1 text-start">{errorMessage}</p>
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
      <form onSubmit={handleSubmit} className="w-full">
        <div className="flex w-full items-end gap-2 rounded-2xl border border-border bg-surface p-2 shadow-sm transition-shadow duration-200 focus-within:border-[color-mix(in_srgb,var(--secondary)_55%,transparent)] focus-within:shadow-[0_0_0_3px_var(--ring)]">
          <textarea
            ref={textareaRef}
            value={value}
            onChange={(event) => onChange(event.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={t("composer.placeholder")}
            rows={1}
            dir="auto"
            className="min-h-[44px] max-h-40 min-w-0 flex-1 resize-none border-0 bg-transparent py-2.5 ps-3 pe-1 text-start text-sm leading-relaxed text-text-primary outline-none placeholder:text-text-tertiary"
            disabled={disabled}
          />
          <button
            type="submit"
            disabled={submitDisabled}
            aria-label={t("composer.send")}
            className="btn-primary flex h-10 shrink-0 items-center gap-1.5 rounded-xl px-4 text-sm font-semibold disabled:cursor-not-allowed"
          >
            <SendIcon />
            <span className="hidden sm:inline">{t("composer.send")}</span>
          </button>
        </div>
        <p className="mt-2 px-1 text-start text-[11px] text-text-secondary">
          <kbd className="rounded border border-border bg-surface px-1.5 py-0.5 font-mono text-[10px]">
            Enter
          </kbd>
          <span> send · </span>
          <kbd className="rounded border border-border bg-surface px-1.5 py-0.5 font-mono text-[10px]">
            Shift+Enter
          </kbd>
          <span> new line</span>
        </p>
      </form>
    </div>
  );
}
