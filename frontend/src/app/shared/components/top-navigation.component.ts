import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router, RouterModule } from '@angular/router';
import { NzMenuModule } from 'ng-zorro-antd/menu';
import { NzLayoutModule } from 'ng-zorro-antd/layout';
import { NzButtonModule } from 'ng-zorro-antd/button';
import { NzIconModule } from 'ng-zorro-antd/icon';
import { NzDropDownModule } from 'ng-zorro-antd/dropdown';
import { NzAvatarModule } from 'ng-zorro-antd/avatar';
import { I18nService } from '../../core/services/i18n.service';
import { StateService } from '../../core/services/state.service';
import { AuthService } from '../../core/services/auth.service';

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
    NzDropDownModule,
    NzAvatarModule
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
            <span class="language-label">{{ isArabic ? 'EN' : 'ع' }}</span>
          </button>

          <!-- Authenticated User Section -->
          <div *ngIf="isAuthenticated()" class="user-section">
            <!-- User Info -->
            <div class="user-info">
              <nz-avatar 
                [nzText]="getUserInitials()" 
                [nzSize]="32" 
                class="user-avatar"
                nzSrc="">
              </nz-avatar>
              <span class="user-name">{{ getUserDisplayName() }}</span>
            </div>
            
            <!-- Logout Button -->
            <button nz-button nzType="default" (click)="logout()" class="logout-btn">
              <span nz-icon nzType="logout" nzTheme="outline"></span>
              <span>{{ t('nav.logout') }}</span>
            </button>
          </div>

          <!-- Login Button (when not authenticated) -->
          <div *ngIf="!isAuthenticated()" class="login-section">
            <button nz-button nzType="primary" (click)="loginWithAuth0()" class="login-btn">
              <span nz-icon nzType="login" nzTheme="outline"></span>
              <span>{{ t('nav.login') }}</span>
            </button>
          </div>
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

    .user-section {
      display: flex;
      align-items: center;
      gap: 16px;
    }

    .user-info {
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .user-avatar {
      background: #669B80;
      color: white;
      font-weight: 600;
    }

    .user-name {
      font-weight: 500;
      color: #262626;
      font-size: 14px;
    }

    .logout-btn {
      border-color: #d9d9d9;
      height: 32px;
      padding: 0 12px;
      border-radius: 6px;
      display: flex;
      align-items: center;
      gap: 4px;
      color: #666;
    }

    .logout-btn:hover {
      border-color: #669B80;
      color: #669B80;
    }

    .login-section {
      display: flex;
      align-items: center;
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

    /* RTL User Section */
    :host-context([dir="rtl"]) .user-section {
      flex-direction: row-reverse;
    }

    :host-context([dir="rtl"]) .user-info {
      flex-direction: row-reverse;
    }

    :host-context([dir="rtl"]) .user-name {
      margin-left: 0;
      margin-right: 8px;
    }

    :host-context([dir="rtl"]) .logout-btn {
      margin-left: 0;
      margin-right: 16px;
    }

    :host-context([dir="rtl"]) .login-btn {
      flex-direction: row-reverse;
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
    private i18nService: I18nService,
    private stateService: StateService,
    private authService: AuthService
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

  switchLanguage(lang: 'en' | 'ar') {
    this.i18nService.setLanguage(lang);
    this.updateLanguageState();
  }

  toggleLanguage() {
    const newLang = this.isArabic ? 'en' : 'ar';
    this.switchLanguage(newLang);
  }

  /**
   * Check if user is authenticated
   */
  isAuthenticated(): boolean {
    return this.stateService.isAuthenticated();
  }

  /**
   * Get user display name
   */
  getUserDisplayName(): string {
    return this.stateService.userDisplayName();
  }

  /**
   * Get user initials for avatar
   */
  getUserInitials(): string {
    const user = this.stateService.currentUser();
    if (!user) return 'U';
    
    const firstName = user.first_name || '';
    const lastName = user.last_name || '';
    
    if (firstName && lastName) {
      return `${firstName.charAt(0)}${lastName.charAt(0)}`.toUpperCase();
    } else if (firstName) {
      return firstName.charAt(0).toUpperCase();
    } else if (user.email) {
      return user.email.charAt(0).toUpperCase();
    }
    
    return 'U';
  }

  /**
   * Handle user logout
   */
  async logout(): Promise<void> {
    try {
      await this.authService.logout();
    } catch (error) {
      console.error('Logout error:', error);
      // Force navigation to login even if logout fails
      await this.router.navigate(['/auth/login']);
    }
  }

  /**
   * Initiate Auth0 login flow
   */
  async loginWithAuth0(): Promise<void> {
    try {
      await this.authService.login();
    } catch (error) {
      console.error('Auth0 login error:', error);
      // Fallback to login page on error
      this.router.navigate(['/auth/login']);
    }
  }

  /**
   * Navigate to login page (fallback for direct navigation)
   */
  navigateToLogin(): void {
    this.router.navigate(['/auth/login']);
  }
}
