import { Injectable, signal, computed, inject } from '@angular/core';
import { DOCUMENT } from '@angular/common';
import { StateService } from './state.service';

/**
 * Internationalization service for EN/AR bilingual support
 * Handles language switching, RTL layouts, and Islamic content localization
 */
@Injectable({
  providedIn: 'root'
})
export class I18nService {
  private readonly document = inject(DOCUMENT);
  private readonly stateService = inject(StateService);

  // Translation dictionaries
  private readonly translations = {
    en: {
      // Navigation
      'nav.dashboard': 'Dashboard',
      'nav.resources': 'Resources',
      'nav.access_requests': 'Access Requests',
      'nav.analytics': 'Analytics',
      'nav.admin': 'Administration',
      'nav.profile': 'Profile',
      'nav.logout': 'Logout',
      'nav.login': 'Login',
      'nav.register': 'Register',

      // Common UI
      'common.loading': 'Loading...',
      'common.error': 'Error',
      'common.success': 'Success',
      'common.warning': 'Warning',
      'common.info': 'Information',
      'common.save': 'Save',
      'common.cancel': 'Cancel',
      'common.delete': 'Delete',
      'common.edit': 'Edit',
      'common.view': 'View',
      'common.create': 'Create',
      'common.update': 'Update',
      'common.search': 'Search',
      'common.filter': 'Filter',
      'common.clear': 'Clear',
      'common.submit': 'Submit',
      'common.close': 'Close',
      'common.yes': 'Yes',
      'common.no': 'No',
      'common.confirm': 'Confirm',

      // Authentication
      'auth.welcome': 'Welcome to Itqan CMS',
      'auth.login_title': 'Sign In to Your Account',
      'auth.register_title': 'Create Your Account',
      'auth.email': 'Email Address',
      'auth.password': 'Password',
      'auth.remember_me': 'Remember me',
      'auth.forgot_password': 'Forgot password?',
      'auth.no_account': "Don't have an account?",
      'auth.have_account': 'Already have an account?',
      'auth.sign_in': 'Sign In',
      'auth.sign_up': 'Sign Up',
      'auth.signing_in': 'Signing in...',
      'auth.signing_up': 'Creating account...',
      'auth.logout_confirm': 'Are you sure you want to logout?',

      // Dashboard
      'dashboard.welcome': 'Welcome to Itqan CMS',
      'dashboard.overview': 'Overview',
      'dashboard.recent_activity': 'Recent Activity',
      'dashboard.quick_actions': 'Quick Actions',
      'dashboard.stats.total_resources': 'Total Resources',
      'dashboard.stats.pending_requests': 'Pending Requests',
      'dashboard.stats.active_users': 'Active Users',
      'dashboard.stats.published_content': 'Published Content',

      // Resources
      'resources.title': 'Quranic Resources',
      'resources.create': 'Create Resource',
      'resources.edit': 'Edit Resource',
      'resources.delete_confirm': 'Are you sure you want to delete this resource?',
      'resources.type.text': 'Quranic Text',
      'resources.type.audio': 'Audio Recitation',
      'resources.type.translation': 'Translation',
      'resources.type.tafsir': 'Commentary (Tafsir)',
      'resources.language': 'Language',
      'resources.version': 'Version',
      'resources.publisher': 'Publisher',
      'resources.published_at': 'Published Date',
      'resources.checksum': 'Integrity Checksum',

      // Access Requests
      'access_requests.title': 'Access Requests',
      'access_requests.create': 'Request Access',
      'access_requests.status.pending': 'Pending Review',
      'access_requests.status.under_review': 'Under Review',
      'access_requests.status.approved': 'Approved',
      'access_requests.status.rejected': 'Rejected',
      'access_requests.status.expired': 'Expired',
      'access_requests.status.revoked': 'Revoked',
      'access_requests.priority.low': 'Low Priority',
      'access_requests.priority.normal': 'Normal Priority',
      'access_requests.priority.high': 'High Priority',
      'access_requests.priority.urgent': 'Urgent',
      'access_requests.justification': 'Justification',
      'access_requests.admin_notes': 'Admin Notes',
      'access_requests.approve': 'Approve',
      'access_requests.reject': 'Reject',
      'access_requests.revoke': 'Revoke',

      // Islamic Content
      'islamic.quran': 'Quran',
      'islamic.hadith': 'Hadith',
      'islamic.dua': 'Dua',
      'islamic.tafsir': 'Tafsir',
      'islamic.surah': 'Surah',
      'islamic.ayah': 'Ayah',
      'islamic.verse': 'Verse',
      'islamic.reciter': 'Reciter',
      'islamic.translation': 'Translation',
      'islamic.transliteration': 'Transliteration',
      'islamic.commentary': 'Commentary',
      'islamic.arabic_text': 'Arabic Text',
      'islamic.bismillah': 'In the name of Allah, the Most Gracious, the Most Merciful',

      // Errors
      'error.network': 'Network connection error',
      'error.unauthorized': 'Unauthorized access',
      'error.forbidden': 'Access forbidden',
      'error.not_found': 'Resource not found',
      'error.server': 'Server error',
      'error.validation': 'Validation error',
      'error.unknown': 'An unexpected error occurred',

      // Language
      'language.english': 'English',
      'language.arabic': 'العربية',
      'language.switch_to_arabic': 'Switch to Arabic',
      'language.switch_to_english': 'Switch to English'
    },
    ar: {
      // Navigation
      'nav.dashboard': 'لوحة التحكم',
      'nav.resources': 'الموارد',
      'nav.access_requests': 'طلبات الوصول',
      'nav.analytics': 'التحليلات',
      'nav.admin': 'الإدارة',
      'nav.profile': 'الملف الشخصي',
      'nav.logout': 'تسجيل الخروج',
      'nav.login': 'تسجيل الدخول',
      'nav.register': 'إنشاء حساب',

      // Common UI
      'common.loading': 'جاري التحميل...',
      'common.error': 'خطأ',
      'common.success': 'نجح',
      'common.warning': 'تحذير',
      'common.info': 'معلومات',
      'common.save': 'حفظ',
      'common.cancel': 'إلغاء',
      'common.delete': 'حذف',
      'common.edit': 'تعديل',
      'common.view': 'عرض',
      'common.create': 'إنشاء',
      'common.update': 'تحديث',
      'common.search': 'بحث',
      'common.filter': 'تصفية',
      'common.clear': 'مسح',
      'common.submit': 'إرسال',
      'common.close': 'إغلاق',
      'common.yes': 'نعم',
      'common.no': 'لا',
      'common.confirm': 'تأكيد',

      // Authentication
      'auth.welcome': 'مرحباً بك في نظام إتقان',
      'auth.login_title': 'تسجيل الدخول إلى حسابك',
      'auth.register_title': 'إنشاء حساب جديد',
      'auth.email': 'عنوان البريد الإلكتروني',
      'auth.password': 'كلمة المرور',
      'auth.remember_me': 'تذكرني',
      'auth.forgot_password': 'نسيت كلمة المرور؟',
      'auth.no_account': 'ليس لديك حساب؟',
      'auth.have_account': 'لديك حساب بالفعل؟',
      'auth.sign_in': 'تسجيل الدخول',
      'auth.sign_up': 'إنشاء حساب',
      'auth.signing_in': 'جاري تسجيل الدخول...',
      'auth.signing_up': 'جاري إنشاء الحساب...',
      'auth.logout_confirm': 'هل أنت متأكد من تسجيل الخروج؟',

      // Dashboard
      'dashboard.welcome': 'مرحباً بك في نظام إتقان',
      'dashboard.overview': 'نظرة عامة',
      'dashboard.recent_activity': 'النشاط الأخير',
      'dashboard.quick_actions': 'إجراءات سريعة',
      'dashboard.stats.total_resources': 'إجمالي الموارد',
      'dashboard.stats.pending_requests': 'الطلبات المعلقة',
      'dashboard.stats.active_users': 'المستخدمون النشطون',
      'dashboard.stats.published_content': 'المحتوى المنشور',

      // Resources
      'resources.title': 'الموارد القرآنية',
      'resources.create': 'إنشاء مورد',
      'resources.edit': 'تعديل المورد',
      'resources.delete_confirm': 'هل أنت متأكد من حذف هذا المورد؟',
      'resources.type.text': 'النص القرآني',
      'resources.type.audio': 'التلاوة الصوتية',
      'resources.type.translation': 'الترجمة',
      'resources.type.tafsir': 'التفسير',
      'resources.language': 'اللغة',
      'resources.version': 'الإصدار',
      'resources.publisher': 'الناشر',
      'resources.published_at': 'تاريخ النشر',
      'resources.checksum': 'مجموع التحقق من السلامة',

      // Access Requests
      'access_requests.title': 'طلبات الوصول',
      'access_requests.create': 'طلب وصول',
      'access_requests.status.pending': 'في انتظار المراجعة',
      'access_requests.status.under_review': 'قيد المراجعة',
      'access_requests.status.approved': 'موافق عليه',
      'access_requests.status.rejected': 'مرفوض',
      'access_requests.status.expired': 'منتهي الصلاحية',
      'access_requests.status.revoked': 'ملغي',
      'access_requests.priority.low': 'أولوية منخفضة',
      'access_requests.priority.normal': 'أولوية عادية',
      'access_requests.priority.high': 'أولوية عالية',
      'access_requests.priority.urgent': 'عاجل',
      'access_requests.justification': 'المبرر',
      'access_requests.admin_notes': 'ملاحظات الإدارة',
      'access_requests.approve': 'موافقة',
      'access_requests.reject': 'رفض',
      'access_requests.revoke': 'إلغاء',

      // Islamic Content
      'islamic.quran': 'القرآن',
      'islamic.hadith': 'الحديث',
      'islamic.dua': 'الدعاء',
      'islamic.tafsir': 'التفسير',
      'islamic.surah': 'السورة',
      'islamic.ayah': 'الآية',
      'islamic.verse': 'الآية',
      'islamic.reciter': 'القارئ',
      'islamic.translation': 'الترجمة',
      'islamic.transliteration': 'النقل الحرفي',
      'islamic.commentary': 'التعليق',
      'islamic.arabic_text': 'النص العربي',
      'islamic.bismillah': 'بسم الله الرحمن الرحيم',

      // Errors
      'error.network': 'خطأ في الاتصال بالشبكة',
      'error.unauthorized': 'وصول غير مصرح به',
      'error.forbidden': 'وصول محظور',
      'error.not_found': 'المورد غير موجود',
      'error.server': 'خطأ في الخادم',
      'error.validation': 'خطأ في التحقق',
      'error.unknown': 'حدث خطأ غير متوقع',

      // Language
      'language.english': 'English',
      'language.arabic': 'العربية',
      'language.switch_to_arabic': 'التبديل إلى العربية',
      'language.switch_to_english': 'Switch to English'
    }
  };

