import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { NzCardModule } from 'ng-zorro-antd/card';
import { NzDividerModule } from 'ng-zorro-antd/divider';
import { NzTypographyModule } from 'ng-zorro-antd/typography';
import { NzSpaceModule } from 'ng-zorro-antd/space';
import { NzTagModule } from 'ng-zorro-antd/tag';
import { NzIconModule } from 'ng-zorro-antd/icon';
import { NzCodeEditorModule } from 'ng-zorro-antd/code-editor';
import { I18nService } from '../../core/services/i18n.service';

@Component({
  selector: 'app-content-standards',
  standalone: true,
  imports: [
    CommonModule,
    NzCardModule,
    NzDividerModule,
    NzTypographyModule,
    NzSpaceModule,
    NzTagModule,
    NzIconModule,
    NzCodeEditorModule
  ],
  template: `
    <div class="content-standards-page" [dir]="isArabic ? 'rtl' : 'ltr'">
      <!-- Page Header -->
      <div class="page-header">
        <h1 class="main-title" [class.rtl]="isArabic">
          {{ t('content_standards.title') }}
        </h1>
        <p class="subtitle">
          {{ t('content_standards.subtitle') }}
        </p>
      </div>

      <!-- Content Sections -->
      <div class="content-sections">
        <!-- Verse Usage Standards -->
        <nz-card 
          class="standards-card"
          [nzTitle]="t('content_standards.verse.title')"
          [nzBordered]="true">
          
          <div class="section-content">
            <p class="section-description" [class.rtl]="isArabic">
              {{ t('content_standards.verse.description') }}
            </p>
            
            <ul class="guidelines-list" [class.rtl]="isArabic">
              <li>{{ t('content_standards.verse.guideline_1') }}</li>
              <li>{{ t('content_standards.verse.guideline_2') }}</li>
              <li>{{ t('content_standards.verse.guideline_3') }}</li>
            </ul>
            
            <div class="code-example">
              <h4>{{ t('content_standards.verse.example_title') }}</h4>
              <div class="code-block">
                <code>getVerse('2:255')</code>
              </div>
            </div>
          </div>
        </nz-card>

        <!-- Word Usage Standards -->
        <nz-card 
          class="standards-card"
          [nzTitle]="t('content_standards.word.title')"
          [nzBordered]="true">
          
          <div class="section-content">
            <p class="section-description" [class.rtl]="isArabic">
              {{ t('content_standards.word.description') }}
            </p>
            
            <ul class="guidelines-list" [class.rtl]="isArabic">
              <li>{{ t('content_standards.word.guideline_1') }}</li>
              <li>{{ t('content_standards.word.guideline_2') }}</li>
              <li>{{ t('content_standards.word.guideline_3') }}</li>
            </ul>
            
            <div class="code-example">
              <h4>{{ t('content_standards.word.example_title') }}</h4>
              <div class="code-block">
                <code>getWord("الله")</code>
              </div>
            </div>
          </div>
        </nz-card>

        <!-- Tafsir Usage Standards -->
        <nz-card 
          class="standards-card"
          [nzTitle]="t('content_standards.tafsir.title')"
          [nzBordered]="true">
          
          <div class="section-content">
            <p class="section-description" [class.rtl]="isArabic">
              {{ t('content_standards.tafsir.description') }}
            </p>
            
            <ul class="guidelines-list" [class.rtl]="isArabic">
              <li>{{ t('content_standards.tafsir.guideline_1') }}</li>
              <li>{{ t('content_standards.tafsir.guideline_2') }}</li>
              <li>{{ t('content_standards.tafsir.guideline_3') }}</li>
            </ul>
            
            <div class="code-example">
              <h4>{{ t('content_standards.tafsir.example_title') }}</h4>
              <div class="code-block">
                <code>getTafsir('2:255')</code>
              </div>
            </div>
          </div>
        </nz-card>
      </div>

      <!-- Footer -->
      <div class="page-footer">
        <nz-divider></nz-divider>
        <p class="copyright" [class.rtl]="isArabic">
          {{ t('content_standards.copyright') }}
        </p>
      </div>
    </div>
  `,
  styles: [`
    .content-standards-page {
      min-height: calc(100vh - 64px);
      background: #fafafa;
      padding: 80px 24px 40px; /* Top padding accounts for fixed header */
    }

    .page-header {
      max-width: 1200px;
      margin: 0 auto 40px;
      text-align: center;
      background: white;
      padding: 40px;
      border-radius: 8px;
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
    }

    .main-title {
      font-size: 32px;
      font-weight: 600;
      color: #262626;
      margin-bottom: 16px;
      line-height: 1.4;
    }

    .main-title.rtl {
      font-family: 'Noto Sans Arabic', sans-serif;
      font-size: 28px;
      direction: rtl;
    }

    .subtitle {
      font-size: 16px;
      color: #595959;
      line-height: 1.6;
      max-width: 800px;
      margin: 0 auto;
    }

    .content-sections {
      max-width: 1200px;
      margin: 0 auto;
      display: flex;
      flex-direction: column;
      gap: 32px;
    }

    .standards-card {
      border-radius: 8px;
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
      transition: box-shadow 0.3s ease;
    }

    .standards-card:hover {
      box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1);
    }

    .standards-card ::ng-deep .ant-card-head-title {
      font-size: 20px;
      font-weight: 600;
      color: #669B80;
    }

    .section-content {
      padding: 8px 0;
    }

    .section-description {
      font-size: 16px;
      color: #595959;
      margin-bottom: 20px;
      line-height: 1.6;
    }

    .section-description.rtl {
      direction: rtl;
      text-align: right;
      font-family: 'Noto Sans Arabic', sans-serif;
    }

    .guidelines-list {
      margin: 20px 0;
      padding-left: 20px;
      list-style-type: disc;
    }

    .guidelines-list.rtl {
      padding-left: 0;
      padding-right: 20px;
      direction: rtl;
      text-align: right;
      font-family: 'Noto Sans Arabic', sans-serif;
    }

    .guidelines-list li {
      margin-bottom: 8px;
      color: #595959;
      line-height: 1.5;
    }

    .code-example {
      background: #f5f5f5;
      border-radius: 6px;
      padding: 20px;
      margin-top: 20px;
      border-left: 4px solid #669B80;
    }

    .code-example.rtl {
      border-left: none;
      border-right: 4px solid #669B80;
      direction: rtl;
      text-align: right;
    }

    .code-example h4 {
      font-size: 14px;
      color: #262626;
      margin-bottom: 12px;
      font-weight: 500;
    }

    .code-block {
      background: #262626;
      color: #f5f5f5;
      padding: 12px 16px;
      border-radius: 4px;
      font-family: 'Monaco', 'Consolas', 'Courier New', monospace;
      font-size: 14px;
      overflow-x: auto;
    }

    .code-block code {
      color: #52c41a;
      background: transparent;
      padding: 0;
      font-size: 14px;
    }

    .page-footer {
      max-width: 1200px;
      margin: 40px auto 0;
      text-align: center;
    }

    .copyright {
      color: #8c8c8c;
      font-size: 14px;
      margin: 20px 0 0;
    }

    .copyright.rtl {
      font-family: 'Noto Sans Arabic', sans-serif;
      direction: rtl;
    }

    /* Responsive Design */
    @media (max-width: 768px) {
      .content-standards-page {
        padding: 80px 16px 20px;
      }

      .page-header {
        padding: 24px;
        margin-bottom: 24px;
      }

      .main-title {
        font-size: 24px;
      }

      .main-title.rtl {
        font-size: 22px;
      }

      .content-sections {
        gap: 20px;
      }

      .standards-card ::ng-deep .ant-card-head-title {
        font-size: 18px;
      }

      .code-example {
        padding: 16px;
      }
    }

    /* Islamic Pattern Background */
    .content-standards-page::before {
      content: '';
      position: fixed;
      top: 0;
      left: 0;
      right: 0;
      bottom: 0;
      background: linear-gradient(45deg, rgba(102, 155, 128, 0.02) 25%, transparent 25%), 
                  linear-gradient(-45deg, rgba(102, 155, 128, 0.02) 25%, transparent 25%),
                  linear-gradient(45deg, transparent 75%, rgba(102, 155, 128, 0.02) 75%), 
                  linear-gradient(-45deg, transparent 75%, rgba(102, 155, 128, 0.02) 75%);
      background-size: 40px 40px;
      background-position: 0 0, 0 20px, 20px -20px, -20px 0px;
      opacity: 0.3;
      z-index: -1;
    }
  `]
})
export class ContentStandardsComponent implements OnInit {
  isArabic = false;

  constructor(private i18nService: I18nService) {}

  ngOnInit() {
    // Initialize language state
    this.updateLanguageState();
  }

  private updateLanguageState(): void {
    this.isArabic = this.i18nService.currentLanguage() === 'ar';
    
    // Update document direction
    document.documentElement.setAttribute('dir', this.isArabic ? 'rtl' : 'ltr');
    document.documentElement.setAttribute('lang', this.isArabic ? 'ar' : 'en');
  }

  /**
   * Translation helper method
   */
  t(key: string): string {
    return this.i18nService.translate(key);
  }
}
