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
      className="flex items-center gap-0.5 rounded-xl border border-border bg-[var(--panel-muted)] p-0.5"
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
            className={`min-w-[2.25rem] rounded-lg px-2.5 py-1 text-[10px] font-bold uppercase tracking-wide transition-all duration-200 ${
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
