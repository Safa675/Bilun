import type { Metadata, Viewport } from "next";
import { Suspense } from "react";
import { Fraunces, Inter } from "next/font/google";
import AppTopBar from "@/components/shell/AppTopBar";
import { ConfigProvider } from "@/lib/configContext";
import { SUT_BRAND } from "@/lib/constants";
import { ShellStateProviders } from "@/stores/providers";
import "./globals.css";
import "./styles/sut-how-modal.css";

const fontDisplay = Fraunces({
  subsets: ["latin"],
  variable: "--font-display",
  weight: ["400", "500", "700"],
  style: ["normal", "italic"],
  display: "swap",
});

const fontSans = Inter({
  subsets: ["latin"],
  variable: "--font-sans",
  weight: ["400", "500", "600", "700"],
  display: "swap",
});

export const metadata: Metadata = {
  title: SUT_BRAND.metaTitle,
  description: SUT_BRAND.metaDescription,
};

export const viewport: Viewport = {
  themeColor: "#FFFFFF",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={`${fontDisplay.variable} ${fontSans.variable}`}>
      <body className="antialiased" suppressHydrationWarning>
        <a
          href="#main-content"
          className="sr-only focus:not-sr-only focus:absolute focus:top-4 focus:left-4 focus:z-[9999] focus:bg-white focus:px-4 focus:py-2 focus:rounded-lg focus:shadow-lg focus:text-[var(--text-primary)] focus:font-semibold"
        >
          Skip to main content
        </a>
        <ConfigProvider>
          <ShellStateProviders>
            <Suspense>
              <AppTopBar />
            </Suspense>
            {children}
          </ShellStateProviders>
        </ConfigProvider>
      </body>
    </html>
  );
}
