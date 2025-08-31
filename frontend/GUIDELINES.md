# Itqan CMS - Development Guidelines

## 📋 Overview

This document establishes the development standards, best practices, and guidelines for maintaining the Itqan CMS codebase. All developers and AI agents **MUST** follow these guidelines to ensure consistency, quality, and protection of core features.

## 🎯 Core Principles

### 1. **Quality Standards**
- **Type Safety First**: Everything must be strictly typed with TypeScript
- **SSR Compliance**: Maintain server-side rendering excellence
- **Performance Focus**: Optimize for speed and minimal bundle size
- **Security Priority**: Implement security best practices
- **Accessibility**: Ensure WCAG compliance

### 2. **Consistency Rules**
- **Uniform Naming**: Follow established naming conventions
- **Structured Organization**: Maintain clean file/folder hierarchy
- **Code Style**: Use consistent formatting and patterns
- **Documentation**: Document all public APIs and complex logic

## 🏗️ Architecture Guidelines

### **Directory Structure - STRICTLY ENFORCED**

```
src/
├── app/                          # Next.js App Router (CORE - DO NOT MODIFY STRUCTURE)
│   ├── [locale]/                 # Dynamic locale routing (PROTECTED)
│   │   ├── layout.tsx            # Root layout (CRITICAL - SSR)
│   │   ├── page.tsx              # Homepage (CRITICAL - SSR)
│   │   ├── loading.tsx           # Loading UI
│   │   ├── error.tsx             # Error boundary
│   │   └── not-found.tsx         # 404 page
│   ├── globals.css               # Global styles (CRITICAL - RTL/LTR)
│   └── favicon.ico
├── components/                   # React components
│   ├── ui/                       # Atomic UI components (shadcn/ui)
│   ├── providers/                # React context providers (PROTECTED)
│   │   ├── locale-provider.tsx   # I18n context (CRITICAL)
│   │   └── theme-provider.tsx    # Theme context (CRITICAL)
│   ├── [feature-name]/           # Feature-specific components
│   └── *.tsx                     # Shared components
├── lib/                          # Utility libraries
│   ├── i18n/                     # Internationalization (PROTECTED)
│   │   ├── types.ts              # I18n type definitions (CRITICAL)
│   │   ├── utils.ts              # Locale utilities (CRITICAL)
│   │   └── dictionaries.ts       # Translation loading (CRITICAL)
│   ├── styles/                   # Style utilities
│   │   └── logical.ts            # CSS logical properties (CRITICAL)
│   ├── utils.ts                  # General utilities
│   └── env.ts                    # Environment configuration (PROTECTED)
├── dictionaries/                 # Translation files (PROTECTED)
│   ├── ar.json                   # Arabic translations (CRITICAL)
│   └── en.json                   # English translations (CRITICAL)

└── middleware.ts                 # Next.js middleware (CRITICAL - ROUTING)
```

### **Protected/Critical Files - REQUIRE SPECIAL CARE**

#### 🔒 **CRITICAL FILES (Extreme caution required)**
- `src/middleware.ts` - Routing and security
- `src/app/[locale]/layout.tsx` - SSR root layout
- `src/lib/i18n/types.ts` - Type definitions
- `src/lib/i18n/utils.ts` - Core i18n logic
- `src/app/globals.css` - RTL/LTR styles
- `package.json` - Dependencies and scripts
- `next.config.ts` - Next.js configuration
- `tsconfig.json` - TypeScript configuration

#### 🛡️ **PROTECTED DIRECTORIES (Review required)**
- `src/lib/i18n/` - Internationalization system
- `src/components/providers/` - React contexts
- `src/dictionaries/` - Translation files
- `src/lib/styles/` - Styling system

## 📝 Naming Conventions

### **Files and Directories**
```typescript
// ✅ CORRECT
components/language-switcher.tsx    // kebab-case for files
lib/i18n/utils.ts                  // kebab-case for files
// ❌ INCORRECT
components/LanguageSwitcher.tsx     // PascalCase not allowed
lib/i18n/Utils.ts                  // PascalCase not allowed
```

