"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useState, type ReactNode } from "react";
import { fetchBackendHealth, fetchBackendReadiness } from "@/lib/backend";
import { useLocale } from "@/components/i18n/LocaleProvider";
import { ThemeToggle } from "@/components/theme/ThemeToggle";
import { LanguageToggle } from "@/components/i18n/LanguageToggle";
import type { TranslationKey } from "@/lib/i18n";

function ChatIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5Z" />
    </svg>
  );
}
function LibraryIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
      <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2Z" />
    </svg>
  );
}
function WarehouseIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M21 8v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8" />
      <path d="m2 8 10-5 10 5" />
      <path d="M8 21v-7h8v7" />
    </svg>
  );
}
function CorpusIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <ellipse cx="12" cy="5" rx="8" ry="3" />
      <path d="M4 5v6c0 1.66 3.58 3 8 3s8-1.34 8-3V5" />
      <path d="M4 11v6c0 1.66 3.58 3 8 3s8-1.34 8-3v-6" />
    </svg>
  );
}

interface Feature {
  href: string;
  labelKey: TranslationKey;
  descKey: TranslationKey;
  icon: ReactNode;
  featured?: boolean;
}

const FEATURES: Feature[] = [
  { href: "/chat", labelKey: "nav.chat", descKey: "home.featureChatDesc", icon: <ChatIcon />, featured: true },
  { href: "/formulations", labelKey: "nav.formulations", descKey: "home.featureLibraryDesc", icon: <LibraryIcon /> },
  { href: "/warehouse", labelKey: "nav.warehouse", descKey: "home.featureWarehouseDesc", icon: <WarehouseIcon /> },
  { href: "/corpus", labelKey: "nav.corpus", descKey: "home.featureCorpusDesc", icon: <CorpusIcon /> },
];

export default function Home() {
  const { t } = useLocale();
  const [status, setStatus] = useState("…");
  const [ready, setReady] = useState<boolean | null>(null);

  useEffect(() => {
    fetchBackendHealth()
      .then((h) => setStatus(`${h.service}: ${h.status}`))
      .catch(() => setStatus("backend: unavailable"));

    fetchBackendReadiness()
      .then((r) => setReady(r.ready))
      .catch(() => setReady(false));
  }, []);

  return (
    <div className="app-mesh-bg flex min-h-screen flex-col">
      <header className="relative z-10 flex items-center justify-between px-5 py-4 lg:px-10">
        <div className="logo-container logo-container--header animate-fade-in-down">
          <Image src="/logo.png" alt="Pharma AI" width={28} height={28} className="h-full w-full object-contain" priority />
        </div>
        <div className="flex items-center gap-2">
          <LanguageToggle />
          <ThemeToggle />
        </div>
      </header>

      <main className="relative z-10 mx-auto flex w-full max-w-5xl flex-1 flex-col justify-center px-5 py-10 lg:px-8">
        {/* Hero */}
        <div className="text-center">
          <span
            className="animate-fade-in-down ring-gradient inline-flex items-center gap-2 rounded-full bg-surface/70 px-3.5 py-1.5 text-xs font-semibold text-text-secondary backdrop-blur"
          >
            <span className="relative flex h-1.5 w-1.5">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-accent opacity-60" />
              <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-accent" />
            </span>
            {t("home.eyebrow")}
          </span>

          <h1
            className="animate-fade-in-up mt-7 text-balance text-4xl font-extrabold leading-[1.05] tracking-tight text-text-primary sm:text-6xl"
            style={{ animationDelay: "60ms" }}
          >
            <span className="gradient-text">{t("home.title")}</span>
          </h1>
          <p
            className="animate-fade-in-up mx-auto mt-5 max-w-xl text-pretty text-base leading-relaxed text-text-secondary sm:text-lg"
            style={{ animationDelay: "120ms" }}
          >
            {t("home.subtitle")}
          </p>

          <div
            className="animate-fade-in-up mt-7 flex flex-wrap items-center justify-center gap-3"
            style={{ animationDelay: "180ms" }}
          >
            <Link
              href="/chat"
              className="btn-primary inline-flex items-center gap-2 rounded-xl px-7 py-3.5 text-sm font-semibold"
            >
              {t("home.openChat")}
              <span aria-hidden className="rtl:rotate-180">→</span>
            </Link>
            <span className="inline-flex items-center gap-2 rounded-full border border-border bg-surface/70 px-3.5 py-2 text-xs font-medium text-text-secondary backdrop-blur">
              <span
                className={`h-2 w-2 rounded-full ${
                  ready === null
                    ? "bg-warning animate-pulse"
                    : ready
                      ? "bg-success shadow-[0_0_10px_rgba(22,179,100,0.6)]"
                      : "bg-warning animate-pulse"
                }`}
              />
              {status}
            </span>
          </div>
        </div>

        {/* Feature grid */}
        <div className="stagger-children mt-12 grid gap-4 sm:grid-cols-2">
          {FEATURES.map((f) => (
            <Link
              key={f.href}
              href={f.href}
              className={`hover-lift group relative flex flex-col overflow-hidden rounded-2xl border p-5 ${
                f.featured
                  ? "ring-gradient border-transparent bg-surface shadow-soft sm:p-6"
                  : "border-border bg-surface/80 shadow-sm backdrop-blur"
              }`}
            >
              {f.featured ? (
                <span
                  aria-hidden
                  className="pointer-events-none absolute -right-10 -top-10 h-32 w-32 rounded-full opacity-60 blur-2xl"
                  style={{ background: "var(--brand-gradient-soft)" }}
                />
              ) : null}
              <span
                className={`relative flex h-11 w-11 items-center justify-center rounded-xl ${
                  f.featured ? "text-white" : "text-secondary"
                }`}
                style={
                  f.featured
                    ? { background: "var(--brand-gradient-vivid)" }
                    : { background: "color-mix(in srgb, var(--secondary) 12%, transparent)" }
                }
              >
                <span className="h-5 w-5">{f.icon}</span>
              </span>
              <h2 className="relative mt-4 flex items-center gap-2 text-base font-bold text-text-primary">
                {t(f.labelKey)}
              </h2>
              <p className="relative mt-1.5 flex-1 text-sm leading-relaxed text-text-secondary">
                {t(f.descKey)}
              </p>
              <span className="relative mt-4 inline-flex items-center gap-1.5 text-xs font-semibold text-secondary">
                {t("home.enter")}
                <span aria-hidden className="transition-transform duration-300 group-hover:translate-x-1 rtl:rotate-180 rtl:group-hover:-translate-x-1">
                  →
                </span>
              </span>
            </Link>
          ))}
        </div>
      </main>
    </div>
  );
}
