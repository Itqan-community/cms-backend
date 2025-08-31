"use client";

import { useState } from 'react';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useAuth } from '@/components/providers/auth0-integrated-provider';
import type { Dictionary, Locale } from '@/lib/i18n/types';
import { logical, direction } from '@/lib/styles/logical';
import { validateSignupForm } from '@/lib/validations';
import { signupUser } from '@/lib/auth';
import { cn } from '@/lib/utils';
import { ArrowLeft, Home } from 'lucide-react';

interface SignupFormProps {
  dict: Dictionary;
  locale: Locale;
}

export function SignupForm({ dict, locale }: SignupFormProps) {
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
  
  const { updateUser } = useAuth();

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
        // Convert the response user to the Auth0IntegratedProvider User format
        const auth0User = {
          id: response.user.id,
          email: response.user.email,
          firstName: response.user.firstName,
          lastName: response.user.lastName,
          provider: 'email',
          profileCompleted: true,
          auth0Id: response.user.id, // Use the same ID for email users
        };
        
        // Update the user in the Auth0IntegratedProvider context
        updateUser(auth0User);
        
        // Redirect to dashboard
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



  return (
    <div className="relative min-h-screen bg-neutral-100" dir={direction.getDir(locale)}>
      {/* Back to Site Button */}
      <Button
        variant="outline"
        asChild
        className="absolute top-6 left-6 border-[1.25px] border-neutral-950 bg-transparent hover:bg-neutral-200/50 rounded-[10px] h-12 px-4"
      >
        <Link href={`/${locale}`} className="flex items-center gap-2">
          <Home className="size-5 text-neutral-950" />
          <span className="text-[18px] font-normal text-neutral-950 leading-[20px]">
            {locale === 'ar' ? 'العودة لموقع إتقان' : 'Back to Itqan'}
          </span>
        </Link>
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
