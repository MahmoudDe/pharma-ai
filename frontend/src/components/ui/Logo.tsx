import Image from "next/image";

type LogoSize = "sm" | "header" | "lg";

const SIZE_CONFIG: Record<
  LogoSize,
  { containerClass: string; width: number; height: number }
> = {
  sm: { containerClass: "logo-container--sm", width: 24, height: 24 },
  header: { containerClass: "logo-container--header", width: 26, height: 26 },
  lg: { containerClass: "logo-container-lg", width: 56, height: 56 },
};

interface LogoProps {
  size?: LogoSize;
  alt?: string;
  className?: string;
  active?: boolean;
  priority?: boolean;
  ring?: boolean;
}

export function Logo({
  size = "header",
  alt = "Pharma AI",
  className = "",
  active = false,
  priority = false,
  ring = false,
}: LogoProps) {
  const { containerClass, width, height } = SIZE_CONFIG[size];

  return (
    <div
      className={[
        "logo-container",
        containerClass,
        active ? "avatar-active" : "",
        ring ? "ring-gradient" : "",
        className,
      ]
        .filter(Boolean)
        .join(" ")}
      aria-hidden={alt === "" ? true : undefined}
    >
      <Image
        src="/logo.png"
        alt={alt}
        width={width}
        height={height}
        className="logo-img h-full w-full object-contain"
        priority={priority}
      />
    </div>
  );
}
