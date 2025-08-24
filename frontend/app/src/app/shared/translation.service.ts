import { Injectable, signal } from '@angular/core';

export interface Translations {
  // Header
  'header.title': string;
  'header.subtitle': string;
  'header.ltr': string;
  'header.rtl': string;
  
  // Demo Gallery
  'demo.title': string;
  'demo.contentStandards': string;
  'demo.homeUnauth': string;
  'demo.homeAuth': string;
  'demo.login': string;
  'demo.registerOAuth': string;
  'demo.registerEmail': string;
  'demo.profileCapture': string;
  'demo.resourceDetails': string;
  'demo.licenseDetails': string;
  'demo.publisherDetails': string;
  'demo.resourceDialog': string;
  'demo.licenseTermsDialog': string;
  'demo.licenseTermsConfirm': string;
  
  // Content Standards
  'contentStandards.title': string;
  'contentStandards.subtitle': string;
  'contentStandards.description': string;
  'contentStandards.section1.title': string;
  'contentStandards.section1.desc': string;
  'contentStandards.section1.rule1': string;
  'contentStandards.section1.rule2': string;
  'contentStandards.section1.rule3': string;
  'contentStandards.section2.title': string;
  'contentStandards.section2.desc': string;
  'contentStandards.section2.rule1': string;
  'contentStandards.section2.rule2': string;
  'contentStandards.section2.rule3': string;
  'contentStandards.section3.title': string;
  'contentStandards.section3.desc': string;
  'contentStandards.section3.rule1': string;
  'contentStandards.section3.rule2': string;
  'contentStandards.section3.rule3': string;
  'contentStandards.footer': string;
  
  // Home Pages
  'home.unauth.title': string;
  'home.unauth.description': string;
  'home.unauth.login': string;
  'home.unauth.register': string;
  'home.auth.title': string;
  'home.auth.description': string;
  'home.auth.goToPublisher': string;
  
  // Authentication
  'auth.login.title': string;
  'auth.login.welcome': string;
  'auth.login.email': string;
  'auth.login.password': string;
  'auth.login.loginButton': string;
  'auth.login.oauthButton': string;
  'auth.login.register': string;
  'auth.register.oauth.title': string;
  'auth.register.oauth.github': string;
  'auth.register.oauth.google': string;
  'auth.register.email.title': string;
  'auth.register.email.createAccount': string;
  'auth.profile.title': string;
  'auth.profile.fullName': string;
  'auth.profile.role': string;
  'auth.profile.organization': string;
  'auth.profile.save': string;
  'auth.profile.developer': string;
  'auth.profile.publisher': string;
  
  // Resources
  'resource.title': string;
  'resource.description': string;
  'resource.viewLicense': string;
  'resource.openDetails': string;
  
  // License
  'license.title': string;
  'license.description': string;
  'license.rule1': string;
  'license.rule2': string;
  'license.acceptDownload': string;
  
  // Publisher
  'publisher.title': string;
  'publisher.description': string;
  'publisher.table.name': string;
  'publisher.table.version': string;
  'publisher.table.lang': string;
  'publisher.table.license': string;
  'publisher.table.view': string;
  
  // Dialogs
  'dialog.resource.title': string;
  'dialog.resource.content': string;
  'dialog.resource.close': string;
  'dialog.license.title': string;
  'dialog.license.content': string;
  'dialog.license.cancel': string;
  'dialog.license.accept': string;
  'dialog.confirm.title': string;
  'dialog.confirm.content': string;
  'dialog.confirm.back': string;
  'dialog.confirm.confirm': string;
}

