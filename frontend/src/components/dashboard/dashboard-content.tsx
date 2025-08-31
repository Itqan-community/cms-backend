"use client";

import { useAuth } from '@/components/providers/auth0-integrated-provider';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import type { Dictionary, Locale } from '@/lib/i18n/types';
import { logical, spacing, typography } from '@/lib/styles/logical';
import { cn } from '@/lib/utils';

interface DashboardContentProps {
  dict: Dictionary;
  locale: Locale;
}

export function DashboardContent({ dict, locale }: DashboardContentProps) {
  const { user, logout } = useAuth();

  if (!user) {
    return null; // This shouldn't happen due to route protection
  }

  return (
    <div className={cn("min-h-screen bg-background", logical.paddingInline('4'), "py-8")}>
      <div className="max-w-4xl mx-auto space-y-6">
        {/* Header */}
        <div className={cn("flex justify-between items-center", spacing.blockMd)}>
          <div>
            <h1 className={cn(typography.heading, "text-3xl font-bold")}>
              {locale === 'ar' ? 'لوحة التحكم' : 'Dashboard'}
            </h1>
            <p className="text-muted-foreground mt-2">
              {locale === 'ar' 
                ? `أهلاً وسهلاً، ${user.firstName} ${user.lastName}` 
                : `Welcome, ${user.firstName} ${user.lastName}`
              }
            </p>
          </div>
          <Button variant="outline" onClick={logout}>
            {locale === 'ar' ? 'تسجيل الخروج' : 'Logout'}
          </Button>
        </div>

        {/* User Info Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <Card>
            <CardHeader>
              <CardTitle className={typography.heading}>
                {locale === 'ar' ? 'معلومات الحساب' : 'Account Information'}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div>
                <strong>{dict.auth.email}:</strong> {user.email}
              </div>
              <div>
                <strong>{dict.auth.firstName}:</strong> {user.firstName}
              </div>
              <div>
                <strong>{dict.auth.lastName}:</strong> {user.lastName}
              </div>
              {user.jobTitle && (
                <div>
                  <strong>{dict.auth.jobTitle}:</strong> {user.jobTitle}
                </div>
              )}
              {user.phoneNumber && (
                <div>
                  <strong>{dict.auth.phoneNumber}:</strong> {user.phoneNumber}
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className={typography.heading}>
                {locale === 'ar' ? 'حالة الحساب' : 'Account Status'}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div>
                <strong>{locale === 'ar' ? 'نوع الحساب' : 'Account Type'}:</strong>{' '}
                {user.provider === 'email' 
                  ? (locale === 'ar' ? 'بريد إلكتروني' : 'Email')
                  : user.provider === 'google'
                  ? 'Google'
                  : 'GitHub'
                }
              </div>
              <div>
                <strong>{locale === 'ar' ? 'حالة الملف الشخصي' : 'Profile Status'}:</strong>{' '}
                <span className={user.profileCompleted ? 'text-green-600' : 'text-orange-600'}>
                  {user.profileCompleted 
                    ? (locale === 'ar' ? 'مكتمل' : 'Complete')
                    : (locale === 'ar' ? 'غير مكتمل' : 'Incomplete')
                  }
                </span>
              </div>
              <div>
                <strong>{locale === 'ar' ? 'تاريخ الانضمام' : 'Member Since'}:</strong>{' '}
                {new Date().toLocaleDateString(locale === 'ar' ? 'ar-SA' : 'en-US')}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Welcome Message */}
        <Card>
          <CardHeader>
            <CardTitle className={typography.heading}>
              {locale === 'ar' ? 'مرحباً بك في منصة المطورين' : 'Welcome to Developer Platform'}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className={cn(typography.paragraph, "text-muted-foreground")}>
              {locale === 'ar' 
                ? 'تم تسجيل دخولك بنجاح! يمكنك الآن الوصول إلى جميع ميزات المنصة والبدء في إنشاء مشاريعك.'
                : 'You have successfully logged in! You can now access all platform features and start building your projects.'
              }
            </p>
            
            <div className="mt-6 flex gap-4">
              <Button>
                {locale === 'ar' ? 'ابدأ مشروع جديد' : 'Start New Project'}
              </Button>
              <Button variant="outline">
                {locale === 'ar' ? 'عرض المشاريع' : 'View Projects'}
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
