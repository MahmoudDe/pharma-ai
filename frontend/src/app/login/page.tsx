"use client";

import Link from "next/link";
import { Suspense, useState, type FormEvent } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { AuthShell } from "@/components/auth/AuthShell";
import { GuestGuard } from "@/components/auth/AuthGuard";
import { PasswordField } from "@/components/auth/PasswordField";
import { useAuth } from "@/components/auth/AuthProvider";
import { useLocale } from "@/components/i18n/LocaleProvider";
import { Spinner } from "@/components/ui/Spinner";

function safeNext(raw: string | null): string {
  if (!raw || !raw.startsWith("/") || raw.startsWith("//")) return "/chat";
  return raw;
}

function LoginForm() {
  const { t } = useLocale();
  const { login } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await login(email.trim(), password);
      router.replace(safeNext(searchParams.get("next")));
    } catch (err) {
      setError(err instanceof Error ? err.message : t("auth.genericError"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={(event) => void handleSubmit(event)} className="space-y-4">
      {error ? (
        <div className="rounded-xl border border-error/30 bg-error/10 px-3.5 py-2.5 text-sm text-error">
          {error}
        </div>
      ) : null}
      <div>
        <label htmlFor="email" className="field-label">
          {t("auth.email")}
        </label>
        <input
          id="email"
          name="email"
          type="email"
          autoComplete="email"
          required
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          placeholder={t("auth.emailPlaceholder")}
          className="field-input"
        />
      </div>
      <PasswordField
        id="password"
        name="password"
        label={t("auth.password")}
        value={password}
        onChange={setPassword}
        placeholder={t("auth.passwordPlaceholder")}
        autoComplete="current-password"
        required
      />
      <button type="submit" disabled={busy} className="btn-primary mt-2 flex w-full items-center justify-center gap-2 rounded-xl px-4 py-3 text-sm font-semibold">
        {busy ? <Spinner className="h-4 w-4 text-white" /> : null}
        {busy ? t("auth.submitting") : t("auth.submitLogin")}
      </button>
      <p className="pt-2 text-center text-sm text-text-secondary">
        {t("auth.noAccount")}{" "}
        <Link href="/register" className="font-semibold text-secondary hover:underline">
          {t("auth.createOne")}
        </Link>
      </p>
    </form>
  );
}

export default function LoginPage() {
  const { t } = useLocale();
  return (
    <GuestGuard>
      <AuthShell title={t("auth.welcomeBack")} subtitle={t("auth.welcomeBackSubtitle")}>
        <Suspense
          fallback={
            <div className="flex justify-center py-8">
              <Spinner />
            </div>
          }
        >
          <LoginForm />
        </Suspense>
      </AuthShell>
    </GuestGuard>
  );
}