  // Current language from state service
  readonly currentLanguage = this.stateService.currentLanguage;
  readonly isRTL = this.stateService.isRTL;

  // Computed translation function
  readonly t = computed(() => {
    const lang = this.currentLanguage();
    return (key: string, params?: Record<string, string | number>): string => {
      let translation = (this.translations[lang] as any)[key] || key;
      
      // Replace parameters if provided
      if (params) {
        Object.entries(params).forEach(([param, value]) => {
          translation = translation.replace(`{{${param}}}`, String(value));
        });
      }
      
      return translation;
    };
  });

  constructor() {
    // Initialize language from browser or localStorage
    this.initializeLanguage();
  }

  /**
   * Initialize language from browser preferences or localStorage
   */
  private initializeLanguage(): void {
    if (typeof window === 'undefined') return;

    // Check localStorage first
    const savedLanguage = localStorage.getItem('itqan_language') as 'en' | 'ar';
    if (savedLanguage && ['en', 'ar'].includes(savedLanguage)) {
      this.setLanguage(savedLanguage);
      return;
    }

    // Detect from browser language
    const browserLang = navigator.language.toLowerCase();
    if (browserLang.startsWith('ar')) {
      this.setLanguage('ar');
    } else {
      this.setLanguage('en');
    }
  }