### **React Components**
```typescript
// ✅ CORRECT - PascalCase for component names
export function LanguageSwitcher() {}
export function ThemeProvider() {}
export default function HomePage() {}

// ❌ INCORRECT
export function languageSwitcher() {}  // camelCase not allowed
export function theme_provider() {}    // snake_case not allowed
```

### **Variables and Functions**
```typescript
// ✅ CORRECT - camelCase
const currentLocale = 'ar';
const isValidLocale = (locale: string) => {};
const getDictionary = async () => {};

// ❌ INCORRECT
const current_locale = 'ar';           // snake_case not allowed
const IsValidLocale = () => {};        // PascalCase not allowed
```

### **Types and Interfaces**
```typescript
// ✅ CORRECT - PascalCase
type Locale = 'ar' | 'en';
interface HomePageProps {}
interface LocaleContextType {}

// ❌ INCORRECT
type locale = 'ar' | 'en';             // camelCase not allowed
interface homePageProps {}             // camelCase not allowed
```

### **Constants**
```typescript
// ✅ CORRECT - SCREAMING_SNAKE_CASE for global constants
const DEFAULT_LOCALE = 'ar';
const SUPPORTED_LOCALES = ['ar', 'en'];

// ✅ CORRECT - camelCase for local constants
const defaultLocale = 'ar';
const locales = ['ar', 'en'] as const;
```

## 🌍 Internationalization Guidelines

### **CRITICAL RULES - NEVER VIOLATE**

#### 1. **Locale Type Safety**
```typescript
// ✅ ALWAYS use the Locale type
import type { Locale } from '@/lib/i18n/types';

// ✅ ALWAYS validate before casting
if (!isValidLocale(locale)) {
  notFound();
}
const validatedLocale = locale as Locale;

// ❌ NEVER use string directly
const locale: string = 'ar'; // Wrong!
```

#### 2. **Translation Loading**
```typescript
// ✅ CORRECT - Server components
const dict = await getDictionary(locale);

// ✅ CORRECT - Client components
const { t, dict } = useTranslation();

// ❌ NEVER import translations directly
import ar from '@/dictionaries/ar.json'; // Wrong!
```

#### 3. **RTL/LTR Handling**
```typescript
// ✅ ALWAYS use logical properties
import { logical, direction } from '@/lib/styles/logical';

// ✅ CORRECT usage
className={cn(logical.paddingStart('4'), logical.textStart)}
const isRTL = direction.isRTL(locale);

// ❌ NEVER use hardcoded directional classes
className="pl-4 text-left" // Wrong! Not RTL-aware
```

#### 4. **URL Structure**
```typescript
// ✅ CORRECT pattern
/ar/            // Arabic homepage
/en/            // English homepage
/ar/about       // Arabic about page
/en/about       // English about page

// ❌ WRONG patterns
/about?lang=ar  // Query parameters not allowed
/ar-SA/         // Region codes not supported
```

### **Translation Management**

#### Adding New Translations
```json
// 1. Add to src/dictionaries/ar.json
{
  "newKey": "النص العربي"
}

// 2. Add to src/dictionaries/en.json  
{
  "newKey": "English text"
}

// 3. Update type in src/lib/i18n/types.ts
export type Dictionary = {
  // ... existing keys
  newKey: string;
};
```

#### Using Translations
```typescript
// ✅ Server components
export default async function MyPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  const validatedLocale = locale as Locale;
  const dict = await getDictionary(validatedLocale);
  
  return <h1>{dict.newKey}</h1>;
}

// ✅ Client components
"use client";
export function MyComponent() {
  const { t } = useTranslation();
  return <h1>{t('newKey')}</h1>;
}
```

## 🎨 Styling Guidelines

### **CSS Logical Properties - MANDATORY**

#### Always Use Logical Properties
```css
/* ✅ CORRECT - Logical properties */
.element {
  padding-inline-start: 1rem;    /* ps-4 */
  padding-inline-end: 1rem;      /* pe-4 */
  margin-inline-start: auto;     /* ms-auto */
  text-align: start;             /* text-start */
}

/* ❌ WRONG - Physical properties */
.element {
  padding-left: 1rem;            /* Not RTL-aware */
  padding-right: 1rem;           /* Not RTL-aware */
  margin-left: auto;             /* Not RTL-aware */
  text-align: left;              /* Not RTL-aware */
}
```

