"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { AppColors } from "@/constants/AppColors";
import { AuthShell } from "@/components/auth/AuthShell";
import { GuestGuard } from "@/components/auth/AuthGuard";
import { PasswordField, passwordStrength } from "@/components/auth/PasswordField";
import { useAuth } from "@/components/auth/AuthProvider";
import { useLocale } from "@/components/i18n/LocaleProvider";
import { Spinner } from "@/components/ui/Spinner";
import type { TranslationKey } from "@/lib/i18n";

const STRENGTH_LABELS: TranslationKey[] = [
  "auth.strengthWeak",
  "auth.strengthWeak",
  "auth.strengthOk",
  "auth.strengthStrong",
];
const STRENGTH_COLORS = [AppColors.error, AppColors.error, AppColors.warning, AppColors.success];

export default function RegisterPage() {
  const { t } = useLocale();
  const { register } = useAuth();
  const router = useRouter();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const strength = passwordStrength(password);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    if (password !== confirm) {
      setError(t("auth.passwordMismatch"));
      return;
    }
    setBusy(true);
    try {
      await register(name.trim(), email.trim(), password, confirm);
      router.replace("/chat");
    } catch (err) {
      setError(err instanceof Error ? err.message : t("auth.genericError"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <GuestGuard>
      <AuthShell title={t("auth.createTitle")} subtitle={t("auth.createSubtitle")}>
        <form onSubmit={(event) => void handleSubmit(event)} className="space-y-4">
          {error ? (
            <div className="rounded-xl border border-error/30 bg-error/10 px-3.5 py-2.5 text-sm text-error">
              {error}
            </div>
          ) : null}
          <div>
            <label htmlFor="name" className="field-label">
              {t("auth.name")}
            </label>
            <input
              id="name"
              name="name"
              type="text"
              autoComplete="name"
              required
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder={t("auth.namePlaceholder")}
              className="field-input"
            />
          </div>
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
            autoComplete="new-password"
            required
          />
          {password ? (
            <div>
              <div className="mb-1.5 flex items-center justify-between text-[11px] font-semibold">
                <span className="text-text-secondary">{t("auth.passwordStrength")}</span>
                <span style={{ color: STRENGTH_COLORS[strength] }}>{t(STRENGTH_LABELS[strength])}</span>
              </div>
              <div className="grid grid-cols-3 gap-1.5">
                {[1, 2, 3].map((level) => (
                  <span
                    key={level}
                    className="h-1.5 rounded-full bg-border"
                    style={
                      strength >= level ? { background: STRENGTH_COLORS[strength] } : undefined
                    }
                  />
                ))}
              </div>
            </div>
          ) : null}
          <PasswordField
            id="password_confirmation"
            name="password_confirmation"
            label={t("auth.confirmPassword")}
            value={confirm}
            onChange={setConfirm}
            placeholder={t("auth.confirmPassword")}
            autoComplete="new-password"
            invalid={confirm.length > 0 && confirm !== password}
            required
          />
          <button
            type="submit"
            disabled={busy}
            className="btn-primary mt-2 flex w-full items-center justify-center gap-2 rounded-xl px-4 py-3 text-sm font-semibold"
          >
            {busy ? <Spinner className="h-4 w-4 text-white" /> : null}
            {busy ? t("auth.submitting") : t("auth.submitRegister")}
          </button>
          <p className="pt-2 text-center text-sm text-text-secondary">
            {t("auth.hasAccount")}{" "}
            <Link href="/login" className="font-semibold text-secondary hover:underline">
              {t("auth.signInInstead")}
            </Link>
          </p>
        </form>
      </AuthShell>
    </GuestGuard>
  );
}
