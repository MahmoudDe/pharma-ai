"use client";

import Link from "next/link";
import { ThemeToggle } from "@/components/theme/ThemeToggle";
import { LanguageToggle } from "@/components/i18n/LanguageToggle";
import { Logo } from "@/components/ui/Logo";
import { useLocale } from "@/components/i18n/LocaleProvider";
import { useAuth } from "@/components/auth/AuthProvider";
import { UserMenu } from "@/components/auth/UserMenu";

export type AppRoute = "chat" | "warehouse" | "formulations" | "corpus" | "profile";

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
      className={`relative inline-flex h-7 shrink-0 items-center rounded-lg px-2.5 text-xs font-semibold leading-none whitespace-nowrap transition-all duration-300 ${
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
  const { user, loading } = useAuth();

  return (
    <header
      className={`glass-header app-header animate-fade-in-down relative z-10 ${
        compact ? "app-header--compact" : ""
      }`}
    >
      <Link href="/" className="group flex h-9 min-w-0 shrink-0 items-center gap-2.5">
        <Logo
          size="sm"
          className="transition-transform duration-300 group-hover:scale-105"
        />
        <span className={`min-w-0 leading-tight ${compact ? "hidden" : ""}`}>
          <span className="block truncate text-[0.9375rem] font-bold text-text-primary">
            {t("app.title")}
          </span>
          <span className="block truncate text-[0.6875rem] text-text-secondary">
            {t("app.subtitle")}
          </span>
        </span>
      </Link>
      <div
        className={`flex min-w-0 items-center justify-end ${
          compact ? "flex-nowrap gap-1.5 overflow-hidden" : "flex-wrap gap-1.5 sm:gap-2"
        }`}
      >
        <nav className="flex h-9 min-w-0 items-center gap-0.5 overflow-x-auto rounded-xl border border-border bg-[var(--panel-muted)] p-1">
          <NavPill href="/chat" label={t("nav.chat")} active={active === "chat"} />
          <NavPill
            href="/formulations"
            label={t("nav.formulations")}
            active={active === "formulations"}
          />
          <NavPill href="/warehouse" label={t("nav.warehouse")} active={active === "warehouse"} />
          <NavPill href="/corpus" label={t("nav.corpus")} active={active === "corpus"} />
        </nav>
        {statusSlot ? (
          <span className={compact ? "hidden xl:inline-flex" : undefined}>{statusSlot}</span>
        ) : null}
        <LanguageToggle />
        <ThemeToggle />
        {loading ? (
          <span className="h-9 w-9 shrink-0 animate-pulse rounded-xl bg-border/80" aria-hidden />
        ) : user ? (
          <UserMenu compact={compact} />
        ) : (
          <div className="flex h-9 items-center gap-1.5">
            <Link
              href="/login"
              className="btn-ghost inline-flex h-9 items-center rounded-xl px-3 text-xs font-semibold"
            >
              {t("auth.login")}
            </Link>
            <Link
              href="/register"
              className="btn-primary hidden h-9 items-center rounded-xl px-3 text-xs font-semibold sm:inline-flex"
            >
              {t("auth.register")}
            </Link>
          </div>
        )}
      </div>
    </header>
  );
}
