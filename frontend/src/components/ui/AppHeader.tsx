"use client";

import Link from "next/link";
import { AppColors } from "@/constants/AppColors";
import { ThemeToggle } from "@/components/theme/ThemeToggle";
import { LanguageToggle } from "@/components/i18n/LanguageToggle";
import { useLocale } from "@/components/i18n/LocaleProvider";

export type AppRoute = "chat" | "warehouse" | "formulations" | "corpus";

interface AppHeaderProps {
  active: AppRoute;
  statusSlot?: React.ReactNode;
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
      className={`relative rounded-lg px-3 py-1.5 text-xs font-semibold transition-all duration-300 ${
        active
          ? "nav-pill-active text-white"
          : "text-text-secondary hover:bg-background hover:text-text-primary"
      }`}
      style={active ? { background: AppColors.buttonGradient } : undefined}
    >
      {label}
    </Link>
  );
}

export function AppHeader({ active, statusSlot }: AppHeaderProps) {
  const { t } = useLocale();

  return (
    <header className="glass-header app-header animate-fade-in-down relative z-10">
      <div className="min-w-0 leading-tight">
        <h1 className="truncate text-[0.9375rem] font-bold text-text-primary">{t("app.title")}</h1>
        <p className="truncate text-[0.6875rem] text-text-secondary">{t("app.subtitle")}</p>
      </div>
      <div className="flex shrink-0 flex-wrap items-center justify-end gap-1.5 sm:gap-2">
        <nav className="flex items-center gap-1 rounded-xl border border-border bg-[var(--panel-muted)] p-1">
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
