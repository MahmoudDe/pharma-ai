"use client";

import { AppColors } from "@/constants/AppColors";
import { useLocale } from "@/components/i18n/LocaleProvider";
import { Logo } from "@/components/ui/Logo";

const PREVIEW_ROWS = [
  { name: "Cocamidopropyl betaine", amount: "8.0%", phase: "A" },
  { name: "Glycerin", amount: "3.0%", phase: "B" },
  { name: "Panthenol", amount: "0.5%", phase: "B" },
];

export function ProductPreview() {
  const { t } = useLocale();

  return (
    <div className="landing-preview-stage relative mx-auto w-full max-w-lg lg:mx-0 lg:max-w-none">
      <div
        aria-hidden
        className="landing-orb -start-8 top-8 h-40 w-40 opacity-80"
        style={{ background: AppColors.secondary }}
      />
      <div
        aria-hidden
        className="landing-orb -end-6 bottom-4 h-36 w-36 opacity-70"
        style={{ background: AppColors.accent, animationDelay: "1.4s" }}
      />

      <div className="landing-preview-card relative">
        <div className="ring-gradient card-sheen overflow-hidden rounded-3xl border border-border bg-surface shadow-[var(--shadow-panel)]">
          <div className="flex items-center justify-between border-b border-border px-4 py-3">
            <div className="flex items-center gap-2.5">
              <Logo size="sm" />
              <div className="leading-tight">
                <p className="text-xs font-bold text-text-primary">{t("app.title")}</p>
                <p className="text-[10px] text-text-secondary">{t("nav.chat")}</p>
              </div>
            </div>
            <span
              className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[10px] font-semibold"
              style={{
                background: AppColors.softGradient,
                color: AppColors.secondary,
              }}
            >
              <span
                className="h-1.5 w-1.5 rounded-full"
                style={{ background: AppColors.success, boxShadow: `0 0 8px ${AppColors.success}` }}
              />
              {t("home.previewVerified")}
            </span>
          </div>

          <div className="space-y-3 bg-[var(--surface-sunken)] p-4">
            <div className="ms-auto max-w-[88%] rounded-2xl rounded-ee-md px-3.5 py-2.5 text-xs font-medium leading-relaxed text-white"
              style={{ background: AppColors.buttonGradient }}
            >
              {t("home.previewUser")}
            </div>

            <div className="max-w-[92%] rounded-2xl rounded-es-md border border-border bg-surface px-3.5 py-2.5 shadow-sm">
              <p className="text-xs leading-relaxed text-text-primary">{t("home.previewAssistant")}</p>
              <span
                className="mt-2 inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold text-secondary"
                style={{
                  background: "color-mix(in srgb, var(--accent) 16%, transparent)",
                }}
              >
                {t("home.previewCite")}
              </span>
            </div>

            <div className="overflow-hidden rounded-2xl border border-border bg-surface shadow-sm">
              <div className="flex items-center justify-between border-b border-border px-3 py-2">
                <p className="text-xs font-bold text-text-primary">{t("home.previewFormula")}</p>
                <span className="font-mono text-[10px] text-text-tertiary">100%</span>
              </div>
              <table className="w-full text-start text-[11px]">
                <thead>
                  <tr className="border-b border-border bg-surface-sunken text-[10px] uppercase tracking-wide text-text-secondary">
                    <th className="px-3 py-1.5 font-semibold">{t("formula.colIngredient")}</th>
                    <th className="px-3 py-1.5 font-semibold">{t("formula.colAmount")}</th>
                    <th className="px-3 py-1.5 font-semibold">{t("formula.colPhase")}</th>
                  </tr>
                </thead>
                <tbody>
                  {PREVIEW_ROWS.map((row) => (
                    <tr key={row.name} className="border-b border-border/50 last:border-0">
                      <td className="px-3 py-1.5 text-text-primary">{row.name}</td>
                      <td className="px-3 py-1.5 font-mono text-text-secondary">{row.amount}</td>
                      <td className="px-3 py-1.5 text-text-secondary">{row.phase}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