#### Tailwind Class Usage
```typescript
// ✅ CORRECT - Use logical utilities
import { logical, layoutPatterns, spacing } from '@/lib/styles/logical';

className={cn(
  logical.paddingStart('4'),     // ps-4
  logical.textStart,             // text-start
  layoutPatterns.spaceBetween,   // flex justify-between items-center
  spacing.gapMd                  // gap-4
)}

// ❌ WRONG - Physical directional classes
className="pl-4 text-left ml-auto" // Not RTL-aware
```

### **Component Styling Patterns**
```typescript
// ✅ CORRECT - Use cn() utility for class merging
import { cn } from '@/lib/utils';

className={cn(
  "base-classes",
  conditionalClass && "conditional-classes",
  props.className
)}

// ❌ WRONG - String concatenation
className={"base-classes " + (conditionalClass ? "conditional-classes" : "")}
```

## 🔒 Theme System Guidelines

### **Theme Provider Usage**
```typescript
// ✅ CORRECT - Use the enhanced provider
import { ThemeProvider } from '@/components/providers/theme-provider';

<ThemeProvider>
  {children}
</ThemeProvider>

// ❌ WRONG - Don't import next-themes directly in app code
import { ThemeProvider } from 'next-themes'; // Wrong!
```

### **Theme-Aware Components**
```typescript
// ✅ CORRECT - Client component with theme
"use client";
import { useTheme } from 'next-themes';

export function ThemeAwareComponent() {
  const { theme, setTheme } = useTheme();
  // Component logic
}
```

## ⚙️ Configuration Guidelines

### **Environment Variables**
```typescript
// ✅ ALWAYS use the env utility
import { env, isDevelopment } from '@/lib/env';

const backendUrl = env.NEXT_PUBLIC_BACKEND_URL;
if (isDevelopment) {
  console.log('Development mode');
}

// ❌ NEVER access process.env directly in components
const url = process.env.NEXT_PUBLIC_BACKEND_URL; // Wrong!
```

### **Next.js Configuration**
```typescript
// ✅ CRITICAL - next.config.ts structure
const nextConfig: NextConfig = {
  experimental: {
    optimizePackageImports: ['lucide-react'], // Package optimization
  },
  async redirects() {
    return [
      {
        source: '/',
        destination: '/ar',     // CRITICAL - Default to Arabic
        permanent: false,
      },
    ];
  },
};
```



## 📦 Dependency Management

### **Package Installation Rules**
```bash
# ✅ CORRECT - Always specify exact versions for critical deps
npm install next@15.5.0
npm install react@19.1.0
npm install typescript@^5

# ✅ CORRECT - Group related dependencies
npm install @radix-ui/react-slot class-variance-authority clsx

# ❌ WRONG - Don't install without version specification for core deps
npm install next  # Could break compatibility
```

### **Import Guidelines**
```typescript
// ✅ CORRECT - Import order
import React from 'react';                    // External libraries
import { NextRequest } from 'next/server';    // Next.js imports
import { Button } from '@/components/ui/button'; // Internal components
import { cn } from '@/lib/utils';             // Internal utilities
import type { Locale } from '@/lib/i18n/types'; // Type imports last

// ✅ CORRECT - Group imports
import { 
  logical, 
  layoutPatterns, 
  spacing 
} from '@/lib/styles/logical';

// ❌ WRONG - Scattered imports
import { logical } from '@/lib/styles/logical';
import React from 'react';
import { spacing } from '@/lib/styles/logical';
```

## 🚨 Critical Security Rules

### **Middleware Security**
```typescript
// ✅ CRITICAL - Always include security headers
const response = NextResponse.next();
response.headers.set('X-Content-Type-Options', 'nosniff');
response.headers.set('X-Frame-Options', 'DENY');
response.headers.set('X-XSS-Protection', '1; mode=block');
```

### **Input Validation**
```typescript
// ✅ ALWAYS validate user inputs
function isValidLocale(locale: string): locale is Locale {
  return locales.includes(locale as Locale);
}

// ✅ ALWAYS validate before using
if (!isValidLocale(userInput)) {
  throw new Error('Invalid locale');
}
```

