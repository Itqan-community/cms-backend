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
      'common.or': 'or',
      'common.and': 'and',

      // App
      'app.name': 'Itqan CMS',

      // Navigation
      'nav.home': 'Home',
      'nav.about': 'About',
      'nav.publishers': 'Publishers',
      'nav.content_standards': 'Content & Technical Standards',
      'nav.documentation': 'Documentation',
      'nav.api_standards': 'API Standards',
      'nav.language': 'Language',
      'nav.switch_language': 'Switch Language',

      // Authentication
      'auth.welcome': 'Welcome to Itqan CMS',
      'auth.get_started': 'Get Started',
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
      'auth.continue_github': 'Continue with GitHub',
      'auth.continue_google': 'Continue with Google',
      'auth.continue_email': 'Continue with Email',
      'auth.forgot_password_link': 'Forgot your password?',
      'auth.terms_agreement': 'By signing in, you agree to our',
      'auth.terms_service': 'Terms of Service',
      'auth.privacy_policy': 'Privacy Policy',
      'auth.register_free': 'Sign up for free',

      // Dashboard
      'dashboard.welcome': 'Welcome to Itqan CMS',
      'dashboard.overview': 'Overview',
      'dashboard.recent_activity': 'Recent Activity',
      'dashboard.quick_actions': 'Quick Actions',
      'dashboard.stats.total_resources': 'Total Resources',
      'dashboard.stats.pending_requests': 'Pending Requests',
      'dashboard.stats.active_users': 'Active Users',
      'dashboard.stats.published_content': 'Published Content',

      // Landing Page
      'landing.hero.title': 'Authentic Islamic Content Management System',
      'landing.hero.description': 'Aggregate, license, and distribute verified Quranic content through controlled APIs with proper Islamic licensing workflows and scholarly review.',
      'landing.hero.start_free': 'Start Free',
      'landing.hero.watch_demo': 'Watch Demo',
      'landing.hero.browse_content': 'Browse Content',

      // Documentation Section
      'landing.docs.title': 'API Documentation: Data Access Standards',
      'landing.docs.subtitle': 'This document outlines the data access standards for files. Please follow the guidance provided for each category.',

              // Content Standards Page
        'content_standards.title': 'Documents: Data Access Standards',
        'content_standards.subtitle': 'This document describes the standards for accessing data in files. Please follow the guidelines below for each category.',
        'content_standards.verse.title': 'Verse Usage Standards',
        'content_standards.verse.description': 'To access verses, follow the standards below:',
        'content_standards.verse.guideline_1': 'Use correct verse identifier format',
        'content_standards.verse.guideline_2': 'Ensure proper verse indexing',
        'content_standards.verse.guideline_3': 'Check for latest updates in verse database',
        'content_standards.verse.example_title': 'Example: To access verse 2:255, use',
        'content_standards.word.title': 'Word Usage Standards',
        'content_standards.word.description': 'To access words, adhere to the following:',
        'content_standards.word.guideline_1': 'Use specified word keys',
        'content_standards.word.guideline_2': 'Ensure word list is updated',
        'content_standards.word.guideline_3': 'Maintain consistency in word formatting',
        'content_standards.word.example_title': 'Example: To retrieve word "الله", use',
        'content_standards.tafsir.title': 'Tafsir Usage Standards',
        'content_standards.tafsir.description': 'When accessing tafsir, follow the guidelines below:',
        'content_standards.tafsir.guideline_1': 'Use correct tafsir reference',
        'content_standards.tafsir.guideline_2': 'Ensure accuracy of translations',
        'content_standards.tafsir.guideline_3': 'Check for updated interpretations',
        'content_standards.tafsir.example_title': 'Example: To access tafsir for verse 2:255, use',
        'content_standards.copyright': '© Documentation Standards 2023. All rights reserved.',

        // Asset Store Page
        'asset_store.search_placeholder': 'Search for Islamic resources...',
        'asset_store.loading': 'Loading resources...',
        'asset_store.license': 'License',
        'asset_store.download': 'Download',
        'asset_store.pagination_total': 'Showing {start}-{end} of {total} resources',
        'asset_store.no_resources': 'No resources found matching your criteria',
        'asset_store.filters': 'Filters',
        'asset_store.categories': 'Categories',
        'asset_store.creative_commons': 'Creative Commons License',
        'asset_store.language': 'Language',
        'asset_store.all_languages': 'All Languages',

      // API Usage Standards
      'landing.docs.api_usage.title': 'API Usage Standards',
      'landing.docs.api_usage.correct_format': 'Use the correct API format for data access.',
      'landing.docs.api_usage.proper_indexing': 'Ensure proper indexing of the API in a correct format.',
      'landing.docs.api_usage.verify_database': 'Verify the most beneficial database entries.',
      'landing.docs.api_usage.example_desc': 'Example: Access verse 2:255, use getVerse(\'2:255\')',

      // Word Usage Standards
      'landing.docs.word_usage.title': 'Word Usage Standards',
      'landing.docs.word_usage.defined_keys': 'Use the specified key definitions for words.',
      'landing.docs.word_usage.update_list': 'Ensure updating the list of defined words.',
      'landing.docs.word_usage.maintain_format': 'Maintain consistency in word formatting.',
      'landing.docs.word_usage.example_desc': 'Example: To retrieve the word "Allah", use getWord("الله")',

      // Tafsir Usage Standards
      'landing.docs.tafsir_usage.title': 'Tafsir Usage Standards',
      'landing.docs.tafsir_usage.correct_reference': 'Use the correct reference for tafsir access.',
      'landing.docs.tafsir_usage.verify_accuracy': 'Ensure verification of translation accuracy.',
      'landing.docs.tafsir_usage.modern_interpretations': 'Verify the existence of verified modern interpretations.',
      'landing.docs.tafsir_usage.example_desc': 'Example: To access tafsir for verse 2:255, use getTafsir(\'2:255\')',

      // Statistics
      'landing.stats.resources': 'Islamic Resources',
      'landing.stats.developers': 'Active Developers',
      'landing.stats.api_calls': 'Monthly API Calls',
      'landing.stats.countries': 'Countries Served',

      // Features
      'landing.features.title': 'Why Choose Itqan CMS?',
      'landing.features.subtitle': 'Built specifically for Islamic content with scholarly review and authentic verification.',
      'landing.features.authentic.title': 'Authentic Content',
      'landing.features.authentic.description': 'All Quranic content is verified by Islamic scholars with SHA-256 integrity checksums.',
      'landing.features.multilingual.title': 'Multilingual Support',
      'landing.features.multilingual.description': 'Native Arabic with RTL support plus comprehensive translation management.',
      'landing.features.api.title': 'Robust API',
      'landing.features.api.description': 'RESTful APIs with proper authentication, rate limiting, and Islamic licensing compliance.',

      // Footer
      'footer.about.title': 'About Itqan',
      'footer.about.description': 'Specialized headless CMS for Islamic content management with scholarly review and global distribution.',
      'footer.resources.title': 'Resources',
      'footer.resources.documentation': 'Documentation',
      'footer.resources.api_reference': 'API Reference',
      'footer.resources.guides': 'Developer Guides',
      'footer.resources.support': 'Support',
      'footer.legal.title': 'Legal',
      'footer.legal.privacy': 'Privacy Policy',
      'footer.legal.terms': 'Terms of Service',
      'footer.legal.licenses': 'Content Licenses',
      'footer.copyright': '© 2023 Itqan Development. All rights reserved.',

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
      'common.or': 'أو',
      'common.and': 'و',

      // App
      'app.name': 'نظام إتقان',

      // Navigation
      'nav.home': 'الرئيسية',
      'nav.about': 'عن المشروع',
      'nav.publishers': 'الناشرين',
      'nav.content_standards': 'معايير المحتوى والتقنية',
      'nav.documentation': 'معايير البحوث والتقنية',
      'nav.api_standards': 'معايير استخدام آية',
      'nav.language': 'اللغة',
      'nav.switch_language': 'تبديل اللغة',

      // Authentication
      'auth.welcome': 'مرحباً بك في نظام إتقان',
      'auth.get_started': 'تسجيل الدخول',
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
      'auth.continue_github': 'المتابعة مع GitHub',
      'auth.continue_google': 'المتابعة مع Google',
      'auth.continue_email': 'المتابعة بالبريد الإلكتروني',
      'auth.forgot_password_link': 'نسيت كلمة المرور؟',
      'auth.terms_agreement': 'بتسجيل الدخول، فإنك توافق على',
      'auth.terms_service': 'شروط الخدمة',
      'auth.privacy_policy': 'سياسة الخصوصية',
      'auth.register_free': 'إنشاء حساب مجاني',

      // Dashboard
      'dashboard.welcome': 'مرحباً بك في نظام إتقان',
      'dashboard.overview': 'نظرة عامة',
      'dashboard.recent_activity': 'النشاط الأخير',
      'dashboard.quick_actions': 'إجراءات سريعة',
      'dashboard.stats.total_resources': 'إجمالي الموارد',
      'dashboard.stats.pending_requests': 'الطلبات المعلقة',
      'dashboard.stats.active_users': 'المستخدمون النشطون',
      'dashboard.stats.published_content': 'المحتوى المنشور',

      // Landing Page
      'landing.hero.title': 'نظام إدارة المحتوى الإسلامي الموثق',
      'landing.hero.description': 'يجمع ويرخص ويوزع المحتوى القرآني الموثق من خلال واجهات برمجة التطبيقات المتحكم فيها مع سير عمل الترخيص الإسلامي والمراجعة العلمية.',
      'landing.hero.start_free': 'ابدأ مجاناً',
      'landing.hero.watch_demo': 'شاهد العرض التوضيحي',
      'landing.hero.browse_content': 'تصفح المحتوى',

      // Documentation Section
      'landing.docs.title': 'الوثائق: معايير الوصول إلى البيانات',
      'landing.docs.subtitle': 'يوضح هذا المستند معايير الوصول إلى البيانات في الملفات. يرجى اتباع الإرشادات أدناه لكل فئة.',

              // Content Standards Page
        'content_standards.title': 'الوثائق: معايير الوصول إلى البيانات',
        'content_standards.subtitle': 'هذه الوثيقة تصف معايير الوصول إلى البيانات في الملفات. يرجى اتباع الإرشادات أدناه لكل فئة.',
        'content_standards.verse.title': 'معايير استخدام الآية',
        'content_standards.verse.description': 'للوصول إلى الآيات، اتبع المعايير التالية:',
        'content_standards.verse.guideline_1': 'استخدم تنسيق معرف الآية الصحيح',
        'content_standards.verse.guideline_2': 'تأكد من فهرسة الآية بشكل صحيح',
        'content_standards.verse.guideline_3': 'تحقق من آخر التحديثات في قاعدة بيانات الآيات',
        'content_standards.verse.example_title': 'مثال: للوصول إلى الآية 2:255، استخدم',
        'content_standards.word.title': 'معايير استخدام الكلمات',
        'content_standards.word.description': 'للوصول إلى الكلمات، التزم بما يلي:',
        'content_standards.word.guideline_1': 'استخدم مفاتيح الكلمات المحددة',
        'content_standards.word.guideline_2': 'تأكد من تحديث قائمة الكلمات',
        'content_standards.word.guideline_3': 'احفظ على الاتساق في تنسيق الكلمات',
        'content_standards.word.example_title': 'مثال: لاسترجاع كلمة "الله"، استخدم',
        'content_standards.tafsir.title': 'معايير استخدام تفسير',
        'content_standards.tafsir.description': 'عند الوصول إلى تفسير، اتبع الإرشادات التالية:',
        'content_standards.tafsir.guideline_1': 'استخدم مرجع التفسير الصحيح',
        'content_standards.tafsir.guideline_2': 'تأكد من دقة الترجمات',
        'content_standards.tafsir.guideline_3': 'تحقق من وجود تفسيرات محدثة لتفسير',
        'content_standards.tafsir.example_title': 'مثال: للوصول إلى تفسير للآية 2:255، استخدم',
        'content_standards.copyright': '© معايير التوثيق لعام 2023. كل الحقوق محفوظة.',

        // Asset Store Page
        'asset_store.search_placeholder': 'البحث عن الموارد الإسلامية...',
        'asset_store.loading': 'جاري تحميل الموارد...',
        'asset_store.license': 'الرخصة',
        'asset_store.download': 'تحميل',
        'asset_store.pagination_total': 'عرض {start}-{end} من {total} مورد',
        'asset_store.no_resources': 'لم يتم العثور على موارد تطابق معاييرك',
        'asset_store.filters': 'المرشحات',
        'asset_store.categories': 'الفئات',
        'asset_store.creative_commons': 'رخصة المشاع الإبداعي',
        'asset_store.language': 'اللغة',
        'asset_store.all_languages': 'جميع اللغات',

      // API Usage Standards
      'landing.docs.api_usage.title': 'معايير استخدام آية',
      'landing.docs.api_usage.correct_format': 'استخدم تنسيق معرف الآية الصحيح.',
      'landing.docs.api_usage.proper_indexing': 'تأكد من فهرسة الآية بشكل صحيح.',
      'landing.docs.api_usage.verify_database': 'تحقق من أكبر التحديثات في قاعدة بيانات الآيات.',
      'landing.docs.api_usage.example_desc': 'مثال: للوصول إلى الآية 2:255، استخدم getVerse(\'2:255\')',

      // Word Usage Standards
      'landing.docs.word_usage.title': 'معايير استخدام الكلمات',
      'landing.docs.word_usage.defined_keys': 'استخدم مفاتيح الكلمات المحددة.',
      'landing.docs.word_usage.update_list': 'تأكد من تحديث قائمة الكلمات.',
      'landing.docs.word_usage.maintain_format': 'الحفاظ على الاتساق في تنسيق الكلمات.',
      'landing.docs.word_usage.example_desc': 'مثال: لاسترجاع كلمة "الله"، استخدم getWord("الله")',

      // Tafsir Usage Standards
      'landing.docs.tafsir_usage.title': 'معايير استخدام تفسير',
      'landing.docs.tafsir_usage.correct_reference': 'استخدم مرجع تفسير الصحيح.',
      'landing.docs.tafsir_usage.verify_accuracy': 'تأكد من دقة الترجمات.',
      'landing.docs.tafsir_usage.modern_interpretations': 'تحقق من وجود تفسيرات محدثة لتفسير.',
      'landing.docs.tafsir_usage.example_desc': 'مثال: للوصول إلى تفسير للآية 2:255، استخدم getTafsir(\'2:255\')',

      // Statistics
      'landing.stats.resources': 'الموارد الإسلامية',
      'landing.stats.developers': 'المطورين النشطين',
      'landing.stats.api_calls': 'استدعاءات API الشهرية',
      'landing.stats.countries': 'البلدان المخدومة',

      // Features
      'landing.features.title': 'لماذا تختار نظام إتقان؟',
      'landing.features.subtitle': 'مصمم خصيصاً للمحتوى الإسلامي مع المراجعة العلمية والتحقق الموثق.',
      'landing.features.authentic.title': 'محتوى موثق',
      'landing.features.authentic.description': 'جميع المحتوى القرآني تم التحقق منه من قبل علماء المسلمين مع مجاميع التحقق SHA-256.',
      'landing.features.multilingual.title': 'دعم متعدد اللغات',
      'landing.features.multilingual.description': 'العربية الأصلية مع دعم RTL بالإضافة إلى إدارة الترجمة الشاملة.',
      'landing.features.api.title': 'واجهة برمجة تطبيقات قوية',
      'landing.features.api.description': 'واجهات برمجة تطبيقات RESTful مع التوثيق المناسب وتحديد المعدل والامتثال للترخيص الإسلامي.',

      // Footer
      'footer.about.title': 'عن إتقان',
      'footer.about.description': 'نظام إدارة محتوى متخصص للمحتوى الإسلامي مع المراجعة العلمية والتوزيع العالمي.',
      'footer.resources.title': 'الموارد',
      'footer.resources.documentation': 'الوثائق',
      'footer.resources.api_reference': 'مرجع API',
      'footer.resources.guides': 'أدلة المطورين',
      'footer.resources.support': 'الدعم',
      'footer.legal.title': 'القانونية',
      'footer.legal.privacy': 'سياسة الخصوصية',
      'footer.legal.terms': 'شروط الخدمة',
      'footer.legal.licenses': 'تراخيص المحتوى',
      'footer.copyright': '© 2023 معايير التقنية الدولية. كل الحقوق محفوظة.',

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
   * Initialize the i18n service (public method)
   */
  initialize(): void {
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
