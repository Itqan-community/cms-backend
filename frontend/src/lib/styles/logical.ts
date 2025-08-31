/**
 * Comprehensive CSS Logical Properties Utilities
 * 
 * This unified system provides direction-aware styling using CSS logical properties
 * for optimal performance and automatic RTL/LTR adaptation.
 */

import { type ClassValue } from "clsx";
import { cn } from "@/lib/utils";
import type { Locale } from "@/lib/i18n/types";

/**
 * Core logical property utilities
 * These work automatically with dir="rtl" or dir="ltr" without JavaScript
 */
export const logical = {
  // Margin utilities
  marginStart: (size: string) => `ms-${size}`,
  marginEnd: (size: string) => `me-${size}`,
  marginInline: (size: string) => `mx-${size}`,
  
  // Padding utilities  
  paddingStart: (size: string) => `ps-${size}`,
  paddingEnd: (size: string) => `pe-${size}`,
  paddingInline: (size: string) => `px-${size}`,
  
  // Text alignment
  textStart: "text-start",
  textEnd: "text-end",
  
  // Flexbox alignment
  justifyStart: "justify-start",
  justifyEnd: "justify-end",
  
  // Border utilities
  borderStart: "border-s",
  borderEnd: "border-e",
} as const;

/**
 * Direction-aware component class builder
 */
export function logicalClass(...classes: ClassValue[]): string {
  return cn(classes);
}

/**
 * Advanced direction-aware utility for cases requiring JavaScript control
 */
export function directionAwareClass(
  ltrClasses: ClassValue,
  rtlClasses: ClassValue,
  locale: Locale
): string {
  const isRTL = locale === 'ar';
  return cn(isRTL ? rtlClasses : ltrClasses);
}

/**
 * Common layout patterns using logical properties
 */
export const layoutPatterns = {
  // Container with logical padding
  container: "container-padding",
  
  // Flex layouts that respect text direction
  flexRowReverse: "flex flex-row-reverse",
  flexRow: "flex flex-row",
  
  // Common spacing patterns
  spaceBetween: "flex justify-between items-center",
  spaceAround: "flex justify-around items-center",
  spaceEvenly: "flex justify-evenly items-center",
  
  // Card layouts
  cardHeader: "flex justify-between items-center ps-4 pe-4 pt-4",
  cardContent: "ps-4 pe-4 pb-4",
  cardFooter: "ps-4 pe-4 pb-4 pt-2",
  
  // Navigation patterns
  navItem: "ps-4 pe-4 text-start",
  navList: "flex gap-4",
  
  // Grid layouts
  gridCols: "grid gap-4",
  gridColsResponsive: "grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4",
} as const;

/**
 * Icon positioning utilities for RTL/LTR
 */
export const iconPosition = {
  start: "icon-start",
  end: "icon-end",
} as const;

/**
 * Form-specific logical utilities
 */
export const formLogical = {
  label: "text-start font-medium text-sm mb-2",
  input: "text-start ps-3 pe-3 py-2 w-full",
  inputWithStartIcon: "ps-10 pe-3 py-2",
  inputWithEndIcon: "ps-3 pe-10 py-2",
  inputGroup: "relative",
  helpText: "text-start text-sm text-muted-foreground mt-1",
  errorText: "text-start text-sm text-destructive mt-1",
  fieldset: "space-y-2",
  formRow: "grid grid-cols-1 md:grid-cols-2 gap-4",
} as const;

/**
 * Typography utilities with logical properties
 */
export const typography = {
  heading: "text-start font-bold",
  paragraph: "text-start leading-relaxed",
  caption: "text-start text-sm text-muted-foreground",
  overline: "text-start text-xs uppercase tracking-wide text-muted-foreground",
} as const;

/**
 * Spacing scale using logical properties
 */
export const spacing = {
  // Inline spacing (horizontal in LTR, affects text direction)
  inlineXs: "space-x-1",
  inlineSm: "space-x-2", 
  inlineMd: "space-x-4",
  inlineLg: "space-x-6",
  inlineXl: "space-x-8",
  
  // Block spacing (vertical, direction-independent)
  blockXs: "space-y-1",
  blockSm: "space-y-2",
  blockMd: "space-y-4", 
  blockLg: "space-y-6",
  blockXl: "space-y-8",
  
  // Gap utilities (for flex/grid)
  gapXs: "gap-1",
  gapSm: "gap-2",
  gapMd: "gap-4",
  gapLg: "gap-6",
  gapXl: "gap-8",
} as const;

/**
 * Direction utilities
 */
export const direction = {
  isRTL: (locale: Locale) => locale === 'ar',
  isLTR: (locale: Locale) => locale === 'en',
  getDir: (locale: Locale) => locale === 'ar' ? 'rtl' : 'ltr',
  getDirClass: (locale: Locale) => locale === 'ar' ? 'rtl' : 'ltr',
} as const;

/**
 * Helper to combine multiple logical classes with type safety
 */
export function combineLogical(...classGroups: (ClassValue | keyof typeof logical)[]): string {
  const resolvedClasses = classGroups.map(classGroup => {
    if (typeof classGroup === 'string' && classGroup in logical) {
      return logical[classGroup as keyof typeof logical];
    }
    return classGroup;
  });
  
  return cn(resolvedClasses);
}

/**
 * Responsive logical utilities
 */
export const responsive = {
  // Container queries for different screen sizes
  containerSm: "max-w-sm mx-auto px-4",
  containerMd: "max-w-md mx-auto px-4", 
  containerLg: "max-w-lg mx-auto px-4",
  containerXl: "max-w-xl mx-auto px-4",
  container2Xl: "max-w-2xl mx-auto px-4",
  
  // Responsive padding
  paddingResponsive: "px-4 md:px-6 lg:px-8",
  paddingInlineResponsive: "px-4 sm:px-6 md:px-8 lg:px-12",
  
  // Responsive margins  
  marginResponsive: "mx-4 md:mx-6 lg:mx-8",
  marginInlineResponsive: "mx-4 sm:mx-6 md:mx-8 lg:mx-12",
} as const;

/**
 * Preset component styles using logical properties
 */
export const presets = {
  button: cn(
    "inline-flex items-center justify-center gap-2",
    "ps-4 pe-4 py-2 rounded-md text-sm font-medium",
    "focus-visible:outline-none focus-visible:ring-2",
    "disabled:pointer-events-none disabled:opacity-50"
  ),
  
  card: cn(
    "rounded-lg border bg-card text-card-foreground shadow-sm",
    "ps-6 pe-6 pt-6 pb-6"
  ),
  
  input: cn(
    "flex h-10 w-full rounded-md border border-input",
    "bg-background ps-3 pe-3 py-2 text-sm ring-offset-background",
    "file:border-0 file:bg-transparent file:text-sm file:font-medium",
    "placeholder:text-muted-foreground",
    "focus-visible:outline-none focus-visible:ring-2",
    "disabled:cursor-not-allowed disabled:opacity-50"
  ),
  
  dialog: cn(
    "fixed inset-0 z-50 bg-background/80 backdrop-blur-sm",
    "data-[state=open]:animate-in data-[state=closed]:animate-out",
    "data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0"
  ),
} as const;
