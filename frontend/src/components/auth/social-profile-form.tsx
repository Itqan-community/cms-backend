"use client";

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { useAuth } from '@/components/providers/auth-provider';
import type { Dictionary, Locale } from '@/lib/i18n/types';
import { formLogical, spacing, typography } from '@/lib/styles/logical';
import { validateSocialProfileForm } from '@/lib/validations';
import { completeProfile } from '@/lib/auth';
import { cn } from '@/lib/utils';

interface SocialProfileFormProps {
  dict: Dictionary;
  locale: Locale;
  provider: 'google' | 'github';
  initialData?: {
    firstName?: string;
    lastName?: string;
    email?: string;
  };
}

export function SocialProfileForm({ 
  dict, 
  provider, 
  initialData 
}: SocialProfileFormProps) {
  const [formData, setFormData] = useState({
    firstName: initialData?.firstName || '',
    lastName: initialData?.lastName || '',
    jobTitle: '',
    phoneNumber: '',
    businessModel: '',
    teamSize: '',
    aboutYourself: ''
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [isLoading, setIsLoading] = useState(false);
  const [submitError, setSubmitError] = useState<string>('');
  
  const { login } = useAuth();

  const handleInputChange = (field: keyof typeof formData) => (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>
  ) => {
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
    const validation = validateSocialProfileForm({
      jobTitle: formData.jobTitle,
      phoneNumber: formData.phoneNumber,
      businessModel: formData.businessModel,
      teamSize: formData.teamSize,
      aboutYourself: formData.aboutYourself
    }, dict);
    
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
      const socialUserData = {
        email: initialData?.email || '',
        firstName: formData.firstName,
        lastName: formData.lastName,
        provider
      };
      
      const profileData = {
        jobTitle: formData.jobTitle,
        phoneNumber: formData.phoneNumber,
        businessModel: formData.businessModel,
        teamSize: formData.teamSize,
        aboutYourself: formData.aboutYourself
      };
      
      const response = await completeProfile(socialUserData, profileData);
      
      if (response.success && response.user && response.token) {
        login(response.user, response.token);
      } else {
        setSubmitError(response.error || dict.auth.validation.signupFailed);
      }
    } catch (error) {
      console.error('Profile completion error:', error);
      setSubmitError(dict.auth.validation.networkError);
    } finally {
      setIsLoading(false);
    }
  };

  const providerIcon = provider === 'google' ? (
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
  ) : (
    <svg className="size-5" fill="currentColor" viewBox="0 0 24 24">
      <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/>
    </svg>
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className={cn("text-center", spacing.blockMd)}>
        <div className="flex items-center justify-center gap-3 mb-4">
          {providerIcon}
          <h1 className={cn(
            typography.heading,
            "text-2xl font-bold text-foreground"
          )}>
            {dict.auth.profileCompletion}
          </h1>
        </div>
        <p className="text-sm text-muted-foreground">
          {dict.auth.completeProfile}
        </p>
      </div>

      {/* Profile Completion Form */}
      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Show submit error */}
        {submitError && (
          <div className={cn(
            "p-3 rounded-md border bg-destructive/10 border-destructive/20 text-destructive text-sm",
            formLogical.errorText
          )}>
            {submitError}
          </div>
        )}
        {/* Name Fields - Pre-populated from social login */}
        <div className={cn("grid grid-cols-1 md:grid-cols-2", spacing.gapMd)}>
          <div className={formLogical.fieldset}>
            <Label htmlFor="firstName" className={formLogical.label}>
              {dict.auth.firstName}
              <span className="text-xs text-muted-foreground ml-1">
                ({dict.auth.optional})
              </span>
            </Label>
            <Input
              id="firstName"
              type="text"
              value={formData.firstName}
              onChange={handleInputChange('firstName')}
              className={formLogical.input}
            />
          </div>

          <div className={formLogical.fieldset}>
            <Label htmlFor="lastName" className={formLogical.label}>
              {dict.auth.lastName}
              <span className="text-xs text-muted-foreground ml-1">
                ({dict.auth.optional})
              </span>
            </Label>
            <Input
              id="lastName"
              type="text"
              value={formData.lastName}
              onChange={handleInputChange('lastName')}
              className={formLogical.input}
            />
          </div>
        </div>

        {/* Job Title */}
        <div className={formLogical.fieldset}>
          <Label htmlFor="jobTitle" className={formLogical.label}>
            {dict.auth.jobTitle}
            <span className="text-red-500 ml-1">*</span>
          </Label>
          <Input
            id="jobTitle"
            type="text"
            placeholder={dict.auth.jobTitlePlaceholder}
            value={formData.jobTitle}
            onChange={handleInputChange('jobTitle')}
            className={cn(
              formLogical.input,
              errors.jobTitle && "border-destructive focus-visible:border-destructive"
            )}
            aria-invalid={!!errors.jobTitle}
          />
          {errors.jobTitle && (
            <p className={formLogical.errorText}>{errors.jobTitle}</p>
          )}
        </div>

        {/* Phone Number */}
        <div className={formLogical.fieldset}>
          <Label htmlFor="phoneNumber" className={formLogical.label}>
            {dict.auth.phoneNumber}
            <span className="text-red-500 ml-1">*</span>
          </Label>
          <Input
            id="phoneNumber"
            type="tel"
            placeholder={dict.auth.phoneNumberPlaceholder}
            value={formData.phoneNumber}
            onChange={handleInputChange('phoneNumber')}
            className={cn(
              formLogical.input,
              errors.phoneNumber && "border-destructive focus-visible:border-destructive"
            )}
            aria-invalid={!!errors.phoneNumber}
          />
          {errors.phoneNumber && (
            <p className={formLogical.errorText}>{errors.phoneNumber}</p>
          )}
        </div>

        {/* Business Model */}
        <div className={formLogical.fieldset}>
          <Label htmlFor="businessModel" className={formLogical.label}>
            {dict.auth.businessModel}
            <span className="text-red-500 ml-1">*</span>
          </Label>
          <Textarea
            id="businessModel"
            value={formData.businessModel}
            onChange={handleInputChange('businessModel')}
            className={cn(
              "min-h-20",
              errors.businessModel && "border-destructive focus-visible:border-destructive"
            )}
            rows={3}
            aria-invalid={!!errors.businessModel}
          />
          {errors.businessModel && (
            <p className={formLogical.errorText}>{errors.businessModel}</p>
          )}
        </div>

        {/* Team Size */}
        <div className={formLogical.fieldset}>
          <Label htmlFor="teamSize" className={formLogical.label}>
            {dict.auth.teamSize}
            <span className="text-red-500 ml-1">*</span>
          </Label>
          <Input
            id="teamSize"
            type="text"
            value={formData.teamSize}
            onChange={handleInputChange('teamSize')}
            className={cn(
              formLogical.input,
              errors.teamSize && "border-destructive focus-visible:border-destructive"
            )}
            aria-invalid={!!errors.teamSize}
          />
          {errors.teamSize && (
            <p className={formLogical.errorText}>{errors.teamSize}</p>
          )}
        </div>

        {/* About Yourself */}
        <div className={formLogical.fieldset}>
          <Label htmlFor="aboutYourself" className={formLogical.label}>
            {dict.auth.aboutYourself}
            <span className="text-red-500 ml-1">*</span>
          </Label>
          <Textarea
            id="aboutYourself"
            value={formData.aboutYourself}
            onChange={handleInputChange('aboutYourself')}
            className={cn(
              "min-h-24",
              errors.aboutYourself && "border-destructive focus-visible:border-destructive"
            )}
            rows={4}
            aria-invalid={!!errors.aboutYourself}
          />
          {errors.aboutYourself && (
            <p className={formLogical.errorText}>{errors.aboutYourself}</p>
          )}
        </div>

        {/* Email Display (read-only) */}
        {initialData?.email && (
          <div className={formLogical.fieldset}>
            <Label className={formLogical.label}>
              {dict.auth.email}
            </Label>
            <div className={cn(
              "px-3 py-2 bg-muted rounded-md border text-sm text-muted-foreground",
              formLogical.input
            )}>
              {initialData.email}
            </div>
          </div>
        )}

        <Button
          type="submit"
          className="w-full h-11"
          disabled={isLoading}
        >
          {isLoading ? dict.loading : dict.auth.completeProfile}
        </Button>
      </form>
    </div>
  );
}
