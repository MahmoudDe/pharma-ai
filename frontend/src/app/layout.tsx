import type { Metadata } from "next";
import { IBM_Plex_Sans_Arabic, JetBrains_Mono, Manrope } from "next/font/google";
import { cookies } from "next/headers";
import { Providers } from "@/components/Providers";
import { LOCALE_COOKIE_NAME, parseLocale, type Locale } from "@/lib/i18n";
import "./globals.css";

const appSans = Manrope({
  variable: "--font-app-sans",
  subsets: ["latin"],
});

const appSansArabic = IBM_Plex_Sans_Arabic({
  variable: "--font-app-arabic",
  subsets: ["arabic"],
  weight: ["400", "500", "600", "700"],
});

const appMono = JetBrains_Mono({
  variable: "--font-app-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Pharma AI",
  description:
    "Pharmaceutical manufacturing assistant — cited answers, structured formulas, and warehouse matching.",
};

// Synchronous theme bootstrap. Runs in <head> before the first paint so the
// user never sees a light/dark mismatch flash (FOUC).
const themeBootstrap = `(function(){try{var t=localStorage.getItem('pharma-ai-theme');var sys=window.matchMedia('(prefers-color-scheme: dark)').matches;var theme=(t==='dark'||t==='light')?t:(sys?'dark':'light');document.documentElement.classList.add(theme);}catch(_){}})();`;

const localeBootstrap = `(function(){try{var k='pharma-ai-locale';var l=localStorage.getItem(k);if(l==='ar'||l==='en'){document.documentElement.lang=l;document.documentElement.dir=l==='ar'?'rtl':'ltr';document.cookie=k+'='+l+';path=/;max-age=31536000;SameSite=Lax';}}catch(_){}})();`;

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const cookieStore = await cookies();
  const initialLocale: Locale = parseLocale(cookieStore.get(LOCALE_COOKIE_NAME)?.value);

  return (
    <html
      lang={initialLocale}
      dir={initialLocale === "ar" ? "rtl" : "ltr"}
      className={`${appSans.variable} ${appSansArabic.variable} ${appMono.variable} h-full antialiased`}
      suppressHydrationWarning
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeBootstrap }} />
        <script dangerouslySetInnerHTML={{ __html: localeBootstrap }} />
      </head>
      <body className="min-h-full flex flex-col">
        <Providers initialLocale={initialLocale}>{children}</Providers>
      </body>
    </html>
  );
}
