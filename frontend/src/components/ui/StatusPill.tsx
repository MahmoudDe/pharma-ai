interface StatusPillProps {
  label: string;
  variant: "checking" | "ok" | "warning" | "error";
  pulse?: boolean;
}

const DOT: Record<StatusPillProps["variant"], string> = {
  checking: "bg-warning",
  ok: "bg-success",
  warning: "bg-warning",
  error: "bg-error",
};

const TEXT: Record<StatusPillProps["variant"], string> = {
  checking: "text-warning",
  ok: "text-success",
  warning: "text-warning",
  error: "text-error",
};

export function StatusPill({ label, variant, pulse = false }: StatusPillProps) {
  return (
    <span
      className={`inline-flex max-w-[200px] items-center gap-1.5 truncate rounded-full border border-border/80 bg-background/80 px-2.5 py-1 text-xs font-medium backdrop-blur-sm ${TEXT[variant]}`}
      title={label}
    >
      <span
        className={`h-1.5 w-1.5 shrink-0 rounded-full ${DOT[variant]} ${
          pulse || variant === "checking" ? "animate-pulse" : ""
        } ${variant === "ok" ? "shadow-[0_0_8px_rgba(34,197,94,0.6)]" : ""}`}
      />
      <span className="truncate">{label}</span>
    </span>
  );
}
