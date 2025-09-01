# Itqan CMS - Navigation Menu Documentation

**Date:** 2024-12-19  
**Author:** AI Assistant  

## Overview
Documentation of the top navigation menu items for the Itqan CMS platform, supporting bilingual interface (English/Arabic) with proper RTL layout for Arabic users.

## Top Navigation Menu Items

### Primary Navigation Menu

| Priority | English | Arabic | Route | Authentication Required | Description |
|----------|---------|---------|-------|-------------------------|-------------|
| 1 | Home | الرئيسية | `/` | ❌ No | Asset Store landing page with resource discovery |
| 2 | Publishers | الناشرين | `/publishers` | ❌ No | Publisher directory and profiles |  
| 3 | Content & Technical Standards | معايير المحتوى والتقنية | `/content-standards` | ❌ No | Public documentation for proper API usage |
| 4 | About the Project | عن المشروع | `/about` | ❌ No | Information about Itqan CMS platform |
| 5 | Login | تسجيل الدخول | `/auth/login` | ❌ No | User authentication portal |

### Secondary Navigation Elements

| Element | English | Arabic | Description |
|---------|---------|---------|-------------|
| Language Switcher | EN / العربية | ع / English | Toggle between English and Arabic interface |
| Search Bar | Search | البحث | Global resource search functionality |

## Technical Implementation

### Frontend Components
- **TopNavigationComponent**: `frontend/src/app/shared/components/top-navigation.component.ts`
- **I18nService**: `frontend/src/app/core/services/i18n.service.ts`

### Localization Keys
```typescript
// Navigation translations
'nav.home': 'Home' / 'الرئيسية'
'nav.publishers': 'Publishers' / 'الناشرين'  
'nav.content_standards': 'Content & Technical Standards' / 'معايير المحتوى والتقنية'
'nav.about': 'About the Project' / 'عن المشروع'
'nav.login': 'Login' / 'تسجيل الدخول'
'nav.language': 'Language' / 'اللغة'
```

### RTL Support
- Automatic layout direction changes for Arabic (`dir="rtl"`)
- Proper Arabic typography using 'Noto Sans Arabic' font family
- Right-to-left navigation flow and alignment
- Islamic design patterns and cultural considerations

### Brand Integration
- **Logo**: Itqan CMS logo with Arabic "إتقان" text
- **Primary Color**: #669B80 (Islamic green)
- **Dark Accent**: #22433D
- **Design**: Clean, modern interface respecting Islamic aesthetic principles

## Navigation Flow

### Unauthenticated Users
1. **Home** → Asset Store (public resource discovery)
2. **Content Standards** → API documentation and usage guidelines  
3. **Publishers** → Publisher directory and profiles
4. **About** → Platform information
5. **Login** → Authentication portal

### Authenticated Users
- Same navigation with additional access to protected resources
- Resource download capabilities
- Access request functionality  
- Personal dashboard access

## Islamic Content Considerations
- All navigation respects Islamic content principles
- Arabic-first approach for Islamic terminology
- Scholarly attribution requirements highlighted in documentation
- Content integrity verification throughout user journey

## Next Steps
1. Implement Asset Store as primary home page (ADMIN-001)
2. Complete Publishers directory page
3. Finalize About page content  
4. Test complete navigation flow in both languages

## References
- Frontend Implementation: `frontend/src/app/shared/components/top-navigation.component.ts`
- Screen Flow Documentation: `ai-memory-bank/tasks-screens-flow.csv`
- Wireframes: `docs/screens/ADMIN-001.png` (Asset Store)
- Original Task: Navigation implemented in Tasks 12-16 and enhanced with localization
