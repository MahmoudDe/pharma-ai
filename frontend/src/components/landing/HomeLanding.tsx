"use client";

import Link from "next/link";
import { useEffect, useState, type ReactNode } from "react";
import { AppColors } from "@/constants/AppColors";
import { fetchBackendHealth, fetchBackendReadiness } from "@/lib/backend";
import { useLocale } from "@/components/i18n/LocaleProvider";
import { ThemeToggle } from "@/components/theme/ThemeToggle";
import { LanguageToggle } from "@/components/i18n/LanguageToggle";
import { Logo } from "@/components/ui/Logo";
import { useAuth } from "@/components/auth/AuthProvider";
import { UserMenu } from "@/components/auth/UserMenu";
import { ProductPreview } from "@/components/landing/ProductPreview";
import {
  ArrowIcon,
  BatchIcon,
  ChatIcon,
  CiteIcon,
  CorpusIcon,
  CostIcon,
  LangIcon,
  LibraryIcon,
  LockIcon,
  SheetIcon,
  ShieldIcon,
  SwapIcon,
  WarehouseIcon,
} from "@/components/landing/icons";
import type { TranslationKey } from "@/lib/i18n";

const PROMPTS: TranslationKey[] = [
  "prompts.sulfateFree",
  "prompts.compareBaby",
  "prompts.capbVsSls",
  "prompts.handCream",
];

const STATS: { title: TranslationKey; hint: TranslationKey }[] = [
  { title: "home.statCite", hint: "home.statCiteHint" },
  { title: "home.statPrivate", hint: "home.statPrivateHint" },
  { title: "home.statLang", hint: "home.statLangHint" },
  { title: "home.statStock", hint: "home.statStockHint" },
];

const STEPS: { title: TranslationKey; desc: TranslationKey }[] = [
  { title: "home.how1Title", desc: "home.how1Desc" },
  { title: "home.how2Title", desc: "home.how2Desc" },
  { title: "home.how3Title", desc: "home.how3Desc" },
  { title: "home.how4Title", desc: "home.how4Desc" },
];

const CAPS: { title: TranslationKey; desc: TranslationKey; icon: ReactNode }[] = [
  { title: "home.capCiteTitle", desc: "home.capCiteDesc", icon: <CiteIcon /> },
  { title: "home.capSheetTitle", desc: "home.capSheetDesc", icon: <SheetIcon /> },
  { title: "home.capComplianceTitle", desc: "home.capComplianceDesc", icon: <ShieldIcon /> },
  { title: "home.capCostTitle", desc: "home.capCostDesc", icon: <CostIcon /> },
  { title: "home.capSubTitle", desc: "home.capSubDesc", icon: <SwapIcon /> },
  { title: "home.capBatchTitle", desc: "home.capBatchDesc", icon: <BatchIcon /> },
  { title: "home.capPrivateTitle", desc: "home.capPrivateDesc", icon: <LockIcon /> },
  { title: "home.capLangTitle", desc: "home.capLangDesc", icon: <LangIcon /> },
];

function SectionHeading({
  eyebrow,
  title,
  subtitle,
}: {
  eyebrow: string;
  title: string;
  subtitle: string;
}) {
  return (
    <div className="mx-auto max-w-2xl text-center">
      <p className="eyebrow">{eyebrow}</p>
      <h2 className="mt-3 text-balance text-3xl font-extrabold tracking-tight text-text-primary sm:text-4xl">
        {title}
      </h2>
      <p className="mt-3 text-pretty text-sm leading-relaxed text-text-secondary sm:text-base">
        {subtitle}
      </p>
    </div>
  );
}

function IconBadge({ children, featured = false }: { children: ReactNode; featured?: boolean }) {
  return (
    <span
      className={`flex h-11 w-11 items-center justify-center rounded-xl ${
        featured ? "text-white" : "text-secondary"
      }`}
      style={
        featured
          ? { background: AppColors.buttonGradient }
          : { background: "color-mix(in srgb, var(--secondary) 12%, transparent)" }
      }
    >
      <span className="h-5 w-5">{children}</span>
    </span>
  );
}

