import type { Metadata, Viewport } from "next";
import { cookies } from "next/headers";
import { Suspense } from "react";
import { Fraunces, Inter } from "next/font/google";
import AppSidebar from "@/components/shell/AppSidebar";
import ChatDockInsetSync from "@/components/shell/ChatDockInsetSync";
import SkipToContent from "@/components/shell/SkipToContent";
import WorkspaceRouteSync from "@/components/shell/WorkspaceRouteSync";
import WorkspaceSplitLayout from "@/components/shell/WorkspaceSplitLayout";
import { ConfigProvider } from "@/lib/configContext";
import { SUT_BRAND } from "@/lib/constants";
import { DEFAULT_LOCALE, type Locale } from "@/lib/i18n/types";
import enMessages from "@/messages/en";
import trMessages from "@/messages/tr";

type UserRole = "billing_officer" | "dev";

const ROLE_COOKIE_KEY = "bilun:role";

function resolveMetaDescription(locale: Locale): string {
  const messages = locale === "tr" ? trMessages : enMessages;
  return messages.constants.brand.metaDescription;
}

function parseRole(value: string | undefined): UserRole {
  return value === "billing_officer" ? "billing_officer" : "dev";
}
import WorkspaceTabStripMount from "@/components/shell/WorkspaceTabStripMount";
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

export const viewport: Viewport = {
  themeColor: "#FFFFFF",
};

function parseLocale(value: string | undefined): Locale {
  return value === "tr" ? "tr" : DEFAULT_LOCALE;
}

export async function generateMetadata(): Promise<Metadata> {
  const cookieStore = await cookies();
  const locale = parseLocale(cookieStore.get("bilun:locale")?.value);
  return {
    title: SUT_BRAND.metaTitle,
    description: resolveMetaDescription(locale),
  };
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
              <AppSidebar />
              <WorkspaceRouteSync />
            </Suspense>
            <WorkspaceTabStripMount />
            <WorkspaceSplitLayout>{children}</WorkspaceSplitLayout>
          </ShellStateProviders>
        </ConfigProvider>
      </body>
    </html>
  );
}
