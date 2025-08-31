"use client";

import { createContext, useContext, ReactNode } from "react";
import type { Dictionary, Locale, LocaleContextType } from "@/lib/i18n/types";

const LocaleContext = createContext<LocaleContextType | undefined>(undefined);

interface LocaleProviderProps {
  children: ReactNode;
  locale: Locale;
  dict: Dictionary;
}

export function LocaleProvider({ children, locale, dict }: LocaleProviderProps) {
  const isRTL = locale === 'ar';

  return (
    <LocaleContext.Provider value={{ locale, dict, isRTL }}>
      {children}
    </LocaleContext.Provider>
  );
}

export function useLocale() {
  const context = useContext(LocaleContext);
  if (context === undefined) {
    throw new Error('useLocale must be used within a LocaleProvider');
  }
  return context;
}

/**
 * Enhanced translation hook with additional utilities
 */
export function useTranslation() {
  const { dict, locale, isRTL } = useLocale();
  
  const t = (key: keyof Dictionary) => dict[key];
  
  // Additional utilities
  const formatMessage = (key: keyof Dictionary, values?: Record<string, string | number>) => {
    const message = dict[key];
    // Only format if message is a string
    if (typeof message === 'string' && values) {
      let stringMessage = message;
      Object.entries(values).forEach(([placeholder, value]) => {
        stringMessage = stringMessage.replace(`{${placeholder}}`, String(value));
      });
      return stringMessage;
    }
    return message;
  };
  
  return { 
    t, 
    dict, 
    locale, 
    isRTL,
    formatMessage,
  };
}
