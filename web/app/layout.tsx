import type { Metadata } from "next";
import { Fraunces, Atkinson_Hyperlegible, IBM_Plex_Mono } from "next/font/google";
import "./globals.css";
import { SiteHeader } from "@/components/SiteHeader";
import { ThemeInitScript } from "@/components/ThemeInitScript";

const heading = Fraunces({
  variable: "--font-heading",
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  display: "swap",
  fallback: ["Georgia", "Times New Roman", "serif"],
});

const body = Atkinson_Hyperlegible({
  variable: "--font-body",
  subsets: ["latin"],
  weight: ["400", "700"],
  display: "swap",
  fallback: ["Segoe UI", "Arial", "sans-serif"],
});

const mono = IBM_Plex_Mono({
  variable: "--font-mono",
  subsets: ["latin"],
  weight: ["400", "500"],
  display: "swap",
  fallback: ["SF Mono", "Consolas", "monospace"],
});

export const metadata: Metadata = {
  title: "Braille Press — circuit reading room",
  description:
    "A reading room for machine-read circuit diagrams: plain-language explanations and a teacher review workflow.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${heading.variable} ${body.variable} ${mono.variable}`}
      suppressHydrationWarning
    >
      <body>
        <ThemeInitScript />
        <a href="#main" className="skip-link">
          Skip to main content
        </a>
        <SiteHeader />
        <main id="main">{children}</main>
      </body>
    </html>
  );
}
