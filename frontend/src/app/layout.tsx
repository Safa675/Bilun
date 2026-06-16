import type { Metadata, Viewport } from "next";
import { cookies } from "next/headers";
import { Suspense } from "react";
import { Fraunces, Inter } from "next/font/google";
import AppTopBar from "@/components/shell/AppTopBar";
import ChatDockInsetSync from "@/components/shell/ChatDockInsetSync";
import SkipToContent from "@/components/shell/SkipToContent";
import { ConfigProvider } from "@/lib/configContext";
import { SUT_BRAND } from "@/lib/constants";
import { DEFAULT_LOCALE, type Locale } from "@/lib/i18n/types";

type UserRole = "billing_officer" | "dev";

const ROLE_COOKIE_KEY = "bilun:role";

function parseRole(value: string | undefined): UserRole {
  return value === "billing_officer" ? "billing_officer" : "dev";
}
import { ShellStateProviders } from "@/stores/providers";
import "./globals.css";
import "./styles/sut-how-modal.css";

const fontDisplay = Fraunces({
  subsets: ["latin", "latin-ext"],
  variable: "--font-display",
  weight: ["400", "500", "700"],
  style: ["normal", "italic"],
  display: "swap",
});

const fontSans = Inter({
  subsets: ["latin", "latin-ext"],
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

function parseLocale(value: string | undefined): Locale {
  return value === "tr" ? "tr" : DEFAULT_LOCALE;
}

export default async function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  const cookieStore = await cookies();
  const initialLocale = parseLocale(cookieStore.get("bilun:locale")?.value);
  const initialRole: UserRole = parseRole(cookieStore.get(ROLE_COOKIE_KEY)?.value);

  return (
    <html lang={initialLocale} className={`${fontDisplay.variable} ${fontSans.variable}`}>
      <body className="antialiased" suppressHydrationWarning>
        <ConfigProvider>
          <ShellStateProviders initialLocale={initialLocale} initialRole={initialRole}>
            <SkipToContent />
            <ChatDockInsetSync />
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
