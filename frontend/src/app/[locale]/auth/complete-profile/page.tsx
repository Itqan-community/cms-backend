import { notFound } from 'next/navigation';
import { AuthLayout } from '@/components/auth/auth-layout';
import { SocialProfileForm } from '@/components/auth/social-profile-form';
import { getDictionary } from '@/lib/i18n/dictionaries';
import { isValidLocale } from '@/lib/i18n/utils';
import type { Locale } from '@/lib/i18n/types';

interface CompleteProfilePageProps {
  params: Promise<{
    locale: string;
  }>;
  searchParams: Promise<{
    provider?: 'google' | 'github';
    firstName?: string;
    lastName?: string;
    email?: string;
  }>;
}

export default async function CompleteProfilePage({ 
  params, 
  searchParams 
}: CompleteProfilePageProps) {
  const { locale } = await params;
  const { provider, firstName, lastName, email } = await searchParams;
  
  // Validate locale
  if (!isValidLocale(locale)) {
    notFound();
  }
  
  // Validate provider
  if (!provider || !['google', 'github'].includes(provider)) {
    notFound();
  }
  
  const validatedLocale = locale as Locale;
  const dict = await getDictionary(validatedLocale);

  const initialData = {
    firstName: firstName || '',
    lastName: lastName || '',
    email: email || ''
  };

  return (
    <AuthLayout locale={validatedLocale}>
      <SocialProfileForm 
        dict={dict} 
        locale={validatedLocale}
        provider={provider}
        initialData={initialData}
      />
    </AuthLayout>
  );
}

export async function generateMetadata({ params }: CompleteProfilePageProps) {
  const { locale } = await params;
  
  if (!isValidLocale(locale)) {
    return {};
  }
  
  const validatedLocale = locale as Locale;
  const dict = await getDictionary(validatedLocale);

  return {
    title: dict.auth.profileCompletion,
    description: dict.auth.completeProfile,
  };
}
