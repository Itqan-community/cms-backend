import type { Locale } from './types';

export const locales: readonly Locale[] = ['ar', 'en'] as const;
export const defaultLocale: Locale = 'ar' as const;

/**
 * Validates if a given string is a supported locale
 */
export function isValidLocale(locale: string): locale is Locale {
  return locales.includes(locale as Locale);
}

/**
 * Gets the opposite locale (useful for language switcher)
 */
export function getOppositeLocale(currentLocale: Locale): Locale {
  return currentLocale === 'ar' ? 'en' : 'ar';
}

/**
 * Formats a path with locale prefix
 */
export function localizedPath(path: string, locale: Locale): string {
  // Remove leading slash if present
  const cleanPath = path.startsWith('/') ? path.slice(1) : path;
  return `/${locale}${cleanPath ? `/${cleanPath}` : ''}`;
}

/**
 * Removes locale prefix from path
 */
export function unlocalizedPath(path: string): string {
  const segments = path.split('/');
  if (segments.length > 1 && isValidLocale(segments[1])) {
    return '/' + segments.slice(2).join('/');
  }
  return path;
}

/**
 * Gets locale from path with validation
 */
export function getLocaleFromPath(path: string): Locale | null {
  const segments = path.split('/');
  if (segments.length > 1 && isValidLocale(segments[1])) {
    return segments[1] as Locale;
  }
  return null;
}

/**
 * Direction helpers
 */
export const direction = {
  isRTL: (locale: Locale) => locale === 'ar',
  isLTR: (locale: Locale) => locale === 'en',
  getDir: (locale: Locale) => locale === 'ar' ? 'rtl' : 'ltr',
} as const;

/**
 * Common locale display names
 */
export const localeNames = {
  ar: 'العربية',
  en: 'English',
} as const;

/**
 * Format numbers based on locale
 */
export function formatNumber(num: number, locale: Locale): string {
  return new Intl.NumberFormat(locale === 'ar' ? 'ar-SA' : 'en-US').format(num);
}

/**
 * Format dates based on locale
 */
export function formatDate(date: Date, locale: Locale): string {
  return new Intl.DateTimeFormat(locale === 'ar' ? 'ar-SA' : 'en-US').format(date);
}

/**
 * Format currency based on locale
 */
export function formatCurrency(amount: number, locale: Locale, currency = 'SAR'): string {
  return new Intl.NumberFormat(locale === 'ar' ? 'ar-SA' : 'en-US', {
    style: 'currency',
    currency,
  }).format(amount);
}
