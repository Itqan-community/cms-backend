"use client";

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { useAuth } from '@/components/providers/auth0-integrated-provider';
import { LanguageSwitcher } from '@/components/language-switcher';
import { ThemeToggle } from '@/components/theme-toggle';
import type { Dictionary, Locale } from '@/lib/i18n/types';
import { logical, layoutPatterns, spacing } from '@/lib/styles/logical';
import { cn } from '@/lib/utils';

interface HeaderProps {
  dict: Dictionary;
  locale: Locale;
}

export function Header({ dict, locale }: HeaderProps) {
  const { user, isAuthenticated, logout, isLoading } = useAuth();
  const router = useRouter();

  const handleLogin = () => {
    // Redirect to custom login page instead of Auth0 Universal Login
    router.push(`/${locale}/auth/login`);
  };

  const handleLogout = () => {
    logout();
  };

  return (
    <header className={cn(
      "sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60",
      logical.paddingInline('4'),
      "py-3"
    )}>
      <div className={cn(
        "container mx-auto",
        layoutPatterns.spaceBetween,
        spacing.gapLg
      )}>
        {/* Logo and Navigation */}
        <div className={cn("flex items-center", spacing.gapLg)}>
          {/* Logo */}
          <Link 
            href={`/${locale}`}
            className={cn(
              "flex items-center gap-2 font-bold text-xl text-foreground hover:text-primary transition-colors"
            )}
          >
            <svg className="size-8" viewBox="0 0 24 24" fill="currentColor">
              <path d="M21.98 7.448L19.62 0H4.347L2.02 7.448c-1.352 4.312.03 9.206 3.815 12.015L12.007 24l6.157-4.537c3.785-2.809 5.167-7.703 3.815-12.015z"/>
            </svg>
            <span>إتقان</span>
          </Link>

          {/* Navigation - Only show for authenticated users */}
          {isAuthenticated && (
            <nav className={cn("hidden md:flex", spacing.gapMd)}>
              <Link
                href={`/${locale}/dashboard`}
                className="text-sm font-medium text-muted-foreground hover:text-foreground transition-colors"
              >
                {locale === 'ar' ? 'لوحة التحكم' : 'Dashboard'}
              </Link>
              <Link
                href={`/${locale}/resources`}
                className="text-sm font-medium text-muted-foreground hover:text-foreground transition-colors"
              >
                {locale === 'ar' ? 'الموارد' : 'Resources'}
              </Link>
              <Link
                href={`/${locale}/publishers`}
                className="text-sm font-medium text-muted-foreground hover:text-foreground transition-colors"
              >
                {locale === 'ar' ? 'الناشرين' : 'Publishers'}
              </Link>
            </nav>
          )}
        </div>

        {/* Right side - Auth, Language, Theme */}
        <div className={cn("flex items-center", spacing.gapMd)}>
          {/* Language Switcher */}
          <LanguageSwitcher currentLocale={locale} />

          {/* Theme Toggle */}
          <ThemeToggle />

          {/* Authentication */}
          {isLoading ? (
            <div className="w-20 h-9 bg-muted animate-pulse rounded-md" />
          ) : isAuthenticated && user ? (
            <div className={cn("flex items-center", spacing.gapSm)}>
              {/* User Info */}
              <div className={cn("hidden sm:block", logical.textEnd)}>
                <p className="text-sm font-medium text-foreground">
                  {user.firstName} {user.lastName}
                </p>
                <p className="text-xs text-muted-foreground">
                  {user.email}
                </p>
              </div>

              {/* User Avatar */}
              <div className="size-9 rounded-full bg-primary/10 flex items-center justify-center">
                <span className="text-sm font-medium text-primary">
                  {user.firstName?.[0]?.toUpperCase() || user.email?.[0]?.toUpperCase() || '?'}
                </span>
              </div>

              {/* Logout Button */}
              <Button
                variant="outline"
                size="sm"
                onClick={handleLogout}
                className="hidden sm:flex"
              >
                {locale === 'ar' ? 'تسجيل الخروج' : 'Logout'}
              </Button>
            </div>
          ) : (
            <Button
              onClick={handleLogin}
              size="sm"
              disabled={isLoading}
            >
              {isLoading 
                ? (locale === 'ar' ? 'جاري التحميل...' : 'Loading...') 
                : (locale === 'ar' ? 'تسجيل الدخول' : 'Login')
              }
            </Button>
          )}
        </div>
      </div>
    </header>
  );
}
