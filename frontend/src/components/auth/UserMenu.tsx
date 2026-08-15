"use client";

import Link from "next/link";
import { useEffect, useId, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useRouter } from "next/navigation";
import { useAuth } from "@/components/auth/AuthProvider";
import { UserAvatar } from "@/components/auth/UserAvatar";
import { useLocale } from "@/components/i18n/LocaleProvider";

export function UserMenu({ compact = false }: { compact?: boolean }) {
  const { user, logout } = useAuth();
  const { t } = useLocale();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [mounted, setMounted] = useState(false);
  const [menuPos, setMenuPos] = useState<{ top: number; left: number } | null>(null);
  const rootRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const menuId = useId();

  useEffect(() => setMounted(true), []);

  const updatePosition = () => {
    const btn = buttonRef.current;
    if (!btn) return;
    const rect = btn.getBoundingClientRect();
    const menuWidth = 256; // w-64
    const gap = 8;
    const isRtl = document.documentElement.dir === "rtl";
    let left = isRtl ? rect.left : rect.right - menuWidth;
    left = Math.max(8, Math.min(left, window.innerWidth - menuWidth - 8));
    setMenuPos({ top: rect.bottom + gap, left });
  };

  useEffect(() => {
    if (!open) return;

    updatePosition();

    const onPointer = (event: MouseEvent) => {
      const target = event.target as Node;
      if (rootRef.current?.contains(target) || menuRef.current?.contains(target)) {
        return;
      }
      setOpen(false);
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };

    window.addEventListener("resize", updatePosition);
    window.addEventListener("scroll", updatePosition, true);
    document.addEventListener("mousedown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("resize", updatePosition);
      window.removeEventListener("scroll", updatePosition, true);
      document.removeEventListener("mousedown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  if (!user) return null;

  const menu =
    open && mounted && menuPos
      ? createPortal(
          <div
            ref={menuRef}
            id={menuId}
            role="menu"
            style={{ top: menuPos.top, left: menuPos.left }}
            className="fixed z-[200] w-64 overflow-hidden rounded-2xl border border-border bg-surface shadow-[var(--shadow-panel)]"
          >
            <div className="border-b border-border px-4 py-3">
              <p className="truncate text-sm font-semibold text-text-primary">{user.name}</p>
              <p className="truncate text-xs text-text-secondary">{user.email}</p>
            </div>
            <div className="p-1.5">
              <Link
                href="/profile"
                role="menuitem"
                onClick={() => setOpen(false)}
                className="block rounded-xl px-3 py-2 text-sm font-medium text-text-primary transition-colors hover:bg-[var(--panel-muted)]"
              >
                {t("auth.profile")}
              </Link>
              <button
                type="button"
                role="menuitem"
                className="block w-full rounded-xl px-3 py-2 text-start text-sm font-medium text-text-primary transition-colors hover:bg-[var(--panel-muted)]"
                onClick={async () => {
                  setOpen(false);
                  await logout();
                  router.push("/");
                }}
              >
                {t("auth.logout")}
              </button>
            </div>
          </div>,
          document.body,
        )
      : null;

  return (
    <div ref={rootRef} className="relative z-20 shrink-0">
      <button
        ref={buttonRef}
        type="button"
        onClick={() => {
          if (!open) updatePosition();
          setOpen((current) => !current);
        }}
        aria-expanded={open}
        aria-haspopup="menu"
        aria-controls={open ? menuId : undefined}
        aria-label={user.name}
        className={
          compact
            ? "inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-border bg-surface/80 shadow-sm transition-all duration-200 hover:border-secondary/40 hover:shadow-[var(--shadow-glow)]"
            : "flex h-9 shrink-0 items-center gap-2 rounded-xl border border-border bg-surface/80 p-0.5 pe-2.5 shadow-sm transition-all duration-200 hover:border-secondary/40 hover:shadow-[var(--shadow-glow)]"
        }
      >
        <UserAvatar name={user.name} size="sm" />
        {compact ? null : (
          <span className="hidden max-w-[8rem] truncate text-xs font-semibold text-text-primary sm:block">
            {user.name}
          </span>
        )}
      </button>
      {menu}
    </div>
  );
}
