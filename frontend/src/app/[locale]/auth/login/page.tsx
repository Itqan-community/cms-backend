import { notFound } from 'next/navigation';
import { AuthLayout } from '@/components/auth/auth-layout';
import { Auth0LoginForm } from '@/components/auth/auth0-login-form';
import { getDictionary } from '@/lib/i18n/dictionaries';
import { isValidLocale } from '@/lib/i18n/utils';
import type { Locale } from '@/lib/i18n/types';

interface LoginPageProps {
  params: Promise<{
    locale: string;
  }>;
}

export default async function LoginPage({ params }: LoginPageProps) {
  const { locale } = await params;
  
  // Validate locale
  if (!isValidLocale(locale)) {
    notFound();
  }
  
  const validatedLocale = locale as Locale;
  const dict = await getDictionary(validatedLocale);

  return (
    <AuthLayout locale={validatedLocale}>
      <Auth0LoginForm dict={dict} locale={validatedLocale} />
    </AuthLayout>
  );
}

export async function generateMetadata({ params }: LoginPageProps) {
  const { locale } = await params;
  
  if (!isValidLocale(locale)) {
    return {};
  }
  
  const validatedLocale = locale as Locale;
  const dict = await getDictionary(validatedLocale);

  return {
    title: dict.auth.loginTitle,
    description: dict.auth.loginTitle,
  };
}
