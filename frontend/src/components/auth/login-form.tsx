"use client";

import { useState } from 'react';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useAuth } from '@/components/providers/auth-provider';
import type { Dictionary, Locale } from '@/lib/i18n/types';
import { logical, direction } from '@/lib/styles/logical';
import { validateLoginForm } from '@/lib/validations';
import { loginUser } from '@/lib/auth';
import { cn } from '@/lib/utils';
import { ArrowLeft, Home } from 'lucide-react';

interface LoginFormProps {
  dict: Dictionary;
  locale: Locale;
}

export function LoginForm({ dict, locale }: LoginFormProps) {
  const [formData, setFormData] = useState({
    email: '',
    password: ''
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [isLoading, setIsLoading] = useState(false);
  const [submitError, setSubmitError] = useState<string>('');
  
  const { login } = useAuth();

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

  const handleEmailLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitError('');
    
    // Validate form
    const validation = validateLoginForm(formData, dict);
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
      const response = await loginUser(formData.email, formData.password);
      
      if (response.success && response.user && response.token) {
        login(response.user, response.token);
      } else {
        setSubmitError(response.error || dict.auth.validation.loginFailed);
      }
    } catch (error) {
      console.error('Login error:', error);
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
            {locale === 'ar' ? 'مرحبًا بعودتك!' : 'Welcome Back!'}
          </h1>
          
          <p className="text-[18px] font-normal text-neutral-600 text-center leading-normal">
            {locale === 'ar' ? 'قم بتسجيل الدخول لحسابك في إتقان' : 'Sign in to your Itqan account'}
          </p>
        </div>

        {/* Form */}
        <form onSubmit={handleEmailLogin} className="space-y-4 w-full">
          {/* Show submit error */}
          {submitError && (
            <div className="p-3 rounded-[10px] bg-red-50 border border-red-200 text-red-600 text-sm text-center">
              {submitError}
            </div>
          )}

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
            <div className="w-full flex items-center justify-between px-[3px]">
              <button
                type="button"
                className="text-[14px] text-emerald-700 underline leading-[18px] bg-transparent border-none p-0 cursor-pointer font-medium"
                onClick={() => {/* Handle forgot password */}}
              >
                {locale === 'ar' ? 'نسيت كلمة المرور' : 'Forgot Password'}
              </button>
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
                ? (locale === 'ar' ? 'جاري تسجيل الدخول...' : 'Signing in...') 
                : dict.auth.login
              }
            </span>
          </Button>
        </form>
      </div>

      {/* Register Link */}
      <div 
        className="absolute translate-x-[-50%] translate-y-[100%] text-center"
        style={{ left: "calc(50% + 0.5px)", bottom: "239px" }}
      >
        <p className="text-[18px] font-normal text-neutral-950 leading-[20px]">
          <span>{dict.auth.noAccount} </span>
          <Link
            href={`/${locale}/auth/signup`}
            className="font-bold text-neutral-950 hover:text-[#22433d] transition-colors"
          >
            {dict.auth.register}
          </Link>
        </p>
      </div>
    </div>
  );
}
