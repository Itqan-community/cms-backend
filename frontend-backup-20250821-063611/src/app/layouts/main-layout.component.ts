import { Component, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterOutlet, RouterLink } from '@angular/router';
import { NzLayoutModule } from 'ng-zorro-antd/layout';
import { NzMenuModule } from 'ng-zorro-antd/menu';
import { NzButtonModule } from 'ng-zorro-antd/button';
import { NzIconModule } from 'ng-zorro-antd/icon';
import { NzAvatarModule } from 'ng-zorro-antd/avatar';
import { NzSpaceModule } from 'ng-zorro-antd/space';

import { AuthService } from '../core/services/auth.service';

@Component({
  selector: 'app-main-layout',
  standalone: true,
  imports: [
    CommonModule,
    RouterOutlet,
    RouterLink,
    NzLayoutModule,
    NzMenuModule,
    NzButtonModule,
    NzIconModule,
    NzAvatarModule,
    NzSpaceModule
  ],
  template: `
    <nz-layout class="app-layout">
      <!-- Header -->
      <nz-header class="header">
        <div class="header-content">
          <!-- Logo -->
          <div class="logo">
            <span class="logo-text">Itqan CMS</span>
          </div>

          <!-- Navigation Menu -->
          <ul nz-menu nzMode="horizontal" nzTheme="dark" class="main-menu">
            <li nz-menu-item>
              <a routerLink="/dashboard">
                <span nz-icon nzType="dashboard"></span>
                Dashboard
              </a>
            </li>
            <li nz-menu-item>
              <a routerLink="/public">
                <span nz-icon nzType="global"></span>
                Public Portal
              </a>
            </li>
            <li nz-menu-item *ngIf="isAdmin()">
              <a routerLink="/admin">
                <span nz-icon nzType="setting"></span>
                Admin
              </a>
            </li>
          </ul>

          <!-- User Actions -->
          <div class="user-actions">
            @if (authService.isAuthenticated()) {
              <!-- User Info -->
              <div class="user-info">
                <nz-avatar 
                  [nzSrc]="authService.user()?.picture" 
                  [nzText]="getUserInitials()"
                  nzSize="small">
                </nz-avatar>
                <span class="user-name">{{ authService.user()?.name }}</span>
                <button nz-button nzType="text" (click)="logout()">
                  <span nz-icon nzType="logout"></span>
                  Logout
                </button>
              </div>
            } @else {
              <!-- Login/Register Buttons -->
              <nz-space>
                <button *nzSpaceItem nz-button nzType="default" (click)="login()">
                  Login
                </button>
                <button *nzSpaceItem nz-button nzType="primary" (click)="register()">
                  Get Started
                </button>
              </nz-space>
            }

            <!-- Language Switcher -->
            <div class="lang-switcher">
              <button nz-button nzType="text" (click)="switchLanguage('en')" [class.active]="currentLanguage() === 'EN'">
                EN
              </button>
              <button nz-button nzType="text" (click)="switchLanguage('ar')" [class.active]="currentLanguage() === 'AR'">
                العربية
              </button>
            </div>
          </div>
        </div>
      </nz-header>

      <!-- Main Content -->
      <nz-content class="main-content">
        <router-outlet></router-outlet>
      </nz-content>

      <!-- Footer -->
      <nz-footer class="footer">
        <div class="footer-content">
          <p>&copy; 2024 Itqan Community. All rights reserved.</p>
          <div class="footer-links">
            <a href="/privacy">Privacy Policy</a>
            <a href="/terms">Terms of Service</a>
            <a href="/support">Support</a>
          </div>
        </div>
      </nz-footer>
    </nz-layout>
  `,
  styles: [`
    .app-layout {
      min-height: 100vh;
    }

    .header {
      background-color: var(--itqan-dark);
      padding: 0;
      line-height: 64px;
    }

    .header-content {
      display: flex;
      align-items: center;
      justify-content: space-between;
      max-width: 1200px;
      margin: 0 auto;
      padding: 0 16px;
      height: 64px;
    }

    .logo {
      display: flex;
      align-items: center;
      color: white;
      font-size: 18px;
      font-weight: 600;
    }

    .logo-text {
      margin-left: 12px;
    }

    .main-menu {
      flex: 1;
      margin: 0 32px;
      background: transparent;
      border: none;
    }

    .user-actions {
      display: flex;
      align-items: center;
      gap: 16px;
    }

    .user-info {
      display: flex;
      align-items: center;
      gap: 8px;
      color: white;
    }

    .user-name {
      margin-left: 8px;
    }

    .lang-switcher {
      display: flex;
      align-items: center;
      gap: 4px;
    }

    .lang-switcher button {
      color: white;
    }

    .lang-switcher button.active {
      color: var(--itqan-primary);
    }

    .main-content {
      padding: 24px;
      background: var(--itqan-bg-light);
      min-height: calc(100vh - 128px);
    }

    .footer {
      background: #f0f2f5;
      text-align: center;
      padding: 16px 0;
    }

    .footer-content {
      max-width: 1200px;
      margin: 0 auto;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }

    .footer-links {
      display: flex;
      gap: 16px;
    }

    .footer-links a {
      color: var(--itqan-text-secondary);
      text-decoration: none;
    }

    .footer-links a:hover {
      color: var(--itqan-primary);
    }

    @media (max-width: 768px) {
      .header-content {
        padding: 0 12px;
      }

      .main-menu {
        display: none;
      }

      .footer-content {
        flex-direction: column;
        gap: 8px;
      }
    }
  `]
})
export class MainLayoutComponent {
  currentLanguage = signal('EN');

  constructor(public authService: AuthService) {}

  login(): void {
    this.authService.login();
  }

  register(): void {
    this.authService.register();
  }

  logout(): void {
    this.authService.logout();
  }

  switchLanguage(lang: string): void {
    this.currentLanguage.set(lang.toUpperCase());
    // TODO: Implement i18n language switching
    if (lang === 'ar') {
      document.dir = 'rtl';
    } else {
      document.dir = 'ltr';
    }
  }

  getUserInitials(): string {
    const user = this.authService.user();
    if (!user?.name) return 'U';
    
    return user.name
      .split(' ')
      .map(n => n[0])
      .join('')
      .toUpperCase()
      .substring(0, 2);
  }

  isAdmin(): boolean {
    // TODO: Implement role-based access control
    return false;
  }
}