import type { Metadata, Viewport } from "next";
import { Suspense } from "react";
import { Fraunces, Inter } from "next/font/google";
import AppTopBar from "@/components/shell/AppTopBar";
import ChatDockInsetSync from "@/components/shell/ChatDockInsetSync";
import SkipToContent from "@/components/shell/SkipToContent";
import { ConfigProvider } from "@/lib/configContext";
import { SUT_BRAND } from "@/lib/constants";
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

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={`${fontDisplay.variable} ${fontSans.variable}`}>
      <body className="antialiased" suppressHydrationWarning>
        <ConfigProvider>
          <ShellStateProviders>
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
