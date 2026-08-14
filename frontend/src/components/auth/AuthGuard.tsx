"use client";

import { useEffect, type ReactNode } from "react";
import { usePathname, useRouter } from "next/navigation";
import { Logo } from "@/components/ui/Logo";
import { Spinner } from "@/components/ui/Spinner";
import { useAuth } from "@/components/auth/AuthProvider";
import { useLocale } from "@/components/i18n/LocaleProvider";

function AuthSplash({ label }: { label: string }) {
  return (
    <div className="app-mesh-bg flex min-h-screen flex-col items-center justify-center px-6">
      <div className="glass-panel flex flex-col items-center gap-4 rounded-2xl px-8 py-8">
        <Logo size="lg" priority />
        <Spinner className="h-5 w-5" />
        <p className="text-sm text-text-secondary">{label}</p>
      </div>
    </div>
  );
}

export function AuthGuard({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const { t } = useLocale();

  useEffect(() => {
    if (!loading && !user) {
      const next = pathname && pathname !== "/login" ? `?next=${encodeURIComponent(pathname)}` : "";
      router.replace(`/login${next}`);
    }
  }, [loading, pathname, router, user]);

  if (loading) {
    return <AuthSplash label={t("auth.loading")} />;
  }
  if (!user) {
    return <AuthSplash label={t("auth.redirecting")} />;
  }
  return children;
}

export function GuestGuard({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  const router = useRouter();
  const { t } = useLocale();

  useEffect(() => {
    if (!loading && user) {
      const params = new URLSearchParams(window.location.search);
      const next = params.get("next");
      const target =
        next && next.startsWith("/") && !next.startsWith("//") ? next : "/chat";
      router.replace(target);
    }
  }, [loading, router, user]);

  if (loading) {
    return <AuthSplash label={t("auth.loading")} />;
  }
  if (user) {
    return <AuthSplash label={t("auth.loading")} />;
  }
  return children;
}
