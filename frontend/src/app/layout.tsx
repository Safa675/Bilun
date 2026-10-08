import type { Metadata, Viewport } from "next";
import { cookies } from "next/headers";
import { Suspense } from "react";
import AppSidebar from "@/components/shell/AppSidebar";
import ChatDockInsetSync from "@/components/shell/ChatDockInsetSync";
import SkipToContent from "@/components/shell/SkipToContent";
import WorkspaceRouteSync from "@/components/shell/WorkspaceRouteSync";
import WorkspaceQuickOpen from "@/components/shell/WorkspaceQuickOpen";
import WorkspaceSplitLayout from "@/components/shell/WorkspaceSplitLayout";
import { getServerIdentity } from "@/lib/authServer";
import { SUT_BRAND } from "@/lib/constants";
import { DEFAULT_LOCALE, type Locale } from "@/lib/i18n/types";
import enMessages from "@/messages/en";
import trMessages from "@/messages/tr";

function resolveMetaDescription(locale: Locale): string {
  const messages = locale === "tr" ? trMessages : enMessages;
  return messages.constants.brand.metaDescription;
}

import WorkspaceTabStripMount from "@/components/shell/WorkspaceTabStripMount";
import { ShellStateProviders } from "@/stores/providers";
import "./globals.css";
import "./styles/fonts.css";
import "./styles/sut-how-modal.css";

const FONT_PRELOADS = [
  "/fonts/fraunces/normal-latin.woff2",
  "/fonts/fraunces/normal-latin-ext.woff2",
  "/fonts/fraunces/italic-latin.woff2",
  "/fonts/fraunces/italic-latin-ext.woff2",
  "/fonts/inter/normal-latin.woff2",
  "/fonts/inter/normal-latin-ext.woff2",
];

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
  const initialIdentity = await getServerIdentity(cookieStore.toString());

  return (
    <html lang={initialLocale} className="bilun-fonts">
      <head>
        {FONT_PRELOADS.map((href) => (
          <link
            key={href}
            rel="preload"
            href={href}
            as="font"
            type="font/woff2"
            crossOrigin="anonymous"
          />
        ))}
      </head>
      <body className="antialiased" suppressHydrationWarning>
          <ShellStateProviders initialLocale={initialLocale} initialIdentity={initialIdentity}>
            <SkipToContent />
            <ChatDockInsetSync />
            <Suspense>
              <AppSidebar />
              <WorkspaceRouteSync />
            </Suspense>
            <WorkspaceTabStripMount />
            <WorkspaceSplitLayout>{children}</WorkspaceSplitLayout>
            <WorkspaceQuickOpen />
          </ShellStateProviders>
      </body>
    </html>
  );
}
