"use client";

import Image from "next/image";
import Link from "next/link";
import { ThemeToggle } from "@/components/theme/ThemeToggle";
import { LanguageToggle } from "@/components/i18n/LanguageToggle";
import { useLocale } from "@/components/i18n/LocaleProvider";

export type AppRoute = "chat" | "warehouse" | "formulations" | "corpus";

interface AppHeaderProps {
  active: AppRoute;
  statusSlot?: React.ReactNode;
  /** Hide the brand text (logo only) for space-constrained layouts like the chat column. */
  compact?: boolean;
}

function NavPill({
  href,
  label,
  active,
}: {
  href: string;
  label: string;
  active: boolean;
}) {
  return (
    <Link
      href={href}
      aria-current={active ? "page" : undefined}
      className={`relative rounded-lg px-3 py-1.5 text-xs font-semibold transition-all duration-300 ${
        active
          ? "nav-pill-active text-white"
          : "text-text-secondary hover:bg-surface hover:text-text-primary"
      }`}
      style={active ? { background: "var(--brand-gradient-vivid)" } : undefined}
    >
      {label}
    </Link>
  );
}

export function AppHeader({ active, statusSlot, compact = false }: AppHeaderProps) {
  const { t } = useLocale();

  return (
    <header className="glass-header app-header animate-fade-in-down relative z-10">
      <Link href="/" className="group flex min-w-0 shrink-0 items-center gap-3">
        <span className="logo-container logo-container--header transition-transform duration-300 group-hover:scale-105">
          <Image src="/logo.png" alt="Pharma AI" width={26} height={26} className="h-full w-full object-contain" />
        </span>
        <span className={`min-w-0 leading-tight ${compact ? "lg:hidden" : ""}`}>
          <span className="block truncate text-[0.9375rem] font-bold text-text-primary">
            {t("app.title")}
          </span>
          <span className="block truncate text-[0.6875rem] text-text-secondary">
            {t("app.subtitle")}
          </span>
        </span>
      </Link>
      <div className="flex min-w-0 flex-wrap items-center justify-end gap-1.5 sm:gap-2">
        <nav className="flex flex-wrap items-center gap-1 rounded-xl border border-border bg-[var(--panel-muted)] p-1">
          <NavPill href="/chat" label={t("nav.chat")} active={active === "chat"} />
          <NavPill
            href="/formulations"
            label={t("nav.formulations")}
            active={active === "formulations"}
          />
          <NavPill href="/warehouse" label={t("nav.warehouse")} active={active === "warehouse"} />
          <NavPill href="/corpus" label={t("nav.corpus")} active={active === "corpus"} />
        </nav>
        {statusSlot}
        <LanguageToggle />
        <ThemeToggle />
      </div>
    </header>
  );
}
