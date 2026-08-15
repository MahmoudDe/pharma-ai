"use client";

import { useRef, useState, type ReactNode } from "react";
import { BatchCalculator } from "@/components/formula/BatchCalculator";
import { ComplianceBadge } from "@/components/formula/ComplianceBadge";
import { CostBadge } from "@/components/formula/CostBadge";
import { SubstitutionPanel } from "@/components/formula/SubstitutionPanel";
import { useLocale } from "@/components/i18n/LocaleProvider";
import {
  downloadBlob,
  downloadTextFile,
  formulaToCsv,
  formulaToExcelBlob,
  formulaToPdfBlob,
  safeFormulaFilename,
} from "@/lib/formulaExport";
import { formulaToMarkdown } from "@/lib/formulaMarkdown";
import { sourcePdfUrl } from "@/lib/sources";
import type {
  CitedEvidence,
  StructuredBrief,
  StructuredFormulationView,
  SuggestedNextAction,
} from "@/types/chat";
import { FormulaComparePanel } from "@/components/formula/FormulaComparePanel";

interface FormulaWorksheetProps {
  formulation: StructuredFormulationView | null;
  formulations?: StructuredFormulationView[];
  evidence: CitedEvidence[];
  actions: SuggestedNextAction[];
  onActionClick: (action: SuggestedNextAction) => void;
  brief?: StructuredBrief;
}

/** Stable palette for phase color-coding (works in light & dark). */
const PHASE_PALETTE = ["#7C4ADC", "#21CDF0", "#16B364", "#F59E0B", "#EC4899", "#6366F1", "#0EA5E9"];

function buildPhaseColors(formulation: StructuredFormulationView): Map<string, string> {
  const map = new Map<string, string>();
  let i = 0;
  for (const ing of formulation.ingredients) {
    const phase = (ing.phase ?? "").trim();
    if (!phase || map.has(phase)) continue;
    map.set(phase, PHASE_PALETTE[i % PHASE_PALETTE.length]);
    i += 1;
  }
  return map;
}

function percentTotal(formulation: StructuredFormulationView): number | null {
  let sum = 0;
  let any = false;
  for (const ing of formulation.ingredients) {
    if (ing.amount == null || ing.unit !== "%") continue;
    sum += ing.amount;
    any = true;
  }
  return any ? sum : null;
}

