"use client";

import { useState } from 'react';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useAuth } from '@/components/providers/auth0-integrated-provider';
import type { Dictionary, Locale } from '@/lib/i18n/types';
import { formLogical, spacing, typography } from '@/lib/styles/logical';
import { logical, direction } from '@/lib/styles/logical';
import { validateSignupForm } from '@/lib/validations';
import { signupUser } from '@/lib/auth';
import { cn } from '@/lib/utils';
import { ArrowLeft, Home } from 'lucide-react';

interface SignupFormProps {
  dict: Dictionary;
  locale: Locale;
}

export function Auth0SignupForm({ dict, locale }: SignupFormProps) {
  const { loginWithRedirect, isLoading: authLoading } = useAuth();
  
  // Form state for custom signup
  const [formData, setFormData] = useState({
    firstName: '',
    lastName: '',
    jobTitle: '',
    phoneNumber: '',
    email: '',
    password: ''
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [isLoading, setIsLoading] = useState(false);
  const [submitError, setSubmitError] = useState<string>('');
  const [showCustomForm, setShowCustomForm] = useState(false);

  const handleSocialSignup = (connection: string) => {
    loginWithRedirect({
        connection: connection,
        screen_hint: 'signup',
    });
  };

  const handleEmailSignup = () => {
    setShowCustomForm(true);
  };

  const handleInputChange = (field: keyof typeof formData) => (e: React.ChangeEvent<HTMLInputElement>) => {
    setFormData(prev => ({
      ...prev,
      [field]: e.target.value
    }));
    
    // Clear field error when user starts typing
    if (errors[field]) {
      setErrors(prev => ({
        ...prev,
        [field]: ''
      }));
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitError('');
    
    // Validate form
    const validation = validateSignupForm(formData, dict);
    if (!validation.isValid) {
      const fieldErrors: Record<string, string> = {};
      validation.errors.forEach(error => {
        fieldErrors[error.field] = error.message;
      });
      setErrors(fieldErrors);
      return;
    }
    
    setIsLoading(true);
    
    try {
      const response = await signupUser(formData);
      
      if (response.success && response.user && response.token) {
        // For now, we'll use the existing auth system
        // TODO: Integrate with Auth0IntegratedProvider properly
        window.location.href = `/${locale}/dashboard`;
      } else {
        setSubmitError(response.error || dict.auth.validation.signupFailed);
      }
    } catch (error) {
      console.error('Signup error:', error);
      setSubmitError(dict.auth.validation.networkError);
    } finally {
      setIsLoading(false);
    }
  };

  if (showCustomForm) {
    return (
      <div className="relative min-h-screen bg-neutral-100" dir={direction.getDir(locale)}>
        {/* Back to Social Options Button */}
        <Button
          variant="outline"
          onClick={() => setShowCustomForm(false)}
          className="absolute top-6 left-6 border-[1.25px] border-neutral-950 bg-transparent hover:bg-neutral-200/50 rounded-[10px] h-12 px-4"
        >
          <ArrowLeft className="size-5 text-neutral-950" />
          <span className="text-[18px] font-normal text-neutral-950 leading-[20px] ml-2">
            {locale === 'ar' ? 'العودة' : 'Back'}
          </span>
        </Button>

        {/* Main Content */}
        <div 
          className="absolute left-1/2 translate-x-[-50%] translate-y-[-50%] w-[474px] max-w-[90vw]"
          style={{ top: "calc(50% - 30px)" }}
        >
          {/* Header Section */}
          <div className="flex flex-col gap-3 items-center justify-center w-full mb-8">
            {/* Logo Placeholder - Replace with actual logo if available */}
            <div className="h-12 w-[50px] bg-[#22433d] rounded-md flex items-center justify-center">
              <span className="text-[#669B80] font-bold text-xl">إ</span>
            </div>
            
            <h1 className="text-[32px] font-medium text-neutral-950 text-center leading-normal">
              {locale === 'ar' ? 'مرحبًا بك!' : 'Welcome!'}
            </h1>
            
            <p className="text-[18px] font-normal text-neutral-600 text-center leading-normal">
              {locale === 'ar' ? 'أنشئ حسابك الجديد في إتقان' : 'Create your new account in Itqan'}
            </p>
          </div>

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-4 w-full">
            {/* Show submit error */}
            {submitError && (
              <div className="p-3 rounded-[10px] bg-red-50 border border-red-200 text-red-600 text-sm text-center">
                {submitError}
              </div>
            )}

            {/* Name Fields - Side by Side */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="flex flex-col gap-2 items-end w-full">
                <div className="w-full">
                  <Label 
                    htmlFor="firstName" 
                    className={cn(
                      "text-[16px] font-medium text-neutral-950 leading-[20px]",
                      logical.textStart
                    )}
                  >
                    {dict.auth.firstName}
                  </Label>
                </div>
                <div className="relative w-full">
                  <Input
                    id="firstName"
                    type="text"
                    value={formData.firstName}
                    onChange={handleInputChange('firstName')}
                    className={cn(
                      "bg-white h-10 rounded-[10px] border-[0.75px] border-neutral-200 w-full px-2.5 py-2",
                      "text-[14px] font-normal text-neutral-500 leading-[1.6]",
                      logical.textStart,
                      "focus-visible:ring-0 focus-visible:ring-offset-0 focus-visible:border-[#22433d]",
                      errors.firstName && "border-red-400 focus-visible:border-red-400"
                    )}
                    dir="auto"
                    aria-invalid={!!errors.firstName}
                  />
                </div>
                {errors.firstName && (
                  <p className={cn("text-sm text-red-600 w-full", logical.textStart)}>
                    {errors.firstName}
                  </p>
                )}
              </div>

              <div className="flex flex-col gap-2 items-end w-full">
                <div className="w-full">
                  <Label 
                    htmlFor="lastName" 
                    className={cn(
                      "text-[16px] font-medium text-neutral-950 leading-[20px]",
                      logical.textStart
                    )}
                  >
                    {dict.auth.lastName}
                  </Label>
                </div>
                <div className="relative w-full">
                  <Input
                    id="lastName"
                    type="text"
                    value={formData.lastName}
                    onChange={handleInputChange('lastName')}
                    className={cn(
                      "bg-white h-10 rounded-[10px] border-[0.75px] border-neutral-200 w-full px-2.5 py-2",
                      "text-[14px] font-normal text-neutral-500 leading-[1.6]",
                      logical.textStart,
                      "focus-visible:ring-0 focus-visible:ring-offset-0 focus-visible:border-[#22433d]",
                      errors.lastName && "border-red-400 focus-visible:border-red-400"
                    )}
                    dir="auto"
                    aria-invalid={!!errors.lastName}
                  />
                </div>
                {errors.lastName && (
                  <p className={cn("text-sm text-red-600 w-full", logical.textStart)}>
                    {errors.lastName}
                  </p>
                )}
              </div>
            </div>

            {/* Job Title Field */}
            <div className="flex flex-col gap-2 items-end w-full">
              <div className="w-full">
                <Label 
                  htmlFor="jobTitle" 
                  className={cn(
                    "text-[16px] font-medium text-neutral-950 leading-[20px]",
                    logical.textStart
                  )}
                >
                  {dict.auth.jobTitle}
                </Label>
              </div>
              <div className="relative w-full">
                <Input
                  id="jobTitle"
                  type="text"
                  value={formData.jobTitle}
                  onChange={handleInputChange('jobTitle')}
                  placeholder={dict.auth.jobTitlePlaceholder}
                  className={cn(
                    "bg-white h-10 rounded-[10px] border-[0.75px] border-neutral-200 w-full px-2.5 py-2",
                    "text-[14px] font-normal text-neutral-500 leading-[1.6]",
                    logical.textStart,
                    "focus-visible:ring-0 focus-visible:ring-offset-0 focus-visible:border-[#22433d]",
                    errors.jobTitle && "border-red-400 focus-visible:border-red-400"
                  )}
                  dir="auto"
                  aria-invalid={!!errors.jobTitle}
                />
              </div>
              {errors.jobTitle && (
                <p className={cn("text-sm text-red-600 w-full", logical.textStart)}>
                  {errors.jobTitle}
                </p>
              )}
            </div>

            {/* Phone Number Field */}
            <div className="flex flex-col gap-2 items-end w-full">
              <div className="w-full">
                <Label 
                  htmlFor="phoneNumber" 
                  className={cn(
                    "text-[16px] font-medium text-neutral-950 leading-[20px]",
                    logical.textStart
                  )}
                >
                  {dict.auth.phoneNumber}
                </Label>
              </div>
              <div className="relative w-full">
                <Input
                  id="phoneNumber"
                  type="tel"
                  value={formData.phoneNumber}
                  onChange={handleInputChange('phoneNumber')}
                  placeholder={dict.auth.phoneNumberPlaceholder}
                  className={cn(
                    "bg-white h-10 rounded-[10px] border-[0.75px] border-neutral-200 w-full px-2.5 py-2",
                    "text-[14px] font-normal text-neutral-500 leading-[1.6]",
                    logical.textStart,
                    "focus-visible:ring-0 focus-visible:ring-offset-0 focus-visible:border-[#22433d]",
                    errors.phoneNumber && "border-red-400 focus-visible:border-red-400"
                  )}
                  dir="auto"
                  aria-invalid={!!errors.phoneNumber}
                />
              </div>
              {errors.phoneNumber && (
                <p className={cn("text-sm text-red-600 w-full", logical.textStart)}>
                  {errors.phoneNumber}
                </p>
              )}
            </div>

            {/* Email Field */}
            <div className="flex flex-col gap-2 items-end w-full">
              <div className="w-full">
                <Label 
                  htmlFor="email" 
                  className={cn(
                    "text-[16px] font-medium text-neutral-950 leading-[20px]",
                    logical.textStart
                  )}
                >
                  {dict.auth.email}
                </Label>
              </div>
              <div className="relative w-full">
                <Input
                  id="email"
                  type="email"
                  value={formData.email}
                  onChange={handleInputChange('email')}
                  placeholder={dict.auth.emailPlaceholder}
                  className={cn(
                    "bg-white h-10 rounded-[10px] border-[0.75px] border-neutral-200 w-full px-2.5 py-2",
                    "text-[14px] font-normal text-neutral-500 leading-[1.6]",
                    logical.textStart,
                    "focus-visible:ring-0 focus-visible:ring-offset-0 focus-visible:border-[#22433d]",
                    errors.email && "border-red-400 focus-visible:border-red-400"
                  )}
                  dir="auto"
                  aria-invalid={!!errors.email}
                />
              </div>
              {errors.email && (
                <p className={cn("text-sm text-red-600 w-full", logical.textStart)}>
                  {errors.email}
                </p>
              )}
            </div>

            {/* Password Field */}
            <div className="flex flex-col gap-2 items-end w-full">
              <div className="w-full">
                <Label 
                  htmlFor="password" 
                  className={cn(
                    "text-[16px] font-medium text-neutral-950 leading-[20px]",
                    logical.textStart
                  )}
                >
                  {dict.auth.password}
                </Label>
              </div>
              <div className="relative w-full">
                <Input
                  id="password"
                  type="password"
                  value={formData.password}
                  onChange={handleInputChange('password')}
                  placeholder={dict.auth.passwordPlaceholder}
                  className={cn(
                    "bg-white h-10 rounded-[10px] border-[0.75px] border-neutral-200 w-full px-2.5 py-2",
                    "text-[14px] font-normal text-neutral-500 leading-[1.6]",
                    logical.textStart,
                    "focus-visible:ring-0 focus-visible:ring-offset-0 focus-visible:border-[#22433d]",
                    errors.password && "border-red-400 focus-visible:border-red-400"
                  )}
                  dir="auto"
                  aria-invalid={!!errors.password}
                />
              </div>
              {errors.password && (
                <p className={cn("text-sm text-red-600 w-full", logical.textStart)}>
                  {errors.password}
                </p>
              )}
            </div>

            {/* Submit Button */}
            <Button
              type="submit"
              disabled={isLoading}
              className={cn(
                "bg-[#22433d] hover:bg-[#22433d]/90 h-12 rounded-[10px] w-full",
                "flex items-center justify-center gap-2 text-white font-normal text-[18px] leading-[20px]",
                "transition-colors duration-200"
              )}
            >
              <ArrowLeft className="size-5 text-white" />
              <span>
                {isLoading 
                  ? (locale === 'ar' ? 'جاري إنشاء الحساب...' : 'Creating account...') 
                  : dict.auth.signup
                }
              </span>
            </Button>
          </form>
        </div>

        {/* Login Link */}
        <div 
          className="absolute translate-x-[-50%] translate-y-[100%] text-center"
          style={{ left: "calc(50% + 0.5px)", bottom: "239px" }}
        >
          <p className="text-[18px] font-normal text-neutral-950 leading-[20px]">
            <span>{dict.auth.alreadyHaveAccount} </span>
            <Link
              href={`/${locale}/auth/login`}
              className="font-bold text-neutral-950 hover:text-[#22433d] transition-colors"
            >
              {dict.auth.loginLink}
            </Link>
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className={cn("text-center", spacing.blockMd)}>
        <h1 className={cn(
          typography.heading,
          "text-2xl font-bold text-foreground"
        )}>
          {dict.auth.signupTitle}
        </h1>
      </div>

      {/* Social Signup Buttons */}
      <div className={cn("space-y-3", spacing.blockSm)}>
        <Button
          type="button"
          variant="outline"
          className={cn(
            "w-full h-11",
            "bg-red-500 hover:bg-red-600 text-white border-red-500",
            "flex items-center justify-center gap-3"
          )}
          onClick={() => handleSocialSignup('google-oauth2')}
          disabled={authLoading}
        >
          <svg className="size-5" viewBox="0 0 24 24">
            <path
              fill="currentColor"
              d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
            />
            <path
              fill="currentColor"
              d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
            />
            <path
              fill="currentColor"
              d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
            />
            <path
              fill="currentColor"
              d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
            />
          </svg>
          {authLoading ? (locale === 'ar' ? 'جاري التحميل...' : 'Loading...') : dict.auth.loginWithGoogle}
        </Button>

        <Button
          type="button"
          variant="outline"
          className={cn(
            "w-full h-11",
            "bg-gray-900 hover:bg-gray-800 text-white border-gray-900",
            "flex items-center justify-center gap-3"
          )}
          onClick={() => handleSocialSignup('github')}
          disabled={authLoading}
        >
          <svg className="size-5" fill="currentColor" viewBox="0 0 24 24">
            <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/>
          </svg>
          {authLoading ? (locale === 'ar' ? 'جاري التحميل...' : 'Loading...') : dict.auth.loginWithGitHub}
        </Button>
      </div>

      {/* Divider */}
      <div className="relative">
        <div className="absolute inset-0 flex items-center">
          <span className="w-full border-t" />
        </div>
        <div className="relative flex justify-center text-xs uppercase">
          <span className="bg-card px-2 text-muted-foreground">
            {locale === 'ar' ? 'أو' : 'OR'}
          </span>
        </div>
      </div>

      {/* Email Signup Button */}
      <Button
        type="button"
        className="w-full h-11"
        onClick={handleEmailSignup}
        disabled={authLoading}
      >
        {authLoading ? (locale === 'ar' ? 'جاري التحميل...' : 'Loading...') : dict.auth.signup}
      </Button>

      {/* Login Link */}
      <div className={cn("text-center", spacing.blockSm)}>
        <p className="text-sm text-muted-foreground">
          {dict.auth.alreadyHaveAccount}{' '}
          <Link
            href={`/${locale}/auth/login`}
            className="text-primary hover:underline font-medium"
          >
            {dict.auth.loginLink}
          </Link>
        </p>
      </div>
    </div>
  );
}
