import type { Metadata } from "next";
import { Manrope, JetBrains_Mono } from "next/font/google";
import "./globals.css";

const appSans = Manrope({
  variable: "--font-app-sans",
  subsets: ["latin"],
});

const appMono = JetBrains_Mono({
  variable: "--font-app-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Pharma AI",
  description: "Pharma AI formulation assistant",
};

// Synchronous theme bootstrap. Runs in <head> before the first paint so the
// user never sees a light/dark mismatch flash (FOUC).
const themeBootstrap = `(function(){try{var t=localStorage.getItem('pharma-ai-theme');var sys=window.matchMedia('(prefers-color-scheme: dark)').matches;var theme=(t==='dark'||t==='light')?t:(sys?'dark':'light');document.documentElement.classList.add(theme);}catch(_){}})();`;

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${appSans.variable} ${appMono.variable} h-full antialiased`}
      suppressHydrationWarning
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeBootstrap }} />
      </head>
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
