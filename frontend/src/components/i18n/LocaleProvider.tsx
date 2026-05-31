"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import {
  createT,
  LOCALE_COOKIE_NAME,
  LOCALE_STORAGE_KEY,
  setLocale as setGlobalLocale,
  type Locale,
  type TranslationKey,
} from "@/lib/i18n";

interface LocaleContextValue {
  locale: Locale;
  setLocale: (next: Locale) => void;
  t: (key: TranslationKey, vars?: Record<string, string | number>) => string;
  dir: "ltr" | "rtl";
}

const LocaleContext = createContext<LocaleContextValue | null>(null);

function readStoredLocale(): Locale {
  if (typeof window === "undefined") return "en";
  try {
    const stored = localStorage.getItem(LOCALE_STORAGE_KEY);
    if (stored === "ar" || stored === "en") return stored;
  } catch {
    /* ignore */
  }
  return "en";
}

function persistLocaleCookie(locale: Locale): void {
  document.cookie = `${LOCALE_COOKIE_NAME}=${locale};path=/;max-age=31536000;SameSite=Lax`;
}

function applyDocumentLocale(locale: Locale): void {
  const root = document.documentElement;
  root.lang = locale;
  root.dir = locale === "ar" ? "rtl" : "ltr";
}

export function LocaleProvider({
  children,
  initialLocale = "en",
}: {
  children: ReactNode;
  initialLocale?: Locale;
}) {
  const [locale, setLocaleState] = useState<Locale>(() => {
    setGlobalLocale(initialLocale);
    return initialLocale;
  });
  const didMountSync = useRef(false);

  const setLocale = useCallback((next: Locale) => {
    setLocaleState((current) => {
      if (current === next) return current;
      setGlobalLocale(next);
      try {
        localStorage.setItem(LOCALE_STORAGE_KEY, next);
      } catch {
        /* ignore */
      }
      persistLocaleCookie(next);
      applyDocumentLocale(next);
      return next;
    });
  }, []);

  const t = useMemo(() => createT(locale), [locale]);

  // Once after mount: adopt localStorage if it differs from SSR cookie (no hydration fight).
  useEffect(() => {
    if (didMountSync.current) return;
    didMountSync.current = true;
    const stored = readStoredLocale();
    if (stored !== initialLocale) {
      setGlobalLocale(stored);
      setLocaleState(stored);
      applyDocumentLocale(stored);
      persistLocaleCookie(stored);
    }
  }, [initialLocale]);

  useEffect(() => {
    applyDocumentLocale(locale);
    persistLocaleCookie(locale);
    try {
      localStorage.setItem(LOCALE_STORAGE_KEY, locale);
    } catch {
      /* ignore */
    }
    setGlobalLocale(locale);
  }, [locale]);

  const value = useMemo<LocaleContextValue>(
    () => ({
      locale,
      setLocale,
      t,
      dir: locale === "ar" ? "rtl" : "ltr",
    }),
    [locale, setLocale, t],
  );

  return <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>;
}

export function useLocale(): LocaleContextValue {
  const ctx = useContext(LocaleContext);
  if (!ctx) {
    throw new Error("useLocale must be used within LocaleProvider");
  }
  return ctx;
}
