"use client";

import Image from "next/image";
import Link from "next/link";
import { AppColors } from "@/constants/AppColors";
import { ThemeToggle } from "@/components/theme/ThemeToggle";
import { t } from "@/lib/i18n";

export type AppRoute = "chat" | "warehouse";

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
  return (
    <header className="glass-header animate-fade-in-down relative z-10 flex shrink-0 items-center justify-between gap-3 border-b border-border/80 px-4 py-3 lg:px-6 lg:py-4">
      <div className="flex min-w-0 items-center gap-3">
        <div
          className="animate-float flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl shadow-sm"
          style={{ background: AppColors.softGradient }}
        >
          <Image
            src="/logo.png"
            alt=""
            width={28}
            height={28}
            className="h-7 w-7 object-contain"
          />
        </div>
        <div className="min-w-0">
          <h1 className="truncate text-base font-bold tracking-tight text-text-primary">
            {t("app.title")}
          </h1>
          <p className="truncate text-xs text-text-secondary">{t("app.subtitle")}</p>
        </div>
      </div>
      <div className="flex shrink-0 flex-wrap items-center justify-end gap-2">
        <nav className="flex items-center gap-1 rounded-xl border border-border/80 bg-background/60 p-1">
          <NavPill href="/chat" label={t("nav.chat")} active={active === "chat"} />
          <NavPill href="/warehouse" label={t("nav.warehouse")} active={active === "warehouse"} />
        </nav>
        {statusSlot}
        <ThemeToggle />
      </div>
    </header>
  );
}
