import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router, RouterModule } from '@angular/router';
import { NzMenuModule } from 'ng-zorro-antd/menu';
import { NzLayoutModule } from 'ng-zorro-antd/layout';
import { NzButtonModule } from 'ng-zorro-antd/button';
import { NzIconModule } from 'ng-zorro-antd/icon';
import { NzDropDownModule } from 'ng-zorro-antd/dropdown';
import { I18nService } from '../../core/services/i18n.service';

@Component({
  selector: 'app-top-navigation',
  standalone: true,
  imports: [
    CommonModule,
    RouterModule,
    NzMenuModule,
    NzLayoutModule,
    NzButtonModule,
    NzIconModule,
    NzDropDownModule
  ],
  template: `
    <nz-header class="header">
      <div class="nav-container">
        <!-- Logo -->
        <div class="logo" (click)="navigateHome()">
          <img src="assets/images/itqan-logo.png" alt="Itqan CMS" class="logo-image">
          <span class="logo-text">إتقان</span>
        </div>

        <!-- Navigation Menu -->
        <ul nz-menu nzMode="horizontal" nzTheme="light" class="nav-menu">
          <li nz-menu-item routerLink="/" routerLinkActive="active" [routerLinkActiveOptions]="{exact: true}">
            <span>{{ t('nav.home') }}</span>
          </li>
          
          <li nz-menu-item routerLink="/publishers" routerLinkActive="active">
            <span>{{ t('nav.publishers') }}</span>
          </li>
          
          <li nz-menu-item routerLink="/content-standards" routerLinkActive="active">
            <span>{{ t('nav.content_standards') }}</span>
          </li>
          
          <li nz-menu-item routerLink="/about" routerLinkActive="active">
            <span>{{ t('nav.about') }}</span>
          </li>
        </ul>

        <!-- Right Side Actions -->
        <div class="nav-actions">
          <!-- Language Switcher -->
          <button nz-button nzType="text" (click)="toggleLanguage()" class="language-btn">
            <span nz-icon nzType="global" nzTheme="outline"></span>
            <span class="language-label">{{ isArabic ? 'ع' : 'EN' }}</span>
          </button>

          <!-- Login Button -->
          <button nz-button nzType="primary" (click)="navigateToLogin()" class="login-btn">
            <span nz-icon nzType="login" nzTheme="outline"></span>
            <span>{{ t('nav.login') }}</span>
          </button>
        </div>
      </div>
    </nz-header>
  `,
  styles: [`
    .header {
      background: #fff;
      border-bottom: 1px solid #f0f0f0;
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
      position: fixed;
      top: 0;
      left: 0;
      right: 0;
      z-index: 1000;
      padding: 0;
    }

    .nav-container {
      max-width: 1200px;
      margin: 0 auto;
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0 24px;
      height: 64px;
    }

    .logo {
      display: flex;
      align-items: center;
      cursor: pointer;
      transition: opacity 0.3s ease;
    }

    .logo:hover {
      opacity: 0.8;
    }

    .logo-image {
      height: 32px;
      width: auto;
      margin-right: 8px;
    }

    .logo-text {
      font-size: 24px;
      font-weight: 600;
      color: #669B80;
      font-family: 'Noto Sans Arabic', sans-serif;
    }

    .nav-menu {
      flex: 1;
      justify-content: center;
      border: none;
      background: transparent;
      margin: 0 32px;
    }

    .nav-menu .ant-menu-item {
      border-bottom: 2px solid transparent;
      margin: 0 16px;
      padding: 0 8px;
      height: 62px;
      line-height: 62px;
      transition: all 0.3s ease;
    }

    .nav-menu .ant-menu-item:hover,
    .nav-menu .ant-menu-item.active {
      color: #669B80;
      border-bottom-color: #669B80;
      background: transparent;
    }

    .nav-menu .ant-menu-item span {
      font-weight: 500;
      font-size: 15px;
    }

    .nav-actions {
      display: flex;
      align-items: center;
      gap: 16px;
    }

    .language-btn {
      display: flex;
      align-items: center;
      gap: 4px;
      border: 1px solid #d9d9d9;
      border-radius: 6px;
      padding: 4px 12px;
      height: 32px;
    }

    .language-label {
      font-size: 14px;
      font-weight: 500;
      min-width: 20px;
      text-align: center;
    }

    .check-icon {
      color: #669B80;
      margin-right: 8px;
    }

    .login-btn {
      background: #669B80;
      border-color: #669B80;
      height: 36px;
      padding: 0 20px;
      border-radius: 6px;
      display: flex;
      align-items: center;
      gap: 6px;
    }

    .login-btn:hover,
    .login-btn:focus {
      background: #5a8670;
      border-color: #5a8670;
    }

    /* RTL Support */
    :host-context([dir="rtl"]) .logo-image {
      margin-right: 0;
      margin-left: 8px;
    }

    :host-context([dir="rtl"]) .nav-menu {
      margin: 0 32px;
    }

    :host-context([dir="rtl"]) .nav-actions {
      flex-direction: row-reverse;
    }

    :host-context([dir="rtl"]) .check-icon {
      margin-right: 0;
      margin-left: 8px;
    }

    /* Responsive Design */
    @media (max-width: 768px) {
      .nav-container {
        padding: 0 16px;
      }
      
      .nav-menu {
        display: none;
      }
      
      .logo-text {
        display: none;
      }
    }
  `]
})
export class TopNavigationComponent {
  isArabic = false;

  constructor(
    private router: Router,
    private i18nService: I18nService
  ) {
    // Initialize language state
    this.updateLanguageState();
  }

  private updateLanguageState(): void {
    this.isArabic = this.i18nService.currentLanguage() === 'ar';
  }

  /**
   * Translation helper method
   */
  t(key: string): string {
    return this.i18nService.translate(key);
  }

  navigateHome() {
    this.router.navigate(['/']);
  }

  navigateToLogin() {
    this.router.navigate(['/auth/login']);
  }

  switchLanguage(lang: 'en' | 'ar') {
    this.i18nService.setLanguage(lang);
    this.updateLanguageState();
  }

  toggleLanguage() {
    const newLang = this.isArabic ? 'en' : 'ar';
    this.switchLanguage(newLang);
  }
}
