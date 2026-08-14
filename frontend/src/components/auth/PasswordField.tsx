"use client";

import { useState } from "react";
import { useLocale } from "@/components/i18n/LocaleProvider";

export function PasswordField({
  id,
  name,
  value,
  onChange,
  placeholder,
  autoComplete,
  invalid,
  label,
  required,
}: {
  id: string;
  name: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  autoComplete?: string;
  invalid?: boolean;
  label: string;
  required?: boolean;
}) {
  const { t } = useLocale();
  const [visible, setVisible] = useState(false);

  return (
    <div>
      <label htmlFor={id} className="field-label">
        {label}
      </label>
      <div className="relative">
        <input
          id={id}
          name={name}
          type={visible ? "text" : "password"}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          placeholder={placeholder}
          autoComplete={autoComplete}
          aria-invalid={invalid || undefined}
          required={required}
          className="field-input pe-12"
        />
        <button
          type="button"
          className="absolute end-2 top-1/2 -translate-y-1/2 rounded-lg px-2 py-1 text-[11px] font-semibold text-text-secondary transition-colors hover:text-text-primary"
          onClick={() => setVisible((current) => !current)}
          aria-label={visible ? t("auth.hidePassword") : t("auth.showPassword")}
        >
          {visible ? t("auth.hidePassword") : t("auth.showPassword")}
        </button>
      </div>
    </div>
  );
}

export function passwordStrength(password: string): 0 | 1 | 2 | 3 {
  if (!password) return 0;
  let score = 0;
  if (password.length >= 8) score += 1;
  if (/[A-Z]/.test(password) && /[a-z]/.test(password)) score += 1;
  if (/\d/.test(password) || /[^A-Za-z0-9]/.test(password)) score += 1;
  return score as 0 | 1 | 2 | 3;
}