  /**
   * Set current language
   */
  setLanguage(language: 'en' | 'ar'): void {
    this.stateService.setLanguage(language);
    this.updateDocumentAttributes(language);
  }

  /**
   * Toggle between English and Arabic
   */
  toggleLanguage(): void {
    this.stateService.toggleLanguage();
    const newLang = this.currentLanguage();
    this.updateDocumentAttributes(newLang);
  }

  /**
   * Update document attributes for RTL/LTR and language
   */
  private updateDocumentAttributes(language: 'en' | 'ar'): void {
    if (typeof document === 'undefined') return;

    const isRTL = language === 'ar';
    
    // Update document direction and language
    this.document.documentElement.dir = isRTL ? 'rtl' : 'ltr';
    this.document.documentElement.lang = language;
    
    // Update body class for styling
    const body = this.document.body;
    body.classList.toggle('rtl', isRTL);
    body.classList.toggle('ltr', !isRTL);
    body.classList.toggle('lang-ar', language === 'ar');
    body.classList.toggle('lang-en', language === 'en');

    // Update CSS custom properties for dynamic styling
    this.document.documentElement.style.setProperty('--text-direction', isRTL ? 'rtl' : 'ltr');
    this.document.documentElement.style.setProperty('--start-direction', isRTL ? 'right' : 'left');
    this.document.documentElement.style.setProperty('--end-direction', isRTL ? 'left' : 'right');
  }

