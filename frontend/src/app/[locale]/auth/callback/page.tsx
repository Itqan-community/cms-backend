import { AuthLoading } from '@/components/auth/auth-loading';
import type { Locale } from '@/lib/i18n/types';

interface CallbackPageProps {
  params: Promise<{ locale: string }>;
}

export default async function CallbackPage({ params }: CallbackPageProps) {
  const { locale } = await params;
  const validatedLocale = locale as Locale;

  return (
    <div className="min-h-screen flex items-center justify-center">
      <AuthLoading 
        message={validatedLocale === 'ar' ? 'جاري تسجيل الدخول...' : 'Signing you in...'} 
      />
    </div>
  );
}
