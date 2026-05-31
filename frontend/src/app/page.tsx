import { fetchBackendHealth } from "@/lib/backend";
import Link from "next/link";
import Image from "next/image";
import { AppColors } from "@/constants/AppColors";

export default async function Home() {
  let backendStatus = "offline";

  try {
    const health = await fetchBackendHealth();
    backendStatus = `${health.service}: ${health.status}`;
  } catch {
    backendStatus = "backend: unavailable";
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background p-6">
      <main className="w-full max-w-2xl rounded-2xl border border-border bg-surface p-8 shadow-sm">
        <div className="flex items-center gap-3">
          <Image
            src="/logo_with_text.png"
            alt="Pharma AI logo with text"
            width={220}
            height={52}
            priority
            className="h-9 w-auto object-contain"
          />
        </div>
        <h1 className="mt-4 text-2xl font-semibold text-text-primary">Pharma AI Starter</h1>
        <p className="mt-2 text-text-secondary">
          Frontend and backend are connected with a basic health check.
        </p>
        <div className="mt-6 rounded-xl border border-border p-4">
          <p className="text-sm text-text-secondary">Backend status</p>
          <p className="mt-1 text-lg font-medium text-text-primary">
            {backendStatus}
          </p>
        </div>
        <div className="mt-6 flex items-center gap-3">
          <Link
            href="/chat"
            className="inline-flex rounded-lg px-4 py-2 text-sm font-medium text-white"
            style={{ backgroundColor: AppColors.primary }}
          >
            Open pharmacist chat
          </Link>
          <span
            className="inline-flex rounded-lg px-3 py-2 text-xs font-medium text-white"
            style={{ background: AppColors.gradient }}
          >
            AI Powered
          </span>
        </div>
      </main>
    </div>
  );
}
