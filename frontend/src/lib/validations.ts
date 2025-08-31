import type { Dictionary } from '@/lib/i18n/types';

export interface ValidationError {
  field: string;
  message: string;
}

export interface ValidationResult {
  isValid: boolean;
  errors: ValidationError[];
}

/**
 * Email validation regex
 */
const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

/**
 * Phone validation regex (international format)
 */
const PHONE_REGEX = /^[\+]?[1-9][\d]{0,15}$/;

/**
 * Validation utilities
 */
export const validators = {
  email: (value: string, dict: Dictionary): string | null => {
    if (!value.trim()) {
      return dict.auth.validation.emailRequired;
    }
    if (!EMAIL_REGEX.test(value)) {
      return dict.auth.validation.emailInvalid;
    }
    return null;
  },

  password: (value: string, dict: Dictionary): string | null => {
    if (!value) {
      return dict.auth.validation.passwordRequired;
    }
    if (value.length < 8) {
      return dict.auth.validation.passwordMinLength;
    }
    return null;
  },

  required: (value: string, fieldName: keyof Dictionary['auth']['validation'], dict: Dictionary): string | null => {
    if (!value.trim()) {
      return dict.auth.validation[fieldName];
    }
    return null;
  },

  phone: (value: string, dict: Dictionary): string | null => {
    if (!value.trim()) {
      return dict.auth.validation.phoneRequired;
    }
    if (!PHONE_REGEX.test(value.replace(/\s/g, ''))) {
      return dict.auth.validation.phoneInvalid;
    }
    return null;
  },

  minLength: (value: string, minLength: number, dict: Dictionary): string | null => {
    if (value.trim().length < minLength) {
      return dict.auth.validation.fieldTooShort;
    }
    return null;
  },

  maxLength: (value: string, maxLength: number, dict: Dictionary): string | null => {
    if (value.trim().length > maxLength) {
      return dict.auth.validation.fieldTooLong;
    }
    return null;
  }
};

/**
 * Login form validation
 */
export const validateLoginForm = (
  formData: { email: string; password: string },
  dict: Dictionary
): ValidationResult => {
  const errors: ValidationError[] = [];

  const emailError = validators.email(formData.email, dict);
  if (emailError) {
    errors.push({ field: 'email', message: emailError });
  }

  const passwordError = validators.password(formData.password, dict);
  if (passwordError) {
    errors.push({ field: 'password', message: passwordError });
  }

  return {
    isValid: errors.length === 0,
    errors
  };
};

/**
 * Signup form validation
 */
export const validateSignupForm = (
  formData: {
    firstName: string;
    lastName: string;
    jobTitle: string;
    phoneNumber: string;
    email: string;
    password: string;
  },
  dict: Dictionary
): ValidationResult => {
  const errors: ValidationError[] = [];

  // First name validation
  const firstNameError = validators.required(formData.firstName, 'firstNameRequired', dict);
  if (firstNameError) {
    errors.push({ field: 'firstName', message: firstNameError });
  }

  // Last name validation
  const lastNameError = validators.required(formData.lastName, 'lastNameRequired', dict);
  if (lastNameError) {
    errors.push({ field: 'lastName', message: lastNameError });
  }

  // Job title validation
  const jobTitleError = validators.required(formData.jobTitle, 'jobTitleRequired', dict);
  if (jobTitleError) {
    errors.push({ field: 'jobTitle', message: jobTitleError });
  }

  // Phone validation
  const phoneError = validators.phone(formData.phoneNumber, dict);
  if (phoneError) {
    errors.push({ field: 'phoneNumber', message: phoneError });
  }

  // Email validation
  const emailError = validators.email(formData.email, dict);
  if (emailError) {
    errors.push({ field: 'email', message: emailError });
  }

  // Password validation
  const passwordError = validators.password(formData.password, dict);
  if (passwordError) {
    errors.push({ field: 'password', message: passwordError });
  }

  return {
    isValid: errors.length === 0,
    errors
  };
};

/**
 * Social profile form validation
 */
export const validateSocialProfileForm = (
  formData: {
    jobTitle: string;
    phoneNumber: string;
    businessModel: string;
    teamSize: string;
    aboutYourself: string;
  },
  dict: Dictionary
): ValidationResult => {
  const errors: ValidationError[] = [];

  // Job title validation
  const jobTitleError = validators.required(formData.jobTitle, 'jobTitleRequired', dict);
  if (jobTitleError) {
    errors.push({ field: 'jobTitle', message: jobTitleError });
  }

  // Phone validation
  const phoneError = validators.phone(formData.phoneNumber, dict);
  if (phoneError) {
    errors.push({ field: 'phoneNumber', message: phoneError });
  }

  // Business model validation
  const businessModelError = validators.required(formData.businessModel, 'businessModelRequired', dict);
  if (businessModelError) {
    errors.push({ field: 'businessModel', message: businessModelError });
  }

  // Additional validation for business model length
  const businessModelLengthError = validators.minLength(formData.businessModel, 10, dict);
  if (businessModelLengthError) {
    errors.push({ field: 'businessModel', message: businessModelLengthError });
  }

  // Team size validation
  const teamSizeError = validators.required(formData.teamSize, 'teamSizeRequired', dict);
  if (teamSizeError) {
    errors.push({ field: 'teamSize', message: teamSizeError });
  }

  // About yourself validation
  const aboutYourselfError = validators.required(formData.aboutYourself, 'aboutYourselfRequired', dict);
  if (aboutYourselfError) {
    errors.push({ field: 'aboutYourself', message: aboutYourselfError });
  }

  // Additional validation for about yourself length
  const aboutYourselfLengthError = validators.minLength(formData.aboutYourself, 20, dict);
  if (aboutYourselfLengthError) {
    errors.push({ field: 'aboutYourself', message: aboutYourselfLengthError });
  }

  return {
    isValid: errors.length === 0,
    errors
  };
};