const englishTranslations: Translations = {
  // Header
  'header.title': 'Itqan CMS',
  'header.subtitle': 'Quranic Content Management System',
  'header.ltr': 'LTR',
  'header.rtl': 'RTL',
  
  // Demo Gallery
  'demo.title': 'Demo Gallery',
  'demo.contentStandards': 'Content Standards',
  'demo.homeUnauth': 'Home (Unauth)',
  'demo.homeAuth': 'Home (Auth)',
  'demo.login': 'Login',
  'demo.registerOAuth': 'Register (GitHub/Google)',
  'demo.registerEmail': 'Register (Email)',
  'demo.profileCapture': 'Profile Capture',
  'demo.resourceDetails': 'Resource Details',
  'demo.licenseDetails': 'License Details',
  'demo.publisherDetails': 'Publisher Details',
  'demo.resourceDialog': 'Resource Dialog',
  'demo.licenseTermsDialog': 'License Terms Dialog',
  'demo.licenseTermsConfirm': 'License Terms Confirm',
  
  // Content Standards
  'contentStandards.title': 'Content Standards',
  'contentStandards.subtitle': 'Guidelines for Quranic Data Submission',
  'contentStandards.description': 'To ensure quality and consistency across all Quranic resources, please follow these comprehensive standards when submitting content to the Itqan CMS platform.',
  'contentStandards.section1.title': 'Text Format & Encoding',
  'contentStandards.section1.desc': 'All textual content must adhere to Unicode standards for proper display and processing.',
  'contentStandards.section1.rule1': 'Use UTF-8 encoding for all text files',
  'contentStandards.section1.rule2': 'Normalize Arabic diacritics using Unicode NFC form',
  'contentStandards.section1.rule3': 'Include proper verse markers and chapter divisions',
  'contentStandards.section2.title': 'Metadata Requirements',
  'contentStandards.section2.desc': 'Comprehensive metadata ensures proper attribution and discoverability.',
  'contentStandards.section2.rule1': 'Provide complete license and attribution information',
  'contentStandards.section2.rule2': 'Include language codes (ISO 639-1/639-3)',
  'contentStandards.section2.rule3': 'Specify schema version and content type',
  'contentStandards.section3.title': 'Quality Assurance',
  'contentStandards.section3.desc': 'All submissions undergo review to maintain platform integrity.',
  'contentStandards.section3.rule1': 'Content must be verified against authentic sources',
  'contentStandards.section3.rule2': 'Include source documentation and methodology',
  'contentStandards.section3.rule3': 'Follow naming conventions for files and resources',
  'contentStandards.footer': 'For detailed technical specifications, please refer to our API documentation or contact the Itqan team.',
  
  // Home Pages
  'home.unauth.title': 'Itqan CMS',
  'home.unauth.description': 'Open Quranic data for developers and publishers.',
  'home.unauth.login': 'Login',
  'home.unauth.register': 'Register',
  'home.auth.title': 'Welcome back',
  'home.auth.description': 'Your recent resources and publishers.',
  'home.auth.goToPublisher': 'Go to Publisher',
  
  // Authentication
  'auth.login.title': 'Login',
  'auth.login.welcome': 'Welcome Back',
  'auth.login.email': 'Email',
  'auth.login.password': 'Password',
  'auth.login.loginButton': 'Login',
  'auth.login.oauthButton': 'Login with GitHub/Google',
  'auth.login.register': 'Sign up now',
  'auth.register.oauth.title': 'Register via OAuth',
  'auth.register.oauth.github': 'Continue with GitHub',
  'auth.register.oauth.google': 'Continue with Google',
  'auth.register.email.title': 'Register with Email',
  'auth.register.email.createAccount': 'Create Account',
  'auth.profile.title': 'Complete your profile',
  'auth.profile.fullName': 'Full Name',
  'auth.profile.role': 'Role',
  'auth.profile.organization': 'Organization',
  'auth.profile.save': 'Save',
  'auth.profile.developer': 'Developer',
  'auth.profile.publisher': 'Publisher',
  
  // Resources
  'resource.title': 'Resource: Quran Text v1',
  'resource.description': 'Arabic text with diacritics; format: JSON; size: 12MB.',
  'resource.viewLicense': 'View License Terms',
  'resource.openDetails': 'Open Details Popup',
  
  // License
  'license.title': 'License: CC0',
  'license.description': 'Public domain dedication.',
  'license.rule1': 'Free to copy, modify, distribute.',
  'license.rule2': 'No attribution required.',
  'license.acceptDownload': 'Accept & Download',
  
  // Publisher
  'publisher.title': 'Publisher: Itqan',
  'publisher.description': 'Trusted Quranic resources.',
  'publisher.table.name': 'Name',
  'publisher.table.version': 'Version',
  'publisher.table.lang': 'Lang',
  'publisher.table.license': 'License',
  'publisher.table.view': 'View',
  
  // Dialogs
  'dialog.resource.title': 'Resource Details',
  'dialog.resource.content': 'Popup content for resource details and actions.',
  'dialog.resource.close': 'Close',
  'dialog.license.title': 'License Terms',
  'dialog.license.content': 'Terms and conditions preview for the selected license.',
  'dialog.license.cancel': 'Cancel',
  'dialog.license.accept': 'Accept',
  'dialog.confirm.title': 'Confirm Acceptance',
  'dialog.confirm.content': 'You are about to accept the license and start download.',
  'dialog.confirm.back': 'Back',
  'dialog.confirm.confirm': 'Confirm',
};

