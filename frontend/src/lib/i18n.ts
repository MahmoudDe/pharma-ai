import ar from "@/locales/ar.json";
import en from "@/locales/en.json";

const catalogs = { en, ar } as const;

export type Locale = keyof typeof catalogs;

let locale: Locale = "en";

export function setLocale(next: Locale): void {
  locale = next;
}

export function getLocale(): Locale {
  return locale;
}

export function t(key: keyof typeof en): string {
  const catalog = catalogs[locale];
  return (catalog[key] as string | undefined) ?? en[key] ?? key;
}
