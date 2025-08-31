import Link from "next/link";
import { Button } from "@/components/ui/button";
import { getDictionary } from "@/lib/i18n/dictionaries";
import { MainLayout } from "@/components/layout/main-layout";
import { layoutPatterns, typography, spacing } from "@/lib/styles/logical";
import type { Locale } from "@/lib/i18n/types";
import { cn } from "@/lib/utils";

interface HomePageProps {
  params: Promise<{ locale: string }>;
}

export default async function HomePage({ params }: HomePageProps) {
  const { locale } = await params;
  
  // Validate and cast locale
  const validatedLocale = locale as Locale;
  const dict = await getDictionary(validatedLocale);

  return (
    <MainLayout dict={dict} locale={validatedLocale}>
      <div className="min-h-[calc(100vh-200px)] flex flex-col items-center justify-center gap-8">
        {/* Header with title */}
        <div className="flex items-center gap-4 flex-wrap justify-center">
          <h1 className="text-4xl font-bold text-center">
            {dict.welcome}
          </h1>
        </div>
      
      {/* Description */}
      <p className={cn(typography.paragraph, "text-lg text-muted-foreground text-center max-w-md")}>
        {dict.description}
      </p>
      
      {/* Action buttons - automatically flow with text direction */}
      <div className={cn("flex", spacing.gapMd)}>
        <Button variant="default" className="min-w-[120px]">
          {dict.getStarted}
        </Button>
        <Button variant="outline" className="min-w-[120px]">
          {dict.learnMore}
        </Button>
      </div>

      {/* Auth Demo Links */}
      <div className="mt-8 p-6 border rounded-lg bg-card">
        <h3 className="text-lg font-semibold mb-4 text-center">
          {validatedLocale === 'ar' ? 'تجربة نظام المصادقة' : 'Authentication Demo'}
        </h3>
        <div className={cn("flex flex-wrap justify-center", spacing.gapMd)}>
          <Button asChild variant="default">
            <Link href={`/${validatedLocale}/auth/login`}>
              {validatedLocale === 'ar' ? 'تسجيل الدخول' : 'Login'}
            </Link>
          </Button>
          <Button asChild variant="outline">
            <Link href={`/${validatedLocale}/auth/signup`}>
              {validatedLocale === 'ar' ? 'إنشاء حساب' : 'Sign Up'}
            </Link>
          </Button>
          <Button asChild variant="secondary">
            <Link href={`/${validatedLocale}/auth/complete-profile?provider=google&firstName=John&lastName=Doe&email=john@example.com`}>
              {validatedLocale === 'ar' ? 'إكمال الملف الشخصي (تجربة)' : 'Complete Profile (Demo)'}
            </Link>
          </Button>
        </div>
      </div>
      
      {/* Demo section to showcase automatic RTL layout and theming */}
      <div className="mt-12 ps-6 pe-6 pt-6 pb-6 border rounded-lg max-w-2xl w-full bg-card">
        <h2 className="text-xl font-semibold mb-4 text-start">
          {validatedLocale === 'ar' ? 'مثال على التخطيط الذكي والمظاهر' : 'Smart Layout & Theming Example'}
        </h2>
        
        {/* This layout automatically adapts to RTL/LTR */}
        <div className={cn(layoutPatterns.spaceBetween, "ps-4 pe-4 pt-4 pb-4 bg-muted rounded-md")}>
          <span className="font-medium">
            {validatedLocale === 'ar' ? 'النص الرئيسي' : 'Main Text'}
          </span>
          <Button variant="secondary" size="sm">
            {dict.edit}
          </Button>
        </div>
        
        <div className="mt-4 text-sm text-muted-foreground text-start">
          {validatedLocale === 'ar' 
            ? 'هذا المثال يستخدم الخصائص المنطقية في CSS للتكيف التلقائي مع اتجاه النص والمظهر المظلم/المضيء'
            : 'This example uses CSS logical properties and theme variables to automatically adapt to text direction and light/dark themes'
          }
        </div>
        
        {/* Additional demo: Icon positioning */}
        <div className="mt-6 space-y-3">
          <div className="flex items-center gap-3">
            <div className="w-4 h-4 bg-primary rounded-full icon-start"></div>
            <span className="text-start">
              {validatedLocale === 'ar' ? 'أيقونة في البداية' : 'Icon at start'}
            </span>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-start">
              {validatedLocale === 'ar' ? 'أيقونة في النهاية' : 'Icon at end'}
            </span>
            <div className="w-4 h-4 bg-secondary rounded-full icon-end"></div>
          </div>
        </div>
      </div>
      
      {/* Original test button */}
        <Button variant="outline" className="mt-8" asChild>
          <Link href={`/${validatedLocale}/dashboard`}>
            {validatedLocale === 'ar' ? 'الذهاب إلى لوحة التحكم (يتطلب تسجيل الدخول)' : 'Go to Dashboard (requires login)'}
          </Link>
        </Button>
      </div>
    </MainLayout>
  );
}
