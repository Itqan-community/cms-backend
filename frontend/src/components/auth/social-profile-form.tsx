"use client";

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { useAuth } from '@/components/providers/auth0-integrated-provider';
import type { Dictionary, Locale } from '@/lib/i18n/types';
import { formLogical, spacing, typography } from '@/lib/styles/logical';
import { validateSocialProfileForm } from '@/lib/validations';
import { cn } from '@/lib/utils';

interface SocialProfileFormProps {
  dict: Dictionary;
  locale: Locale;
}

export function SocialProfileForm({ 
  dict,
  locale
}: SocialProfileFormProps) {
  const { user, completeProfile } = useAuth();
  
  const [formData, setFormData] = useState({
    firstName: user?.firstName || '',
    lastName: user?.lastName || '',
    jobTitle: '',
    phoneNumber: '',
    businessModel: '',
    teamSize: '',
    aboutYourself: ''
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [isLoading, setIsLoading] = useState(false);
  const [submitError, setSubmitError] = useState<string>('');

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
      await completeProfile({
        firstName: formData.firstName,
        lastName: formData.lastName,
        jobTitle: formData.jobTitle,
        phoneNumber: formData.phoneNumber,
        businessModel: formData.businessModel,
        teamSize: formData.teamSize,
        aboutYourself: formData.aboutYourself
      });
    } catch (error) {
      console.error('Profile completion error:', error);
      setSubmitError(dict.auth.validation.networkError);
    } finally {
      setIsLoading(false);
    }
  };



  return (
    <div className="space-y-6">
      {/* Header */}
      <div className={cn("text-center", spacing.blockMd)}>
        <div className="flex items-center justify-center gap-3 mb-4">
          <svg className="size-5" viewBox="0 0 24 24" fill="currentColor">
            <path d="M21.98 7.448L19.62 0H4.347L2.02 7.448c-1.352 4.312.03 9.206 3.815 12.015L12.007 24l6.157-4.537c3.785-2.809 5.167-7.703 3.815-12.015z"/>
          </svg>
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
        {user?.email && (
          <div className={formLogical.fieldset}>
            <Label className={formLogical.label}>
              {dict.auth.email}
            </Label>
            <div className={cn(
              "px-3 py-2 bg-muted rounded-md border text-sm text-muted-foreground",
              formLogical.input
            )}>
              {user.email}
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
