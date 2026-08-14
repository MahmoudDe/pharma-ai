"use client";

import { useMemo, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { AppColors } from "@/constants/AppColors";
import { AuthGuard } from "@/components/auth/AuthGuard";
import { PasswordField } from "@/components/auth/PasswordField";
import { useAuth } from "@/components/auth/AuthProvider";
import { UserAvatar } from "@/components/auth/UserAvatar";
import { useLocale } from "@/components/i18n/LocaleProvider";
import { AppHeader } from "@/components/ui/AppHeader";
import { Spinner } from "@/components/ui/Spinner";

function formatMemberSince(iso: string | null, locale: string): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleDateString(locale === "ar" ? "ar" : "en", {
      year: "numeric",
      month: "long",
      day: "numeric",
    });
  } catch {
    return iso;
  }
}

function ProfileContent() {
  const { t, locale } = useLocale();
  const { user, updateProfile, updatePassword, deleteAccount, logout } = useAuth();
  const router = useRouter();
  const [name, setName] = useState(user?.name ?? "");
  const [email, setEmail] = useState(user?.email ?? "");
  const [profileMessage, setProfileMessage] = useState<string | null>(null);
  const [profileError, setProfileError] = useState<string | null>(null);
  const [profileBusy, setProfileBusy] = useState(false);

  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [passwordMessage, setPasswordMessage] = useState<string | null>(null);
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [passwordBusy, setPasswordBusy] = useState(false);

  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deleteEmail, setDeleteEmail] = useState("");
  const [deletePassword, setDeletePassword] = useState("");
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [deleteBusy, setDeleteBusy] = useState(false);

  const memberSince = useMemo(
    () => formatMemberSince(user?.created_at ?? null, locale),
    [locale, user?.created_at],
  );

  if (!user) return null;

  const saveProfile = async (event: FormEvent) => {
    event.preventDefault();
    setProfileError(null);
    setProfileMessage(null);
    setProfileBusy(true);
    try {
      await updateProfile(name.trim(), email.trim());
      setProfileMessage(t("auth.profileSaved"));
    } catch (err) {
      setProfileError(err instanceof Error ? err.message : t("auth.genericError"));
    } finally {
      setProfileBusy(false);
    }
  };

  const savePassword = async (event: FormEvent) => {
    event.preventDefault();
    setPasswordError(null);
    setPasswordMessage(null);
    if (newPassword !== confirmPassword) {
      setPasswordError(t("auth.passwordMismatch"));
      return;
    }
    setPasswordBusy(true);
    try {
      await updatePassword(currentPassword, newPassword, confirmPassword);
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      setPasswordMessage(t("auth.passwordChanged"));
    } catch (err) {
      setPasswordError(err instanceof Error ? err.message : t("auth.genericError"));
    } finally {
      setPasswordBusy(false);
    }
  };

  const confirmDelete = async (event: FormEvent) => {
    event.preventDefault();
    setDeleteError(null);
    if (deleteEmail.trim().toLowerCase() !== user.email.toLowerCase()) {
      setDeleteError(t("auth.deleteEmailMismatch"));
      return;
    }
    setDeleteBusy(true);
    try {
      await deleteAccount(deletePassword);
      router.replace("/");
    } catch (err) {
      setDeleteError(err instanceof Error ? err.message : t("auth.genericError"));
    } finally {
      setDeleteBusy(false);
    }
  };

  return (
    <div className="app-mesh-bg min-h-screen">
      <AppHeader active="profile" />
      <main className="mx-auto w-full max-w-3xl px-5 py-8 lg:px-8">
        <section className="overflow-hidden rounded-3xl border border-border bg-surface shadow-soft">
          <div
            className="relative px-6 py-8 sm:px-8"
            style={{ background: AppColors.softGradient }}
          >
            <div className="flex flex-wrap items-center gap-5">
              <UserAvatar name={user.name} size="lg" />
              <div className="min-w-0">
                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-text-secondary">
                  {t("auth.profileEyebrow")}
                </p>
                <h1 className="mt-1 truncate text-2xl font-extrabold text-text-primary">
                  {user.name}
                </h1>
                <p className="mt-1 text-sm text-text-secondary">
                  {t("auth.memberSince")} {memberSince}
                </p>
              </div>
            </div>
          </div>
        </section>

        <section className="mt-6 rounded-3xl border border-border bg-surface p-6 shadow-sm sm:p-8">
          <h2 className="text-lg font-bold text-text-primary">{t("auth.accountDetails")}</h2>
          <p className="mt-1 text-sm text-text-secondary">{t("auth.profileSubtitle")}</p>
          <form onSubmit={(event) => void saveProfile(event)} className="mt-6 grid gap-4">
            {profileError ? (
              <div className="rounded-xl border border-error/30 bg-error/10 px-3.5 py-2.5 text-sm text-error">
                {profileError}
              </div>
            ) : null}
            {profileMessage ? (
              <div className="rounded-xl border border-success/30 bg-success/10 px-3.5 py-2.5 text-sm text-success">
                {profileMessage}
              </div>
            ) : null}
            <div>
              <label htmlFor="profile-name" className="field-label">
                {t("auth.name")}
              </label>
              <input
                id="profile-name"
                className="field-input"
                value={name}
                onChange={(event) => setName(event.target.value)}
                autoComplete="name"
                required
              />
            </div>
            <div>
              <label htmlFor="profile-email" className="field-label">
                {t("auth.email")}
              </label>
              <input
                id="profile-email"
                type="email"
                className="field-input"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                autoComplete="email"
                required
              />
            </div>
            <div className="flex justify-end">
              <button
                type="submit"
                disabled={profileBusy}
                className="btn-primary inline-flex items-center gap-2 rounded-xl px-5 py-2.5 text-sm font-semibold"
              >
                {profileBusy ? <Spinner className="h-4 w-4 text-white" /> : null}
                {t("auth.saveProfile")}
              </button>
            </div>
          </form>
        </section>

        <section className="mt-6 rounded-3xl border border-border bg-surface p-6 shadow-sm sm:p-8">
          <h2 className="text-lg font-bold text-text-primary">{t("auth.security")}</h2>
          <p className="mt-1 text-sm text-text-secondary">{t("auth.passwordHint")}</p>
          <form onSubmit={(event) => void savePassword(event)} className="mt-6 grid gap-4">
            {passwordError ? (
              <div className="rounded-xl border border-error/30 bg-error/10 px-3.5 py-2.5 text-sm text-error">
                {passwordError}
              </div>
            ) : null}
            {passwordMessage ? (
              <div className="rounded-xl border border-success/30 bg-success/10 px-3.5 py-2.5 text-sm text-success">
                {passwordMessage}
              </div>
            ) : null}
            <PasswordField
              id="current-password"
              name="current_password"
              label={t("auth.currentPassword")}
              value={currentPassword}
              onChange={setCurrentPassword}
              autoComplete="current-password"
              required
            />
            <PasswordField
              id="new-password"
              name="password"
              label={t("auth.newPassword")}
              value={newPassword}
              onChange={setNewPassword}
              autoComplete="new-password"
              placeholder={t("auth.passwordPlaceholder")}
              required
            />
            <PasswordField
              id="confirm-password"
              name="password_confirmation"
              label={t("auth.confirmPassword")}
              value={confirmPassword}
              onChange={setConfirmPassword}
              autoComplete="new-password"
              invalid={confirmPassword.length > 0 && confirmPassword !== newPassword}
            />
            <div className="flex justify-end">
              <button
                type="submit"
                disabled={passwordBusy}
                className="btn-primary inline-flex items-center gap-2 rounded-xl px-5 py-2.5 text-sm font-semibold"
              >
                {passwordBusy ? <Spinner className="h-4 w-4 text-white" /> : null}
                {t("auth.changePassword")}
              </button>
            </div>
          </form>
        </section>

        <section className="mt-6 mb-10 rounded-3xl border border-error/25 bg-surface p-6 shadow-sm sm:p-8">
          <h2 className="text-lg font-bold text-error">{t("auth.dangerZone")}</h2>
          <p className="mt-1 max-w-xl text-sm text-text-secondary">{t("auth.deleteAccountHint")}</p>
          <div className="mt-5 flex flex-wrap gap-3">
            <button
              type="button"
              className="btn-ghost rounded-xl px-4 py-2.5 text-sm font-semibold"
              onClick={async () => {
                await logout();
                router.push("/");
              }}
            >
              {t("auth.logout")}
            </button>
            <button
              type="button"
              className="btn-danger rounded-xl px-4 py-2.5 text-sm font-semibold"
              onClick={() => {
                setDeleteOpen(true);
                setDeleteError(null);
              }}
            >
              {t("auth.deleteAccount")}
            </button>
          </div>
        </section>
      </main>

      {deleteOpen ? (
        <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/45 p-4 sm:items-center">
          <form
            onSubmit={(event) => void confirmDelete(event)}
            className="w-full max-w-md rounded-3xl border border-border bg-surface p-6 shadow-panel"
          >
            <h3 className="text-lg font-bold text-text-primary">{t("auth.deleteConfirmTitle")}</h3>
            <p className="mt-2 text-sm leading-relaxed text-text-secondary">
              {t("auth.deleteConfirmBody")}
            </p>
            {deleteError ? (
              <div className="mt-4 rounded-xl border border-error/30 bg-error/10 px-3.5 py-2.5 text-sm text-error">
                {deleteError}
              </div>
            ) : null}
            <div className="mt-5">
              <label htmlFor="delete-email" className="field-label">
                {t("auth.deleteConfirmLabel", { email: user.email })}
              </label>
              <input
                id="delete-email"
                className="field-input"
                value={deleteEmail}
                onChange={(event) => setDeleteEmail(event.target.value)}
                autoComplete="off"
                placeholder={user.email}
              />
            </div>
            <div className="mt-4">
              <PasswordField
                id="delete-password"
                name="delete_password"
                label={t("auth.requiredPassword")}
                value={deletePassword}
                onChange={setDeletePassword}
                autoComplete="current-password"
                required
              />
            </div>
            <div className="mt-6 flex flex-wrap justify-end gap-2">
              <button
                type="button"
                className="btn-ghost rounded-xl px-4 py-2.5 text-sm font-semibold"
                onClick={() => setDeleteOpen(false)}
              >
                {t("auth.deleteCancel")}
              </button>
              <button
                type="submit"
                disabled={deleteBusy}
                className="btn-danger inline-flex items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-semibold"
              >
                {deleteBusy ? <Spinner className="h-4 w-4" /> : null}
                {t("auth.deleteConfirmAction")}
              </button>
            </div>
          </form>
        </div>
      ) : null}
    </div>
  );
}

export default function ProfilePage() {
  return (
    <AuthGuard>
      <ProfileContent />
    </AuthGuard>
  );
}
