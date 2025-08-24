import { Component, inject } from '@angular/core';
import { RouterLink } from '@angular/router';
import { TranslationService } from '../../shared/translation.service';

@Component({
  standalone: true,
  selector: 'app-content-standards',
  imports: [RouterLink],
  template: `
    <div class="wireframe-page" dir="rtl">
      <!-- Top Navigation Bar (as per wireframe) -->
      <nav class="top-nav">
        <div class="nav-container">
          <div class="nav-tabs">
            <a routerLink="/home-unauth" class="nav-tab">الرئيسية</a>
            <a routerLink="/publishers/itqan" class="nav-tab">الناشرين</a>
            <a routerLink="/content-standards" class="nav-tab active">معايير المحتوى والتقنية</a>
            <a href="#" class="nav-tab">عن المشروع</a>
            <a routerLink="/auth/login" class="nav-tab login-tab">تسجيل الدخول</a>
          </div>
        </div>
      </nav>

      <!-- Main Content -->
      <div class="main-content">
        <div class="content-container">
          <!-- Page Title -->
          <h1 class="page-title">الوثائق: معايير الوصول إلى البيانات</h1>
          <p class="page-subtitle">
            يوضح هذا المستند معايير الوصول إلى البيانات في الملفات. يرجى اتباع الإرشادات أدناه لكل وثيقة.
          </p>

          <!-- Section 1: معايير استخدام الآية -->
          <section class="doc-section">
            <h2 class="section-title">معايير استخدام الآية</h2>
            <p class="section-description">للوصول إلى الآيات، اتبع المعايير التالية:</p>
            
            <div class="criteria-list">
              <div class="criteria-item">استخدم تنسيق معرف الآية الصحيح.</div>
              <div class="criteria-item">تأكد من فهرسة الآية بشكل صحيح.</div>
              <div class="criteria-item">تحقق من آخر التحديثات في قاعدة بيانات الآيات.</div>
            </div>

            <div class="code-example">
              <span class="example-label">مثال: للوصول إلى الآية 2: 255، استخدم</span>
              <code class="code-snippet">getVerse('2:255')</code>
            </div>
          </section>

          <!-- Section 2: معايير استخدام الكلمات -->
          <section class="doc-section">
            <h2 class="section-title">معايير استخدام الكلمات</h2>
            <p class="section-description">للوصول إلى الكلمات، التزم بما يلي:</p>
            
            <div class="criteria-list">
              <div class="criteria-item">استخدم مفاتيح الكلمات المحددة.</div>
              <div class="criteria-item">تأكد من تحديث قائمة الكلمات.</div>
              <div class="criteria-item">الحفاظ على الاتساق في تنسيق الكلمات.</div>
            </div>

            <div class="code-example">
              <span class="example-label">مثال: لاسترجاع كلمة "الله"، استخدم</span>
              <code class="code-snippet">getWord("الله")</code>
            </div>
          </section>

          <!-- Section 3: معايير استخدام تفسير -->
          <section class="doc-section">
            <h2 class="section-title">معايير استخدام تفسير</h2>
            <p class="section-description">عند الوصول إلى تفسير، اتبع الإرشادات التالية:</p>
            
            <div class="criteria-list">
              <div class="criteria-item">استخدم مرجع التفسير الصحيح.</div>
              <div class="criteria-item">تأكد من دقة الترجمات.</div>
              <div class="criteria-item">تحقق من وجود تفسيرات محدثة لتفسير.</div>
            </div>

            <div class="code-example">
              <span class="example-label">مثال: للوصول إلى تفسير للآية 2: 255، استخدم</span>
              <code class="code-snippet">getTafsir ('2:255')</code>
            </div>
          </section>

          <!-- Footer -->
          <footer class="page-footer">
            <p>© معايير التوثيق لعام 2023. كل الحقوق محفوظة.</p>
          </footer>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .wireframe-page {
      min-height: 100vh;
      background: #ffffff;
      font-family: 'Segoe UI', Tahoma, Arial, Helvetica, sans-serif;
      direction: rtl;
    }

    /* Top Navigation */
    .top-nav {
      background: #ffffff;
      border-bottom: 2px solid #000000;
      padding: 0;
    }

    .nav-container {
      max-width: 1200px;
      margin: 0 auto;
      padding: 0 20px;
    }

    .nav-tabs {
      display: flex;
      justify-content: space-between;
      align-items: center;
      height: 60px;
    }

    .nav-tab {
      text-decoration: none;
      color: #000000;
      font-size: 16px;
      font-weight: 500;
      padding: 15px 20px;
      border-radius: 25px;
      transition: all 0.2s;
      white-space: nowrap;
    }

    .nav-tab:hover {
      background: #f0f0f0;
    }

    .nav-tab.active {
      background: #000000;
      color: #ffffff;
    }

    .login-tab {
      border: 2px solid #000000;
      border-radius: 25px;
      padding: 12px 25px;
    }

    .login-tab:hover {
      background: #000000;
      color: #ffffff;
    }

    /* Main Content */
    .main-content {
      padding: 40px 20px;
    }

    .content-container {
      max-width: 1000px;
      margin: 0 auto;
      text-align: right;
    }

    .page-title {
      font-size: 32px;
      font-weight: 700;
      color: #000000;
      margin-bottom: 20px;
      text-align: center;
    }

    .page-subtitle {
      font-size: 18px;
      color: #666666;
      margin-bottom: 50px;
      text-align: center;
      line-height: 1.6;
    }

    /* Document Sections */
    .doc-section {
      margin-bottom: 50px;
      text-align: right;
    }

    .section-title {
      font-size: 24px;
      font-weight: 600;
      color: #000000;
      margin-bottom: 15px;
      text-align: right;
    }

    .section-description {
      font-size: 16px;
      color: #333333;
      margin-bottom: 25px;
      line-height: 1.6;
    }

    .criteria-list {
      margin-bottom: 30px;
    }

    .criteria-item {
      font-size: 16px;
      color: #333333;
      margin-bottom: 10px;
      padding-right: 20px;
      position: relative;
      line-height: 1.5;
    }

    .criteria-item::before {
      content: "•";
      position: absolute;
      right: 0;
      color: #000000;
      font-weight: bold;
    }

    /* Code Examples */
    .code-example {
      background: #f8f9fa;
      border: 1px solid #e9ecef;
      border-radius: 8px;
      padding: 20px;
      margin: 20px 0;
      text-align: right;
    }

    .example-label {
      display: block;
      font-size: 16px;
      color: #333333;
      margin-bottom: 10px;
    }

    .code-snippet {
      background: #ffffff;
      border: 1px solid #dee2e6;
      border-radius: 4px;
      padding: 8px 12px;
      font-family: 'Courier New', monospace;
      font-size: 14px;
      color: #d63384;
      display: inline-block;
      margin-right: 10px;
    }

    /* Footer */
    .page-footer {
      margin-top: 80px;
      padding-top: 30px;
      border-top: 1px solid #e9ecef;
      text-align: center;
    }

    .page-footer p {
      font-size: 14px;
      color: #666666;
      margin: 0;
    }

    /* Responsive Design */
    @media (max-width: 768px) {
      .nav-tabs {
        flex-direction: column;
        height: auto;
        padding: 10px 0;
      }

      .nav-tab {
        margin: 5px 0;
        width: 100%;
        text-align: center;
      }

      .page-title {
        font-size: 24px;
      }

      .section-title {
        font-size: 20px;
      }

      .content-container {
        padding: 0 10px;
      }
    }

    /* RTL Specific Adjustments */
    [dir="rtl"] .criteria-item {
      padding-right: 20px;
      padding-left: 0;
    }

    [dir="rtl"] .criteria-item::before {
      right: 0;
      left: auto;
    }

    [dir="rtl"] .code-snippet {
      margin-right: 0;
      margin-left: 10px;
    }
  `]
})
export class ContentStandardsPage {
  private translationService = inject(TranslationService);
  t = this.translationService.t;
}