  /**
   * Get translation for a key
   */
  translate(key: string, params?: Record<string, string | number>): string {
    return this.t()(key, params);
  }

  /**
   * Get all translations for current language
   */
  getAllTranslations(): Record<string, string> {
    const lang = this.currentLanguage();
    return this.translations[lang];
  }

  /**
   * Check if a translation key exists
   */
  hasTranslation(key: string): boolean {
    const lang = this.currentLanguage();
    return key in this.translations[lang];
  }

  /**
   * Format Islamic date (Hijri calendar support could be added here)
   */
  formatIslamicDate(date: Date | string): string {
    const dateObj = typeof date === 'string' ? new Date(date) : date;
    const lang = this.currentLanguage();
    
    if (lang === 'ar') {
      return dateObj.toLocaleDateString('ar-SA', {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
        calendar: 'gregory' // Could be changed to 'islamic' when supported
      });
    } else {
      return dateObj.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'long',
        day: 'numeric'
      });
    }
  }

  /**
   * Format Islamic time
   */
  formatIslamicTime(date: Date | string): string {
    const dateObj = typeof date === 'string' ? new Date(date) : date;
    const lang = this.currentLanguage();
    
    return dateObj.toLocaleTimeString(lang === 'ar' ? 'ar-SA' : 'en-US', {
      hour: '2-digit',
      minute: '2-digit',
      hour12: true
    });
  }

  /**
   * Format numbers according to locale (Arabic-Indic numerals for Arabic)
   */
  formatNumber(num: number): string {
    const lang = this.currentLanguage();
    
    if (lang === 'ar') {
      return num.toLocaleString('ar-SA');
    } else {
      return num.toLocaleString('en-US');
    }
  }

  /**
   * Get direction-aware margin/padding classes
   */
  getDirectionalClass(property: 'margin' | 'padding', side: 'start' | 'end', size: string): string {
    const isRTL = this.isRTL();
    const actualSide = side === 'start' 
      ? (isRTL ? 'right' : 'left')
      : (isRTL ? 'left' : 'right');
    
    return `${property}-${actualSide}-${size}`;
  }

  /**
   * Get text alignment class based on direction
   */
  getTextAlignClass(align: 'start' | 'end' | 'center'): string {
    if (align === 'center') return 'text-center';
    
    const isRTL = this.isRTL();
    const actualAlign = align === 'start'
      ? (isRTL ? 'right' : 'left')
      : (isRTL ? 'left' : 'right');
    
    return `text-${actualAlign}`;
  }

  /**
   * Get appropriate font family for current language
   */
  getFontFamily(): string {
    const lang = this.currentLanguage();
    
    if (lang === 'ar') {
      return "'Noto Sans Arabic', 'IBM Plex Sans Arabic', 'Amiri', 'Scheherazade New', sans-serif";
    } else {
      return "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif";
    }
  }

  /**
   * Get Quranic text font family
   */
  getQuranicFontFamily(): string {
    return "'Amiri', 'Scheherazade New', 'Noto Sans Arabic', 'IBM Plex Sans Arabic', sans-serif";
  }
}
