import ar from "@/locales/ar.json";
import en from "@/locales/en.json";

const catalogs = { en, ar } as const;

export type Locale = keyof typeof catalogs;
export type TranslationKey = keyof typeof en;

export const LOCALE_STORAGE_KEY = "pharma-ai-locale";
export const LOCALE_COOKIE_NAME = "pharma-ai-locale";

export function parseLocale(value: string | undefined | null): Locale {
  return value === "ar" ? "ar" : "en";
}

let locale: Locale = "en";

export function setLocale(next: Locale): void {
  locale = next;
}

export function getLocale(): Locale {
  return locale;
}

export function createT(forLocale: Locale) {
  return function t(key: TranslationKey, vars?: Record<string, string | number>): string {
    const catalog = catalogs[forLocale];
    let text = (catalog[key] as string | undefined) ?? en[key] ?? key;
    if (vars) {
      for (const [k, v] of Object.entries(vars)) {
        text = text.replaceAll(`{${k}}`, String(v));
      }
    }
    return text;
  };
}

/** Uses module locale; prefer `useLocale().t` in client components. */
export function t(key: TranslationKey, vars?: Record<string, string | number>): string {
  return createT(locale)(key, vars);
}