## 🔄 Code Review Checklist

### **Before Submitting Changes**

#### ✅ **Type Safety**
- [ ] All variables are properly typed
- [ ] No `any` types used
- [ ] Proper type guards implemented
- [ ] Interface definitions updated

#### ✅ **Internationalization**
- [ ] Uses Locale type correctly
- [ ] No hardcoded strings (use translations)
- [ ] RTL/LTR compatibility maintained
- [ ] Logical properties used for styling

#### ✅ **Performance**
- [ ] Server components preferred over client components
- [ ] Proper code splitting maintained
- [ ] No unnecessary re-renders
- [ ] Bundle size impact considered

#### ✅ **Architecture**
- [ ] File placed in correct directory
- [ ] Naming conventions followed
- [ ] No circular dependencies
- [ ] Proper error handling



#### ✅ **Build & Lint**
- [ ] `npm run build` succeeds
- [ ] `npm run lint` passes
- [ ] `npm run type-check` passes
- [ ] No console errors/warnings

## 🚫 Forbidden Practices

### **NEVER DO THESE**

```typescript
// ❌ NEVER modify core i18n types without approval
export type Locale = 'ar' | 'en' | 'fr'; // Requires architecture review

// ❌ NEVER bypass locale validation
const locale = pathname.split('/')[1] as Locale; // Wrong! Use validation

// ❌ NEVER use physical CSS properties in new code
className="ml-4 text-left" // Use logical properties instead

// ❌ NEVER import translations directly
import ar from '@/dictionaries/ar.json'; // Use getDictionary() instead

// ❌ NEVER modify middleware without extreme caution
// This file controls routing and security - requires careful review

// ❌ NEVER add client-side code to server components
"use client"; // Only when absolutely necessary

// ❌ NEVER use hardcoded theme values
const isDark = document.body.classList.contains('dark'); // Use useTheme()

// ❌ NEVER modify tsconfig.json paths without understanding impact
"paths": { "@/*": ["./different/path/*"] } // Could break everything
```

## 🔧 Development Workflow

### **Adding New Features**
1. **Plan**: Review architecture impact
2. **Design**: Follow established patterns
3. **Implement**: Use guidelines and conventions
4. **Review**: Self-check against guidelines
5. **Document**: Update relevant documentation

### **Modifying Existing Features**
1. **Understand**: Read existing code thoroughly
2. **Preserve**: Maintain backward compatibility
3. **Enhance**: Follow improvement patterns
4. **Validate**: Verify all affected areas work correctly
5. **Document**: Update changed behavior

### **Emergency Fixes**
1. **Assess**: Understand the urgency
2. **Isolate**: Minimize change scope
3. **Validate**: Verify fix doesn't break core features
4. **Document**: Explain the emergency change
5. **Follow-up**: Plan proper solution if needed

## 📚 Reference Quick Guide

### **Import Statements**
```typescript
// Type imports
import type { Locale } from '@/lib/i18n/types';

// I18n utilities
import { isValidLocale, direction } from '@/lib/i18n/utils';
import { getDictionary } from '@/lib/i18n/dictionaries';

// Styling utilities  
import { logical, layoutPatterns } from '@/lib/styles/logical';
import { cn } from '@/lib/utils';

// Components
import { Button } from '@/components/ui/button';
import { ThemeProvider } from '@/components/providers/theme-provider';
```

### **Common Patterns**
```typescript
// Page component pattern
export default async function MyPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  const validatedLocale = locale as Locale;
  const dict = await getDictionary(validatedLocale);
  
  return <div>{dict.title}</div>;
}

// Client component pattern
"use client";
export function MyClientComponent() {
  const { t, locale, isRTL } = useTranslation();
  
  return (
    <div className={cn(logical.textStart)}>
      {t('title')}
    </div>
  );
}
```

---

## 🎯 **REMEMBER: These guidelines are MANDATORY**

Following these guidelines ensures:
- **Consistency** across the entire codebase
- **Quality** that meets production standards  
- **Maintainability** for future development
- **Protection** of critical features
- **Performance** optimization
- **Security** best practices

**Any deviation from these guidelines requires explicit approval and documentation of the reasoning.**
