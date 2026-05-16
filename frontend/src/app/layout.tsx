import type { Metadata, Viewport } from "next";
import { ConfigProvider } from "@/lib/configContext";
import { SUT_BRAND } from "@/lib/constants";
import { ShellStateProviders } from "@/stores/providers";
import "./globals.css";
import "./styles/sut-premium.css";
import "./styles/sut-how-modal.css";

export const metadata: Metadata = {
  title: SUT_BRAND.metaTitle,
  description: SUT_BRAND.metaDescription,
};

export const viewport: Viewport = {
  themeColor: "#FAFAF9",
  colorScheme: "light",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className="antialiased" suppressHydrationWarning>
        <a
          href="#main-content"
          className="sr-only focus:not-sr-only focus:absolute focus:top-4 focus:left-4 focus:z-[9999] focus:bg-white focus:px-4 focus:py-2 focus:rounded-lg focus:shadow-lg focus:text-emerald-600 focus:font-semibold"
        >
          Skip to main content
        </a>
        <ConfigProvider>
          <ShellStateProviders>{children}</ShellStateProviders>
        </ConfigProvider>
      </body>
    </html>
  );
}
