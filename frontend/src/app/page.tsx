"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useState } from "react";
import { AppColors } from "@/constants/AppColors";
import { fetchBackendHealth, fetchBackendReadiness } from "@/lib/backend";
import { t } from "@/lib/i18n";

export default function Home() {
  const [status, setStatus] = useState("…");
  const [ready, setReady] = useState(false);

  useEffect(() => {
    fetchBackendHealth()
      .then((h) => setStatus(`${h.service}: ${h.status}`))
      .catch(() => setStatus("backend: unavailable"));

    fetchBackendReadiness()
      .then((r) => setReady(r.ready))
      .catch(() => setReady(false));
  }, []);

  return (
    <div className="app-mesh-bg flex min-h-screen items-center justify-center p-6">
      <main className="glass-panel animate-scale-in relative w-full max-w-2xl overflow-hidden rounded-3xl p-8 lg:p-10">
        <div
          className="pointer-events-none absolute -right-20 -top-20 h-56 w-56 rounded-full opacity-40 blur-3xl"
          style={{ background: AppColors.softGradient }}
        />
        <div className="relative animate-fade-in-down">
          <Image
            src="/logo_with_text.png"
            alt="Pharma AI"
            width={240}
            height={56}
            priority
            className="h-10 w-auto object-contain"
          />
        </div>
        <h1
          className="animate-fade-in-up relative mt-8 text-3xl font-bold tracking-tight text-text-primary"
          style={{ animationDelay: "80ms" }}
        >
          {t("home.title")}
        </h1>
        <p
          className="animate-fade-in-up relative mt-3 max-w-lg text-base leading-relaxed text-text-secondary"
          style={{ animationDelay: "140ms" }}
        >
          {t("home.subtitle")}
        </p>
        <div
          className="animate-fade-in-up relative mt-8 rounded-2xl border border-border/80 bg-background/60 p-4 backdrop-blur-sm"
          style={{ animationDelay: "200ms" }}
        >
          <p className="text-xs font-semibold uppercase tracking-wider text-text-secondary">
            {t("home.status")}
          </p>
          <p className="mt-1 flex items-center gap-2 text-lg font-semibold text-text-primary">
            <span
              className={`h-2 w-2 rounded-full ${ready ? "bg-success shadow-[0_0_8px_rgba(34,197,94,0.5)]" : "bg-warning animate-pulse"}`}
            />
            {status}
          </p>
        </div>
        <div
          className="animate-fade-in-up relative mt-8 flex flex-wrap gap-3"
          style={{ animationDelay: "260ms" }}
        >
          <Link
            href="/chat"
            className="btn-primary inline-flex rounded-xl px-6 py-3 text-sm font-semibold text-white shadow-lg"
            style={{ background: AppColors.buttonGradient }}
          >
            {t("home.openChat")}
          </Link>
          <Link
            href="/warehouse"
            className="hover-lift inline-flex rounded-xl border border-border bg-surface/80 px-6 py-3 text-sm font-semibold text-text-primary"
          >
            {t("home.openWarehouse")}
          </Link>
        </div>
      </main>
    </div>
  );
}
