import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { notFound } from "next/navigation";
import "../globals.css";
import { locales } from "@/lib/i18n/utils";
import { isValidLocale } from "@/lib/i18n/utils";
import type { Locale } from "@/lib/i18n/types";
import { cn } from "@/lib/utils";
import { ThemeProvider } from "@/components/providers/theme-provider";
import { Auth0ProviderWrapper } from "@/components/providers/auth0-provider";
import { Auth0IntegratedProvider } from "@/components/providers/auth0-integrated-provider";
import { direction } from "@/lib/styles/logical";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Itqan CMS",
  description: "A modern content management system",
};

export async function generateStaticParams() {
  return locales.map((locale) => ({ locale }));
}

interface RootLayoutProps {
  children: React.ReactNode;
  params: Promise<{ locale: string }>;
}

export default async function RootLayout({
  children,
  params,
}: RootLayoutProps) {
  const { locale } = await params;
  
  // Validate locale with proper type safety
  if (!isValidLocale(locale)) {
    notFound();
  }

  // Type assertion after validation
  const validatedLocale = locale as Locale;
  const isRTL = direction.isRTL(validatedLocale);
  const dir = direction.getDir(validatedLocale);

  return (
    <html lang={validatedLocale} dir={dir} suppressHydrationWarning>
      <body
        className={cn(
          geistSans.variable,
          geistMono.variable,
          "antialiased",
          isRTL && "font-arabic"
        )}
      >
        <ThemeProvider>
          <Auth0ProviderWrapper>
            <Auth0IntegratedProvider locale={validatedLocale}>
              {children}
            </Auth0IntegratedProvider>
          </Auth0ProviderWrapper>
        </ThemeProvider>
      </body>
    </html>
  );
}
