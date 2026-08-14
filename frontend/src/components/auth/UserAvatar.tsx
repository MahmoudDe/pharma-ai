import { AppColors } from "@/constants/AppColors";

function initialsFromName(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  return parts
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("");
}

export function UserAvatar({
  name,
  size = "md",
}: {
  name: string;
  size?: "sm" | "md" | "lg";
}) {
  const sizeClass =
    size === "lg"
      ? "h-16 w-16 text-xl"
      : size === "sm"
        ? "h-8 w-8 text-[11px]"
        : "h-9 w-9 text-xs";

  return (
    <span
      className={`${sizeClass} inline-flex items-center justify-center rounded-xl font-bold text-white shadow-sm`}
      style={{ background: AppColors.buttonGradient }}
      aria-hidden
    >
      {initialsFromName(name)}
    </span>
  );
}