const arabicTranslations: Translations = {
  // Header
  'header.title': 'نظام إدارة المحتوى إتقان',
  'header.subtitle': 'نظام إدارة المحتوى القرآني',
  'header.ltr': 'يسار إلى يمين',
  'header.rtl': 'يمين إلى يسار',
  
  // Demo Gallery
  'demo.title': 'معرض العروض التوضيحية',
  'demo.contentStandards': 'معايير المحتوى',
  'demo.homeUnauth': 'الصفحة الرئيسية (غير مسجل)',
  'demo.homeAuth': 'الصفحة الرئيسية (مسجل)',
  'demo.login': 'تسجيل الدخول',
  'demo.registerOAuth': 'التسجيل (GitHub/Google)',
  'demo.registerEmail': 'التسجيل (البريد الإلكتروني)',
  'demo.profileCapture': 'إكمال الملف الشخصي',
  'demo.resourceDetails': 'تفاصيل المورد',
  'demo.licenseDetails': 'تفاصيل الترخيص',
  'demo.publisherDetails': 'تفاصيل الناشر',
  'demo.resourceDialog': 'نافذة المورد',
  'demo.licenseTermsDialog': 'نافذة شروط الترخيص',
  'demo.licenseTermsConfirm': 'تأكيد شروط الترخيص',
  
  // Content Standards
  'contentStandards.title': 'معايير المحتوى',
  'contentStandards.subtitle': 'إرشادات تقديم البيانات القرآنية',
  'contentStandards.description': 'لضمان الجودة والاتساق عبر جميع الموارد القرآنية، يرجى اتباع هذه المعايير الشاملة عند تقديم المحتوى إلى منصة نظام إدارة المحتوى إتقان.',
  'contentStandards.section1.title': 'تنسيق النص والترميز',
  'contentStandards.section1.desc': 'يجب أن يلتزم جميع المحتوى النصي بمعايير يونيكود للعرض والمعالجة الصحيحة.',
  'contentStandards.section1.rule1': 'استخدم ترميز UTF-8 لجميع الملفات النصية',
  'contentStandards.section1.rule2': 'قم بتطبيع علامات التشكيل العربية باستخدام نموذج Unicode NFC',
  'contentStandards.section1.rule3': 'أدرج علامات الآيات وتقسيمات السور بشكل صحيح',
  'contentStandards.section2.title': 'متطلبات البيانات الوصفية',
  'contentStandards.section2.desc': 'البيانات الوصفية الشاملة تضمن الإسناد الصحيح وإمكانية الاكتشاف.',
  'contentStandards.section2.rule1': 'قدم معلومات كاملة عن الترخيص والإسناد',
  'contentStandards.section2.rule2': 'أدرج رموز اللغة (ISO 639-1/639-3)',
  'contentStandards.section2.rule3': 'حدد إصدار المخطط ونوع المحتوى',
  'contentStandards.section3.title': 'ضمان الجودة',
  'contentStandards.section3.desc': 'جميع المساهمات تخضع للمراجعة للحفاظ على سلامة المنصة.',
  'contentStandards.section3.rule1': 'يجب التحقق من المحتوى مقابل المصادر الموثقة',
  'contentStandards.section3.rule2': 'أدرج وثائق المصدر والمنهجية',
  'contentStandards.section3.rule3': 'اتبع اصطلاحات التسمية للملفات والموارد',
  'contentStandards.footer': 'للمواصفات التقنية التفصيلية، يرجى الرجوع إلى وثائق API الخاصة بنا أو الاتصال بفريق إتقان.',
  
  // Home Pages
  'home.unauth.title': 'نظام إدارة المحتوى إتقان',
  'home.unauth.description': 'بيانات قرآنية مفتوحة للمطورين والناشرين.',
  'home.unauth.login': 'تسجيل الدخول',
  'home.unauth.register': 'التسجيل',
  'home.auth.title': 'مرحباً بعودتك',
  'home.auth.description': 'مواردك وناشريك الحديثين.',
  'home.auth.goToPublisher': 'اذهب إلى الناشر',
  
  // Authentication
  'auth.login.title': 'تسجيل الدخول',
  'auth.login.welcome': 'مرحباً بعودتك',
  'auth.login.email': 'البريد الإلكتروني',
  'auth.login.password': 'كلمة المرور',
  'auth.login.loginButton': 'تسجيل الدخول',
  'auth.login.oauthButton': 'تسجيل الدخول بـ GitHub/Google',
  'auth.login.register': 'سجل الآن',
  'auth.register.oauth.title': 'التسجيل عبر OAuth',
  'auth.register.oauth.github': 'المتابعة مع GitHub',
  'auth.register.oauth.google': 'المتابعة مع Google',
  'auth.register.email.title': 'التسجيل بالبريد الإلكتروني',
  'auth.register.email.createAccount': 'إنشاء حساب',
  'auth.profile.title': 'أكمل ملفك الشخصي',
  'auth.profile.fullName': 'الاسم الكامل',
  'auth.profile.role': 'الدور',
  'auth.profile.organization': 'المؤسسة',
  'auth.profile.save': 'حفظ',
  'auth.profile.developer': 'مطور',
  'auth.profile.publisher': 'ناشر',
  
  // Resources
  'resource.title': 'المورد: نص القرآن الإصدار 1',
  'resource.description': 'نص عربي مع التشكيل؛ التنسيق: JSON؛ الحجم: 12 ميجابايت.',
  'resource.viewLicense': 'عرض شروط الترخيص',
  'resource.openDetails': 'فتح نافذة التفاصيل',
  
  // License
  'license.title': 'الترخيص: CC0',
  'license.description': 'إهداء للملك العام.',
  'license.rule1': 'حر في النسخ والتعديل والتوزيع.',
  'license.rule2': 'لا يتطلب إسناد.',
  'license.acceptDownload': 'قبول وتحميل',
  
  // Publisher
  'publisher.title': 'الناشر: إتقان',
  'publisher.description': 'موارد قرآنية موثوقة.',
  'publisher.table.name': 'الاسم',
  'publisher.table.version': 'الإصدار',
  'publisher.table.lang': 'اللغة',
  'publisher.table.license': 'الترخيص',
  'publisher.table.view': 'عرض',
  
  // Dialogs
  'dialog.resource.title': 'تفاصيل المورد',
  'dialog.resource.content': 'محتوى النافذة المنبثقة لتفاصيل المورد والإجراءات.',
  'dialog.resource.close': 'إغلاق',
  'dialog.license.title': 'شروط الترخيص',
  'dialog.license.content': 'معاينة الشروط والأحكام للترخيص المحدد.',
  'dialog.license.cancel': 'إلغاء',
  'dialog.license.accept': 'قبول',
  'dialog.confirm.title': 'تأكيد القبول',
  'dialog.confirm.content': 'أنت على وشك قبول الترخيص وبدء التحميل.',
  'dialog.confirm.back': 'رجوع',
  'dialog.confirm.confirm': 'تأكيد',
};

@Injectable({ providedIn: 'root' })
export class TranslationService {
  private currentLang = signal<'en' | 'ar'>('en');
  
  lang = this.currentLang.asReadonly();
  
  setLanguage(lang: 'en' | 'ar') {
    this.currentLang.set(lang);
  }
  
  translate(key: keyof Translations): string {
    const translations = this.currentLang() === 'ar' ? arabicTranslations : englishTranslations;
    return translations[key] || key;
  }
  
  t = this.translate.bind(this);
}
