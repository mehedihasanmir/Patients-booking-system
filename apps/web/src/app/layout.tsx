import type { ReactNode } from "react";
import { Fraunces, Noto_Sans_Bengali, Outfit } from "next/font/google";
import { getLocale } from "next-intl/server";
import "./globals.css";

const display = Fraunces({ subsets: ["latin"], variable: "--font-display", display: "swap" });
const sans = Outfit({ subsets: ["latin"], variable: "--font-sans", display: "swap" });
const bn = Noto_Sans_Bengali({
  subsets: ["bengali"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-bn",
  display: "swap",
});

export default async function RootLayout({ children }: { children: ReactNode }) {
  let locale = "bn";
  try {
    locale = await getLocale();
  } catch {
    locale = "bn";
  }
  return (
    <html lang={locale} className={`${display.variable} ${sans.variable} ${bn.variable}`}>
      <body className="font-sans text-ink antialiased">{children}</body>
    </html>
  );
}
