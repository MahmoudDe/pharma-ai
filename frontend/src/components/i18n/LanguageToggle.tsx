"use client";

import { AppColors } from "@/constants/AppColors";
import { useLocale } from "@/components/i18n/LocaleProvider";
import type { Locale } from "@/lib/i18n";

const LOCALE_LABELS: Record<Locale, string> = {
  en: "EN",
  ar: "ع",
};

export function LanguageToggle() {
  const { locale, setLocale } = useLocale();

  const options: Locale[] = ["en", "ar"];

  return (
    <div
      className="flex h-9 shrink-0 items-center gap-0.5 rounded-xl border border-border bg-[var(--panel-muted)] p-0.5"
      role="group"
      aria-label="Language"
    >
      {options.map((id) => {
        const active = locale === id;
        return (
          <button
            key={id}
            type="button"
            onClick={() => setLocale(id)}
            aria-pressed={active}
            className={`inline-flex h-8 min-w-[2.25rem] items-center justify-center rounded-lg px-2.5 text-[10px] font-bold uppercase tracking-wide transition-all duration-200 ${
              active ? "text-white shadow-sm" : "text-text-secondary hover:text-text-primary"
            }`}
            style={active ? { background: AppColors.buttonGradient } : undefined}
          >
            {LOCALE_LABELS[id]}
          </button>
        );
      })}
    </div>
  );
}
