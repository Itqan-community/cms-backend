import type { Locale } from '@/lib/i18n/types';
import { direction, logical, responsive } from '@/lib/styles/logical';
import { cn } from '@/lib/utils';

interface AuthLayoutProps {
  children: React.ReactNode;
  locale: Locale;
  className?: string;
}

export function AuthLayout({ children, locale, className }: AuthLayoutProps) {
  // Since both login and signup forms now handle their own full-screen layout,
  // we just render the children directly
  return (
    <div className={cn(className)} dir={direction.getDir(locale)}>
      {children}
    </div>
  );
}
