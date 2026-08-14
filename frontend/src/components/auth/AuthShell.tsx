"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { AppColors } from "@/constants/AppColors";
import { LanguageToggle } from "@/components/i18n/LanguageToggle";
import { ThemeToggle } from "@/components/theme/ThemeToggle";
import { Logo } from "@/components/ui/Logo";
import { useLocale } from "@/components/i18n/LocaleProvider";

const FORMULA_CHIPS = [
  { name: "CAPB", amount: "8.0%" },
  { name: "Glycerin", amount: "3.0%" },
  { name: "Panthenol", amount: "0.5%" },
];

export function AuthShell({
  children,
  title,
  subtitle,
}: {
  children: ReactNode;
  title: string;
  subtitle: string;
}) {
  const { t } = useLocale();

  return (
    <div className="app-mesh-bg grid min-h-screen lg:grid-cols-[1.05fr_0.95fr]">
      <aside className="relative hidden overflow-hidden px-10 py-10 text-white lg:flex lg:flex-col lg:justify-between">
        <div
          aria-hidden
          className="absolute inset-0"
          style={{ background: AppColors.buttonGradient }}
        />
        <div
          aria-hidden
          className="absolute inset-0 opacity-40"
          style={{
            background:
              "radial-gradient(ellipse 70% 50% at 10% 0%, rgba(255,255,255,0.28), transparent 55%), radial-gradient(ellipse 50% 40% at 90% 100%, rgba(33,205,240,0.45), transparent 50%)",
          }}
        />
        <div
          aria-hidden
          className="absolute inset-0 opacity-15"
          style={{
            backgroundImage:
              "linear-gradient(rgba(255,255,255,0.35) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.35) 1px, transparent 1px)",
            backgroundSize: "42px 42px",
            maskImage: "radial-gradient(ellipse 80% 70% at 50% 40%, #000 20%, transparent 75%)",
          }}
        />

        <div className="relative z-10">
          <Link href="/" className="inline-flex items-center gap-3">
            <Logo size="header" />
            <span>
              <span className="block text-sm font-bold tracking-wide">{t("app.title")}</span>
              <span className="block text-xs text-white/75">{t("app.subtitle")}</span>
            </span>
          </Link>
        </div>

        <div className="relative z-10 max-w-md">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-white/70">
            {t("auth.brandEyebrow")}
          </p>
          <h1 className="mt-4 text-4xl font-extrabold leading-tight tracking-tight">
            {t("auth.brandTitle")}
          </h1>
          <p className="mt-4 text-sm leading-relaxed text-white/80">{t("auth.brandBody")}</p>
          <ul className="mt-8 space-y-3 text-sm">
            {[t("auth.brandPoint1"), t("auth.brandPoint2"), t("auth.brandPoint3")].map((point) => (
              <li key={point} className="flex items-start gap-3">
                <span className="mt-0.5 inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-white/20 text-[11px] font-bold">
                  ✓
                </span>
                <span className="text-white/90">{point}</span>
              </li>
            ))}
          </ul>
        </div>

        <div className="relative z-10 flex flex-wrap gap-2">
          {FORMULA_CHIPS.map((chip) => (
            <span
              key={chip.name}
              className="rounded-full border border-white/20 bg-white/10 px-3 py-1.5 text-xs font-semibold backdrop-blur-md"
            >
              {chip.name}
              <span className="ms-2 font-mono text-white/70">{chip.amount}</span>
            </span>
          ))}
        </div>
      </aside>

      <div className="relative flex min-h-screen flex-col px-5 py-5 sm:px-8 lg:px-12">
        <header className="flex items-center justify-between gap-3">
          <Link href="/" className="inline-flex items-center gap-2 lg:invisible">
            <Logo size="header" />
            <span className="text-sm font-bold text-text-primary">{t("app.title")}</span>
          </Link>
          <div className="ms-auto flex items-center gap-2">
            <LanguageToggle />
            <ThemeToggle />
          </div>
        </header>

        <main className="mx-auto flex w-full max-w-md flex-1 flex-col justify-center py-10">
          <div className="animate-fade-in-up">
            <h2 className="text-3xl font-extrabold tracking-tight text-text-primary">{title}</h2>
            <p className="mt-2 text-sm leading-relaxed text-text-secondary">{subtitle}</p>
          </div>
          <div className="animate-fade-in-up mt-8" style={{ animationDelay: "80ms" }}>
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}
