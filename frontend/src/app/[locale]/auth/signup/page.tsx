import { notFound } from 'next/navigation';
import { AuthLayout } from '@/components/auth/auth-layout';
import { Auth0SignupForm } from '@/components/auth/auth0-signup-form';
import { getDictionary } from '@/lib/i18n/dictionaries';
import { isValidLocale } from '@/lib/i18n/utils';
import type { Locale } from '@/lib/i18n/types';

interface SignupPageProps {
  params: Promise<{
    locale: string;
  }>;
}

export default async function SignupPage({ params }: SignupPageProps) {
  const { locale } = await params;
  
  // Validate locale
  if (!isValidLocale(locale)) {
    notFound();
  }
  
  const validatedLocale = locale as Locale;
  const dict = await getDictionary(validatedLocale);

  return (
    <AuthLayout locale={validatedLocale}>
      <Auth0SignupForm dict={dict} locale={validatedLocale} />
    </AuthLayout>
  );
}

export async function generateMetadata({ params }: SignupPageProps) {
  const { locale } = await params;
  
  if (!isValidLocale(locale)) {
    return {};
  }
  
  const validatedLocale = locale as Locale;
  const dict = await getDictionary(validatedLocale);

  return {
    title: dict.auth.signupTitle,
    description: dict.auth.signupTitle,
  };
}