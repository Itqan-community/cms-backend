import { Header } from './header';
import type { Dictionary, Locale } from '@/lib/i18n/types';

interface MainLayoutProps {
  children: React.ReactNode;
  dict: Dictionary;
  locale: Locale;
}

export function MainLayout({ children, dict, locale }: MainLayoutProps) {
  return (
    <div className="min-h-screen bg-background">
      <Header dict={dict} locale={locale} />
      <main className="container mx-auto px-4 py-6">
        {children}
      </main>
    </div>
  );
}
