export const AppColors = {
  primary: "#0B0B6E",
  secondary: "#7C4ADC",
  secondaryDark: "#6F49D9",
  accent: "#21CDF0",
  background: "#EEF1F9",
  surface: "#FFFFFF",
  textPrimary: "#141A2E",
  textSecondary: "#5D6B86",
  border: "#E1E6F2",
  success: "#16B364",
  warning: "#F59E0B",
  error: "#EF4444",
  // Signature gradient — kept in sync with --brand-gradient* tokens in globals.css.
  gradient:
    "linear-gradient(115deg, #5B2BD6 0%, #7C4ADC 32%, #5566E6 64%, #21CDF0 100%)",
  softGradient:
    "linear-gradient(115deg, rgba(124,74,220,0.14) 0%, rgba(85,102,230,0.12) 55%, rgba(33,205,240,0.14) 100%)",
  buttonGradient:
    "linear-gradient(115deg, #0B0B6E 0%, #4F2FB5 38%, #7C4ADC 68%, #21CDF0 100%)",
} as const;