export function HomeLanding() {
  const { t } = useLocale();
  const { user, loading } = useAuth();
  const [status, setStatus] = useState("…");
  const [ready, setReady] = useState<boolean | null>(null);
  const chatHref = user ? "/chat" : "/login?next=/chat";

  useEffect(() => {
    fetchBackendHealth()
      .then((h) => setStatus(`${h.service}: ${h.status}`))
      .catch(() => setStatus("backend: unavailable"));

    fetchBackendReadiness()
      .then((r) => setReady(r.ready))
      .catch(() => setReady(false));
  }, []);

  return (
    <div className="app-mesh-bg flex min-h-screen flex-col overflow-x-clip">
      <header className="glass-header sticky top-0 z-30">
        <div className="mx-auto flex w-full max-w-6xl items-center justify-between gap-3 px-5 py-3 lg:px-8">
          <Link href="#top" className="group flex min-w-0 items-center gap-2.5">
            <Logo size="header" className="transition-transform duration-300 group-hover:scale-105" priority />
            <span className="min-w-0 leading-tight">
              <span className="block truncate text-sm font-bold text-text-primary">{t("app.title")}</span>
              <span className="hidden truncate text-[11px] text-text-secondary sm:block">{t("app.subtitle")}</span>
            </span>
          </Link>

          <nav className="hidden items-center gap-1 lg:flex">
            {(
              [
                ["#how", "home.navHow"],
                ["#workspace", "home.navModules"],
                ["#capabilities", "home.navCaps"],
                ["#warehouse", "home.navWarehouse"],
              ] as const
            ).map(([href, key]) => (
              <a
                key={href}
                href={href}
                className="rounded-lg px-3 py-1.5 text-xs font-semibold text-text-secondary transition-colors hover:bg-surface hover:text-text-primary"
              >
                {t(key)}
              </a>
            ))}
          </nav>

          <div className="flex items-center gap-2">
            <LanguageToggle />
            <ThemeToggle />
            {loading ? (
              <span className="h-9 w-9 animate-pulse rounded-xl bg-border/80" aria-hidden />
            ) : user ? (
              <UserMenu />
            ) : (
              <>
                <Link href="/login" className="btn-ghost rounded-xl px-3.5 py-2 text-xs font-semibold">
                  {t("auth.login")}
                </Link>
                <Link
                  href="/register"
                  className="btn-primary hidden rounded-xl px-3.5 py-2 text-xs font-semibold sm:inline-flex"
                >
                  {t("auth.register")}
                </Link>
              </>
            )}
          </div>
        </div>
      </header>

      <main id="top" className="relative z-10 mx-auto flex w-full max-w-6xl flex-1 flex-col px-5 lg:px-8">
        <section className="grid items-center gap-12 py-12 lg:grid-cols-[1.05fr_0.95fr] lg:gap-14 lg:py-16">
          <div>
            <span className="animate-fade-in-down ring-gradient inline-flex items-center gap-2 rounded-full bg-surface/70 px-3.5 py-1.5 text-xs font-semibold text-text-secondary backdrop-blur">
              <span className="relative flex h-1.5 w-1.5">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-accent opacity-60" />
                <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-accent" />
              </span>
              {t("home.eyebrow")}
            </span>

            <h1
              className="animate-fade-in-up mt-6 text-balance text-4xl font-extrabold leading-[1.08] tracking-tight sm:text-6xl"
              style={{ animationDelay: "60ms" }}
            >
              <span className="gradient-text">{t("home.title")}</span>
              <span className="mt-2 block text-lg font-semibold leading-snug tracking-normal text-text-primary sm:text-2xl">
                {t("home.titleAccent")}
              </span>
            </h1>
            <p
              className="animate-fade-in-up mt-5 max-w-xl text-pretty text-base leading-relaxed text-text-secondary sm:text-lg"
              style={{ animationDelay: "120ms" }}
            >
              {t("home.subtitle")}
            </p>
            {user ? (
              <p
                className="animate-fade-in-up mt-3 text-sm font-semibold text-secondary"
                style={{ animationDelay: "150ms" }}
              >
                {t("home.welcomeBack", { name: user.name })}
              </p>
            ) : null}

            <div
              className="animate-fade-in-up mt-8 flex flex-wrap items-center gap-3"
              style={{ animationDelay: "180ms" }}
            >
              <Link href={chatHref} className="btn-primary inline-flex items-center gap-2 rounded-xl px-7 py-3.5 text-sm font-semibold">
                {t("home.openChat")}
                <ArrowIcon />
              </Link>
              {!user ? (
                <Link
                  href="/register"
                  className="btn-ghost inline-flex items-center gap-2 rounded-xl px-6 py-3.5 text-sm font-semibold"
                >
                  {t("auth.register")}
                </Link>
              ) : (
                <Link
                  href="/formulations"
                  className="btn-ghost inline-flex items-center gap-2 rounded-xl px-6 py-3.5 text-sm font-semibold"
                >
                  {t("home.openLibrary")}
                </Link>
              )}
              <a
                href="#how"
                className="inline-flex items-center gap-1.5 px-2 py-2 text-sm font-semibold text-text-secondary transition-colors hover:text-secondary"
              >
                {t("home.secondaryCta")}
                <span aria-hidden className="text-xs">↓</span>
              </a>
            </div>

            <div
              className="animate-fade-in-up mt-6 flex flex-wrap items-center gap-2"
              style={{ animationDelay: "220ms" }}
            >
              <span className="text-[11px] font-semibold uppercase tracking-wide text-text-tertiary">
                {t("home.tryAsking")}
              </span>
              {PROMPTS.map((key) => (
                <Link
                  key={key}
                  href={chatHref}
                  className="rounded-full border border-border bg-surface/80 px-3 py-1.5 text-xs font-medium text-text-secondary backdrop-blur transition-colors hover:border-secondary/40 hover:text-text-primary"
                >
                  {t(key)}
                </Link>
              ))}
            </div>

            <div className="mt-5 inline-flex items-center gap-2 rounded-full border border-border bg-surface/70 px-3.5 py-2 text-xs font-medium text-text-secondary backdrop-blur">
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
            </div>
          </div>

          <div className="animate-fade-in-up" style={{ animationDelay: "160ms" }}>
            <ProductPreview />
          </div>
        </section>

        <section className="stagger-children grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {STATS.map((stat) => (
            <div
              key={stat.title}
              className="rounded-2xl border border-border bg-surface/80 px-4 py-4 shadow-sm backdrop-blur"
            >
              <p className="text-sm font-bold text-text-primary">{t(stat.title)}</p>
              <p className="mt-1 text-xs leading-relaxed text-text-secondary">{t(stat.hint)}</p>
            </div>
          ))}
        </section>

        <section id="how" className="scroll-mt-24 py-20">
          <SectionHeading
            eyebrow={t("home.howEyebrow")}
            title={t("home.howTitle")}
            subtitle={t("home.howSubtitle")}
          />
          <div className="relative mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-4 stagger-children">
            <div
              aria-hidden
              className="landing-step-line pointer-events-none absolute start-[12%] end-[12%] top-10 hidden h-px lg:block"
            />
            {STEPS.map((step, index) => (
              <article
                key={step.title}
                className="hover-lift relative rounded-2xl border border-border bg-surface p-5 shadow-sm"
              >
                <span
                  className="relative z-10 flex h-10 w-10 items-center justify-center rounded-full text-sm font-extrabold text-white"
                  style={{ background: AppColors.buttonGradient }}
                >
                  {String(index + 1).padStart(2, "0")}
                </span>
                <h3 className="mt-4 text-base font-bold text-text-primary">{t(step.title)}</h3>
                <p className="mt-2 text-sm leading-relaxed text-text-secondary">{t(step.desc)}</p>
              </article>
            ))}
          </div>
        </section>

        <section id="workspace" className="scroll-mt-24 pb-8">
          <SectionHeading
            eyebrow={t("home.modulesEyebrow")}
            title={t("home.modulesTitle")}
            subtitle={t("home.modulesSubtitle")}
          />
          <div className="mt-12 grid gap-4 lg:grid-cols-3">
            <Link
              href={chatHref}
              className="hover-lift group relative overflow-hidden rounded-2xl border border-transparent bg-surface p-6 shadow-soft ring-gradient sm:p-7 lg:col-span-3"
            >
              <span
                aria-hidden
                className="pointer-events-none absolute -end-16 -top-16 h-48 w-48 rounded-full opacity-70 blur-3xl"
                style={{ background: AppColors.softGradient }}
              />
              <div className="relative flex flex-col gap-5 sm:flex-row sm:items-center sm:justify-between">
                <div className="flex min-w-0 items-start gap-4">
                  <IconBadge featured>
                    <ChatIcon />
                  </IconBadge>
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="text-lg font-bold text-text-primary">{t("nav.chat")}</h3>
                      <span
                        className="rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-white"
                        style={{ background: AppColors.buttonGradient }}
                      >
                        {t("home.featureChatTag")}
                      </span>
                    </div>
                    <p className="mt-1.5 max-w-2xl text-sm leading-relaxed text-text-secondary">
                      {t("home.featureChatDesc")}
                    </p>
                    <p className="mt-2 text-xs font-semibold text-secondary">{t("home.featureChatPoint")}</p>
                  </div>
                </div>
                <span className="relative inline-flex shrink-0 items-center gap-1.5 text-sm font-semibold text-secondary">
                  {t("home.enter")}
                  <span className="transition-transform duration-300 group-hover:translate-x-1 rtl:rotate-180 rtl:group-hover:-translate-x-1">
                    <ArrowIcon />
                  </span>
                </span>
              </div>
            </Link>

            {(
              [
                {
                  href: "/formulations",
                  label: "nav.formulations" as const,
                  desc: "home.featureLibraryDesc" as const,
                  point: "home.featureLibraryPoint" as const,
                  icon: <LibraryIcon />,
                },
                {
                  href: "/warehouse",
                  label: "nav.warehouse" as const,
                  desc: "home.featureWarehouseDesc" as const,
                  point: "home.featureWarehousePoint" as const,
                  icon: <WarehouseIcon />,
                },
                {
                  href: "/corpus",
                  label: "nav.corpus" as const,
                  desc: "home.featureCorpusDesc" as const,
                  point: "home.featureCorpusPoint" as const,
                  icon: <CorpusIcon />,
                },
              ]
            ).map((mod) => (
              <Link
                key={mod.href}
                href={mod.href}
                className="hover-lift group flex flex-col rounded-2xl border border-border bg-surface/80 p-5 shadow-sm backdrop-blur"
              >
                <IconBadge>{mod.icon}</IconBadge>
                <h3 className="mt-4 text-base font-bold text-text-primary">{t(mod.label)}</h3>
                <p className="mt-1.5 flex-1 text-sm leading-relaxed text-text-secondary">{t(mod.desc)}</p>
                <p className="mt-3 text-xs font-medium text-text-tertiary">{t(mod.point)}</p>
                <span className="mt-4 inline-flex items-center gap-1.5 text-xs font-semibold text-secondary">
                  {t("home.enter")}
                  <span className="transition-transform duration-300 group-hover:translate-x-1 rtl:rotate-180 rtl:group-hover:-translate-x-1">
                    <ArrowIcon />
                  </span>
                </span>
              </Link>
            ))}
          </div>
        </section>

        <section id="capabilities" className="scroll-mt-24 py-20">
          <SectionHeading
            eyebrow={t("home.capsEyebrow")}
            title={t("home.capsTitle")}
            subtitle={t("home.capsSubtitle")}
          />
          <div className="stagger-children mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {CAPS.map((cap) => (
              <article
                key={cap.title}
                className="hover-lift rounded-2xl border border-border bg-surface p-5 shadow-sm"
              >
                <IconBadge>{cap.icon}</IconBadge>
                <h3 className="mt-4 text-sm font-bold text-text-primary">{t(cap.title)}</h3>
                <p className="mt-1.5 text-sm leading-relaxed text-text-secondary">{t(cap.desc)}</p>
              </article>
            ))}
          </div>
        </section>

        <section id="warehouse" className="scroll-mt-24 pb-8">
          <div className="overflow-hidden rounded-3xl border border-border bg-surface shadow-soft">
            <div className="grid lg:grid-cols-2">
              <div className="p-7 sm:p-10">
                <p className="eyebrow">{t("home.whEyebrow")}</p>
                <h2 className="mt-3 text-balance text-3xl font-extrabold tracking-tight text-text-primary">
                  {t("home.whTitle")}
                </h2>
                <p className="mt-3 max-w-md text-sm leading-relaxed text-text-secondary sm:text-base">
                  {t("home.whSubtitle")}
                </p>
                <Link
                  href="/warehouse"
                  className="btn-primary mt-7 inline-flex items-center gap-2 rounded-xl px-6 py-3 text-sm font-semibold"
                >
                  {t("home.openWarehouse")}
                  <ArrowIcon />
                </Link>
              </div>
              <div
                className="relative flex flex-col justify-center gap-3 p-7 sm:p-10"
                style={{ background: AppColors.softGradient }}
              >
                {(
                  [
                    ["01", "home.wh1"],
                    ["02", "home.wh2"],
                    ["03", "home.wh3"],
                  ] as const
                ).map(([num, key]) => (
                  <div
                    key={num}
                    className="flex items-center gap-4 rounded-2xl border border-border/80 bg-surface/90 px-4 py-3.5 shadow-sm backdrop-blur"
                  >
                    <span
                      className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl text-xs font-extrabold text-white"
                      style={{ background: AppColors.buttonGradient }}
                    >
                      {num}
                    </span>
                    <p className="text-sm font-bold text-text-primary">{t(key)}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>

        <section className="py-16">
          <div
            className="relative overflow-hidden rounded-3xl px-6 py-12 text-center text-white sm:px-12"
            style={{ background: AppColors.buttonGradient }}
          >
            <div
              aria-hidden
              className="pointer-events-none absolute inset-0 opacity-40"
              style={{
                background:
                  "radial-gradient(ellipse 60% 50% at 10% 0%, rgba(255,255,255,0.28), transparent 55%), radial-gradient(ellipse 50% 40% at 90% 100%, rgba(33,205,240,0.45), transparent 50%)",
              }}
            />
            <div className="relative">
              <h2 className="text-balance text-3xl font-extrabold tracking-tight sm:text-4xl">
                {t("home.ctaTitle")}
              </h2>
              <p className="mx-auto mt-3 max-w-xl text-sm leading-relaxed text-white/80 sm:text-base">
                {user ? t("home.ctaLoggedIn") : t("home.ctaSubtitle")}
              </p>
              <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
                <Link
                  href={chatHref}
                  className="inline-flex items-center gap-2 rounded-xl bg-white px-7 py-3.5 text-sm font-semibold shadow-sm transition hover:-translate-y-0.5 hover:shadow-lg"
                  style={{ color: AppColors.primary }}
                >
                  {t("home.openChat")}
                  <ArrowIcon />
                </Link>
                {!user ? (
                  <Link
                    href="/register"
                    className="inline-flex items-center gap-2 rounded-xl border border-white/30 bg-white/10 px-6 py-3.5 text-sm font-semibold text-white backdrop-blur transition hover:bg-white/20"
                  >
                    {t("auth.register")}
                  </Link>
                ) : (
                  <Link
                    href="/warehouse"
                    className="inline-flex items-center gap-2 rounded-xl border border-white/30 bg-white/10 px-6 py-3.5 text-sm font-semibold text-white backdrop-blur transition hover:bg-white/20"
                  >
                    {t("home.openWarehouse")}
                  </Link>
                )}
              </div>
            </div>
          </div>
        </section>
      </main>

      <footer className="relative z-10 border-t border-border px-5 py-8 lg:px-8">
        <div className="mx-auto flex w-full max-w-6xl flex-col items-start justify-between gap-3 sm:flex-row sm:items-center">
          <div className="flex items-center gap-2.5">
            <Logo size="sm" />
            <span className="text-sm font-bold text-text-primary">{t("app.title")}</span>
          </div>
          <p className="max-w-lg text-xs leading-relaxed text-text-tertiary">{t("home.footerDisclaimer")}</p>
        </div>
      </footer>
    </div>
  );
}