/* ---------- collapsible section ---------- */
function Section({
  title,
  icon,
  badge,
  defaultOpen = false,
  children,
}: {
  title: string;
  icon: ReactNode;
  badge?: ReactNode;
  defaultOpen?: boolean;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const rootRef = useRef<HTMLDivElement>(null);

  const toggle = () => {
    setOpen((wasOpen) => {
      const next = !wasOpen;
      if (next) {
        requestAnimationFrame(() => {
          rootRef.current?.scrollIntoView({ block: "nearest", behavior: "smooth" });
        });
      }
      return next;
    });
  };

  return (
    <div ref={rootRef} className="surface-inset shrink-0 overflow-hidden">
      <button
        type="button"
        onClick={toggle}
        className="flex w-full items-center gap-2 px-3.5 py-3 text-start"
      >
        <span
          aria-hidden
          className="flex h-6 w-6 items-center justify-center rounded-lg text-secondary"
          style={{ background: "color-mix(in srgb, var(--secondary) 12%, transparent)" }}
        >
          {icon}
        </span>
        <span className="flex-1 text-sm font-bold text-text-primary">{title}</span>
        {badge}
        <svg
          width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
          strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden
          className={`text-text-tertiary transition-transform duration-300 ${open ? "rotate-180" : ""}`}
        >
          <path d="m6 9 6 6 6-6" />
        </svg>
      </button>
      <div className={`constraints-expand ${open ? "open" : ""}`}>
        <div>
          <div className="px-3.5 pb-3.5">{children}</div>
        </div>
      </div>
    </div>
  );
}

/* ---------- spec sheet ---------- */
function SpecSheet({
  formulation,
  brief,
}: {
  formulation: StructuredFormulationView;
  brief?: StructuredBrief;
}) {
  const { t } = useLocale();
  const [copied, setCopied] = useState(false);
  const phaseColors = buildPhaseColors(formulation);
  const total = percentTotal(formulation);
  const baseComplete = total != null && Math.abs(total - 100) <= 0.5;

  const onCopy = async () => {
    await navigator.clipboard.writeText(formulaToMarkdown(formulation));
    setCopied(true);
    setTimeout(() => setCopied(false), 1800);
  };
  const onExportCsv = () => {
    downloadTextFile(
      formulaToCsv(formulation),
      safeFormulaFilename(formulation.name, "csv"),
      "text/csv;charset=utf-8",
    );
  };
  const onExportExcel = () => {
    downloadBlob(formulaToExcelBlob(formulation), safeFormulaFilename(formulation.name, "xlsx"));
  };
  const onExportPdf = () => {
    downloadBlob(formulaToPdfBlob(formulation), safeFormulaFilename(formulation.name, "pdf"));
  };

  return (
    <div>
      {/* title + meta */}
      <div className="flex items-start justify-between gap-2">
        <p className="text-sm font-bold leading-snug text-text-primary">{formulation.name}</p>
        <div className="flex shrink-0 flex-wrap justify-end gap-1">
          <button
            type="button"
            onClick={onExportExcel}
            title={t("formula.exportExcel")}
            className="rounded-lg border border-border px-2 py-1 text-[11px] font-semibold text-text-secondary transition hover:border-secondary/50 hover:bg-secondary/10 hover:text-secondary"
          >
            {t("formula.exportExcel")}
          </button>
          <button
            type="button"
            onClick={onExportPdf}
            title={t("formula.exportPdf")}
            className="rounded-lg border border-border px-2 py-1 text-[11px] font-semibold text-text-secondary transition hover:border-secondary/50 hover:bg-secondary/10 hover:text-secondary"
          >
            {t("formula.exportPdf")}
          </button>
          <button
            type="button"
            onClick={onExportCsv}
            title={t("formula.exportCsv")}
            className="rounded-lg border border-border px-2 py-1 text-[11px] font-semibold text-text-secondary transition hover:border-secondary/50 hover:bg-secondary/10 hover:text-secondary"
          >
            {t("formula.exportCsv")}
          </button>
          <button
            type="button"
            onClick={() => void onCopy()}
            className={`rounded-lg border px-2 py-1 text-[11px] font-semibold transition ${
              copied
                ? "border-success/40 bg-success/10 text-success"
                : "border-border text-secondary hover:border-secondary/50 hover:bg-secondary/10"
            }`}
          >
            {copied ? `✓ ${t("formula.copied")}` : t("formula.copy")}
          </button>
        </div>
      </div>

      <div className="mt-2 flex flex-wrap items-center gap-1.5">
        <span
          className={`rounded-md border px-2 py-0.5 text-[10px] font-bold ${
            baseComplete
              ? "border-success/40 bg-success/10 text-success"
              : "border-border bg-surface-sunken text-text-secondary"
          }`}
        >
          {t("worksheet.total")} {total != null ? `${total.toFixed(1)}%` : "—"}
        </span>
        <span className="rounded-md border border-secondary/30 bg-secondary/10 px-2 py-0.5 font-mono text-[10px] font-semibold text-secondary">
          {(formulation.confidence * 100).toFixed(0)}%
        </span>
        <a
          href={sourcePdfUrl(formulation.doc_id, formulation.pdf_page)}
          target="_blank"
          rel="noopener noreferrer"
          className="rounded-md border border-border bg-surface-sunken px-2 py-0.5 font-mono text-[10px] font-semibold text-text-secondary transition hover:text-secondary"
        >
          {t("evidence.openPdf")}{formulation.pdf_page}
        </a>
        <ComplianceBadge formulation={formulation} markets={brief?.markets} />
        <span className="rounded-md border border-border bg-[var(--panel-muted)] px-2 py-0.5 text-[10px] font-semibold text-text-secondary">
          {formulation.product_types.join(", ") || "general"}
        </span>
      </div>

      {/* spec rows */}
      <div className="mt-3 overflow-hidden rounded-xl border border-border">
        <div className="flex items-center gap-2 border-b border-border bg-surface-sunken px-3 py-2 text-[10px] font-bold uppercase tracking-wider text-text-tertiary">
          <span className="w-6 text-center">{t("worksheet.phase")}</span>
          <span className="flex-1">{t("formula.colIngredient")}</span>
          <span className="font-mono">{t("formula.colAmount")}</span>
        </div>
        <ul>
          {formulation.ingredients.map((ing, index) => {
            const phase = (ing.phase ?? "").trim();
            const color = phase ? phaseColors.get(phase) : undefined;
            return (
              <li
                key={`${ing.raw_name}-${index}`}
                className="flex items-center gap-2 border-b border-border/50 px-3 py-2 text-sm transition-colors last:border-b-0 hover:bg-secondary/5"
                style={color ? { boxShadow: `inset 3px 0 0 ${color}` } : undefined}
              >
                <span className="flex w-6 justify-center">
                  {phase ? (
                    <span
                      className="flex h-5 min-w-5 items-center justify-center rounded-md px-1 text-[10px] font-bold text-white"
                      style={{ background: color }}
                    >
                      {phase}
                    </span>
                  ) : (
                    <span className="text-text-tertiary">·</span>
                  )}
                </span>
                <span className="flex-1 truncate text-text-primary" title={ing.raw_name}>
                  {ing.raw_name}
                </span>
                <span className="shrink-0 font-mono text-xs tabular-nums text-text-secondary">
                  {ing.amount != null ? `${ing.amount}${ing.unit ?? ""}` : "—"}
                </span>
              </li>
            );
          })}
        </ul>
      </div>

      <BatchCalculator formulation={formulation} defaultBatchKg={brief?.batch_size} />
      <CostBadge formulationId={formulation.formulation_id} />
      <SubstitutionPanel formulation={formulation} brief={brief} />
    </div>
  );
}

const CONFIDENCE_DOT: Record<string, string> = {
  high: "bg-success",
  medium: "bg-warning",
  low: "bg-error",
  unknown: "bg-text-tertiary",
};

export function FormulaWorksheet({
  formulation,
  formulations,
  evidence,
  actions,
  onActionClick,
  brief,
}: FormulaWorksheetProps) {
  const { t } = useLocale();
  const list = (
    formulations && formulations.length > 0
      ? formulations
      : formulation
        ? [formulation]
        : []
  ).filter((f) => f.ingredients.length > 0);

  const [activeIdx, setActiveIdx] = useState(0);
  const active = list[Math.min(activeIdx, Math.max(0, list.length - 1))] ?? null;
  const hasContent = Boolean(active) || evidence.length > 0 || actions.length > 0;

  return (
    <div className="flex h-full min-h-0 flex-col">
      {/* header */}
      <div className="flex items-center gap-2.5 border-b border-border px-4 py-3.5 lg:px-5">
        <span
          aria-hidden
          className="flex h-8 w-8 items-center justify-center rounded-xl text-white"
          style={{ background: "var(--brand-gradient-vivid)" }}
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round">
            <path d="M9 3h6M10 3v6.5L4.5 19a2 2 0 0 0 1.8 3h11.4a2 2 0 0 0 1.8-3L14 9.5V3" />
          </svg>
        </span>
        <div className="min-w-0 leading-tight">
          <p className="eyebrow">{t("worksheet.subtitle")}</p>
          <h2 className="truncate text-sm font-bold text-text-primary">{t("worksheet.title")}</h2>
        </div>
        {active ? (
          <span className="ms-auto flex items-center gap-1.5 text-[10px] font-semibold text-success">
            <span className="relative flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-success opacity-50" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-success" />
            </span>
          </span>
        ) : null}
      </div>

      {!hasContent ? (
        <div className="flex flex-1 flex-col items-center justify-center gap-4 p-8 text-center">
          <div
            className="relative flex h-28 w-24 items-center justify-center rounded-xl border border-dashed border-border"
            style={{
              backgroundImage:
                "linear-gradient(var(--grid-line) 1px, transparent 1px), linear-gradient(90deg, var(--grid-line) 1px, transparent 1px)",
              backgroundSize: "12px 12px",
            }}
          >
            <svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="text-text-tertiary" aria-hidden>
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
              <path d="M14 2v6h6M8 13h8M8 17h5" />
            </svg>
          </div>
          <div className="max-w-[15rem]">
            <p className="text-sm font-bold text-text-primary">{t("worksheet.empty")}</p>
            <p className="mt-1.5 text-xs leading-relaxed text-text-secondary">{t("worksheet.emptyHint")}</p>
          </div>
        </div>
      ) : (
        // Keep overflow on a non-flex scroller so accordion growth always
        // contributes to scrollHeight (flex+transform stagger was clipping it).
        <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain p-3 lg:p-4">
          <div className="flex flex-col gap-3 pb-1">
            {/* formulation tabs */}
            {list.length > 1 ? (
              <div className="flex flex-wrap gap-1.5">
                {list.map((f, i) => (
                  <button
                    key={f.formulation_id}
                    type="button"
                    onClick={() => setActiveIdx(i)}
                    className={`max-w-[10rem] truncate rounded-lg px-2.5 py-1 text-xs font-semibold transition ${
                      i === activeIdx
                        ? "text-white"
                        : "border border-border bg-surface-sunken text-text-secondary hover:text-text-primary"
                    }`}
                    style={i === activeIdx ? { background: "var(--brand-gradient-vivid)" } : undefined}
                    title={f.name}
                  >
                    {f.name}
                  </button>
                ))}
              </div>
            ) : null}

            {active ? (
              <div className="surface-card shrink-0 p-3.5">
                <SpecSheet formulation={active} brief={brief} />
              </div>
            ) : null}

            {active && active.procedure && active.procedure.length > 0 ? (
              <Section
                title={t("formula.procedure")}
                icon={
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01" />
                  </svg>
                }
              >
                <ol className="list-decimal space-y-1.5 ps-4 text-xs leading-relaxed text-text-secondary">
                  {active.procedure.map((step, i) => (
                    <li key={i}>{step}</li>
                  ))}
                </ol>
              </Section>
            ) : null}

            {list.length >= 2 ? (
              <Section
                title={t("tools.compareTitle")}
                icon={
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M16 3h5v5M21 3l-7 7M8 21H3v-5M3 21l7-7" />
                  </svg>
                }
              >
                <FormulaComparePanel formulations={list} markets={brief?.markets} />
              </Section>
            ) : null}

            {evidence.length > 0 ? (
              <Section
                defaultOpen
                title={t("evidence.title")}
                badge={
                  <span className="rounded-full border border-border bg-surface px-2 py-0.5 text-[10px] font-bold text-text-secondary">
                    {evidence.length}
                  </span>
                }
                icon={
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
                    <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2Z" />
                  </svg>
                }
              >
                <ul className="space-y-2">
                  {evidence.map((item, index) => {
                    const pdfPage = item.pdf_page ?? item.page;
                    const href = pdfPage ? sourcePdfUrl(item.document_id, pdfPage) : sourcePdfUrl(item.document_id);
                    const dot = CONFIDENCE_DOT[item.confidence ?? "unknown"] ?? CONFIDENCE_DOT.unknown;
                    return (
                      <li
                        key={`${item.document_id}-${pdfPage ?? "na"}-${index}`}
                        className={`rounded-lg border bg-surface p-2.5 text-xs ${
                          item.quote_verified === false ? "border-warning/40" : "border-border"
                        }`}
                      >
                        <div className="flex items-center justify-between gap-2">
                          <span className="flex items-center gap-1.5 truncate font-semibold uppercase tracking-wide text-text-tertiary">
                            <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${dot}`} />
                            <span className="truncate">{item.document_id}</span>
                          </span>
                          {pdfPage ? (
                            <a
                              href={href}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="shrink-0 rounded-md border border-secondary/40 bg-secondary/10 px-1.5 py-0.5 font-mono text-[10px] font-semibold text-secondary transition hover:underline"
                            >
                              {t("evidence.openPdf")}{pdfPage}
                            </a>
                          ) : null}
                        </div>
                        <p className="mt-1.5 line-clamp-4 leading-relaxed text-text-primary">“{item.quote}”</p>
                      </li>
                    );
                  })}
                </ul>
              </Section>
            ) : null}

            {actions.length > 0 ? (
              <div className="surface-inset shrink-0 p-3.5">
                <p className="flex items-center gap-2 text-sm font-bold text-text-primary">
                  <span
                    aria-hidden
                    className="flex h-6 w-6 items-center justify-center rounded-lg text-secondary"
                    style={{ background: "color-mix(in srgb, var(--secondary) 12%, transparent)" }}
                  >
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M13 2 3 14h9l-1 8 10-12h-9l1-8Z" />
                    </svg>
                  </span>
                  {t("actions.title")}
                </p>
                <div className="mt-2.5 flex flex-wrap gap-2">
                  {actions.map((action, index) => (
                    <button
                      key={`${action.type}-${index}`}
                      type="button"
                      onClick={() => onActionClick(action)}
                      className="rounded-full border border-border bg-surface px-3 py-1.5 text-xs font-medium text-text-primary transition-all duration-200 hover:border-secondary/40 hover:bg-secondary/5 hover:text-secondary"
                    >
                      {action.label}
                    </button>
                  ))}
                </div>
              </div>
            ) : null}
          </div>
        </div>
      )}
    </div>
  );
}
