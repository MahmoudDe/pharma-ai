import type { ReactNode } from "react";

function IconFrame({ children }: { children: ReactNode }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
      className="h-full w-full"
    >
      {children}
    </svg>
  );
}

export function ChatIcon() {
  return (
    <IconFrame>
      <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5Z" />
    </IconFrame>
  );
}

export function LibraryIcon() {
  return (
    <IconFrame>
      <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
      <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2Z" />
    </IconFrame>
  );
}

export function WarehouseIcon() {
  return (
    <IconFrame>
      <path d="M21 8v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8" />
      <path d="m2 8 10-5 10 5" />
      <path d="M8 21v-7h8v7" />
    </IconFrame>
  );
}

export function CorpusIcon() {
  return (
    <IconFrame>
      <ellipse cx="12" cy="5" rx="8" ry="3" />
      <path d="M4 5v6c0 1.66 3.58 3 8 3s8-1.34 8-3V5" />
      <path d="M4 11v6c0 1.66 3.58 3 8 3s8-1.34 8-3v-6" />
    </IconFrame>
  );
}

export function CiteIcon() {
  return (
    <IconFrame>
      <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
      <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2Z" />
      <path d="M10 8h6" />
      <path d="M10 12h4" />
    </IconFrame>
  );
}

export function SheetIcon() {
  return (
    <IconFrame>
      <path d="M8 6h13" />
      <path d="M8 12h13" />
      <path d="M8 18h13" />
      <path d="M3 6h.01" />
      <path d="M3 12h.01" />
      <path d="M3 18h.01" />
    </IconFrame>
  );
}

export function ShieldIcon() {
  return (
    <IconFrame>
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z" />
      <path d="m9 12 2 2 4-4" />
    </IconFrame>
  );
}

export function CostIcon() {
  return (
    <IconFrame>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v10" />
      <path d="M9.5 10.5c.4-.9 1.3-1.5 2.5-1.5 1.4 0 2.5.8 2.5 2s-1.1 2-2.5 2c-1.4 0-2.5.8-2.5 2s1.1 2 2.5 2c1.2 0 2.1-.6 2.5-1.5" />
    </IconFrame>
  );
}

export function SwapIcon() {
  return (
    <IconFrame>
      <path d="M16 3h5v5" />
      <path d="m21 3-7 7" />
      <path d="M8 21H3v-5" />
      <path d="m3 21 7-7" />
    </IconFrame>
  );
}

export function BatchIcon() {
  return (
    <IconFrame>
      <path d="M4 20h16" />
      <path d="M6 20V10l6-4 6 4v10" />
      <path d="M9 20v-6h6v6" />
    </IconFrame>
  );
}

export function LockIcon() {
  return (
    <IconFrame>
      <rect x="5" y="11" width="14" height="10" rx="2" />
      <path d="M8 11V8a4 4 0 0 1 8 0v3" />
    </IconFrame>
  );
}

export function LangIcon() {
  return (
    <IconFrame>
      <circle cx="12" cy="12" r="9" />
      <path d="M3 12h18" />
      <path d="M12 3a15 15 0 0 1 0 18" />
      <path d="M12 3a15 15 0 0 0 0 18" />
    </IconFrame>
  );
}

export function ArrowIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden className="h-3.5 w-3.5 rtl:rotate-180">
      <path d="M5 12h14" />
      <path d="m13 6 6 6-6 6" />
    </svg>
  );
}
