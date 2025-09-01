import { Component, computed, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterOutlet, RouterLink, RouterLinkActive } from '@angular/router';
import { NzLayoutModule } from 'ng-zorro-antd/layout';
import { NzMenuModule } from 'ng-zorro-antd/menu';
import { NzIconModule } from 'ng-zorro-antd/icon';
import { FormsModule } from '@angular/forms';
import { NzAvatarModule } from 'ng-zorro-antd/avatar';
import { NzButtonModule } from 'ng-zorro-antd/button';

import { NzSpaceModule } from 'ng-zorro-antd/space';
import { NzTypographyModule } from 'ng-zorro-antd/typography';
import { NzBadgeModule } from 'ng-zorro-antd/badge';

import { StateService } from '../core/services/state.service';
import { AuthService } from '../core/services/auth.service';
import { I18nService } from '../core/services/i18n.service';

/**
 * Main Islamic content management layout component
 * Provides header with Arabic support, sidebar navigation, and responsive design
 */
@Component({
  selector: 'app-islamic-layout',
  standalone: true,
  imports: [
    CommonModule,
    RouterOutlet,
    RouterLink,
    RouterLinkActive,
    FormsModule,
    NzLayoutModule,
    NzMenuModule,
    NzIconModule,

    NzAvatarModule,
    NzButtonModule,

    NzSpaceModule,
    NzTypographyModule,
    NzBadgeModule
  ],
  template: `
    <nz-layout class="islamic-layout">
      <!-- Header with Islamic branding and bilingual support -->
      <nz-header class="islamic-header">
        <div class="header-content">
          <!-- Logo and brand -->
          <div class="logo-section">
            <button 
              nz-button 
              nzType="text" 
              nzSize="large"
              class="sidebar-trigger"
              (click)="toggleSidebar()">
              <span nz-icon [nzType]="sidebarCollapsed() ? 'menu-unfold' : 'menu-fold'"></span>
            </button>
            
            <div class="logo">
              <span class="logo-icon" nz-icon nzType="book"></span>
              <span class="logo-text">{{ t()('nav.dashboard') === 'Dashboard' ? 'إتقان' : 'Itqan' }}</span>
              <span class="logo-subtitle">CMS</span>
            </div>
          </div>

          <!-- Header actions -->
          <div class="header-actions">
            <nz-space nzSize="middle">
              <!-- Language switcher -->
              <div class="language-switcher">
                <button 
                  nz-button 
                  nzType="text" 
                  nzSize="small"
                  (click)="toggleLanguage()"
                  class="lang-button">
                  {{ currentLanguage() === 'ar' ? 'العربية' : 'English' }}
                  <span nz-icon nzType="global"></span>
                </button>
              </div>

              <!-- Notifications -->
              @if (isAuthenticated()) {
                <button nz-button nzType="text" nzSize="large">
                  <nz-badge [nzCount]="pendingNotifications()">
                    <span nz-icon nzType="bell"></span>
                  </nz-badge>
                </button>
              }

              <!-- User menu -->
              @if (isAuthenticated()) {
                <div class="user-menu">
                  <div class="user-info">
                    <nz-avatar 
                      [nzSrc]="currentUser()?.profile_data?.['picture']" 
                      [nzText]="getUserInitials()"
                      nzSize="small">
                    </nz-avatar>
                    <span class="user-name">{{ userDisplayName() }}</span>
                    <button nz-button nzType="text" nzSize="small" (click)="logout()">
                      <span nz-icon nzType="logout"></span>
                    </button>
                  </div>
                </div>
              } @else {
                <button nz-button nzType="primary" routerLink="/auth/login">
                  {{ t()('nav.login') }}
                </button>
              }
            </nz-space>
          </div>
        </div>
      </nz-header>

      <nz-layout class="main-layout">
        <!-- Sidebar navigation -->
        @if (isAuthenticated()) {
          <nz-sider 
            class="sidebar"
            [nzCollapsed]="sidebarCollapsed()"
            [nzWidth]="240"
            [nzCollapsedWidth]="80"
            nzTheme="light">
            
            <ul nz-menu nzMode="inline" [nzInlineCollapsed]="sidebarCollapsed()">
              <!-- Dashboard -->
              <li nz-menu-item routerLink="/dashboard" routerLinkActive="ant-menu-item-selected">
                <span nz-icon nzType="dashboard"></span>
                <span>{{ t()('nav.dashboard') }}</span>
              </li>

              <!-- Resources (Publisher/Admin) -->
              @if (isPublisher() || isAdmin()) {
                <li nz-menu-item routerLink="/resources" routerLinkActive="ant-menu-item-selected">
                  <span nz-icon nzType="book"></span>
                  <span>{{ t()('nav.resources') }}</span>
                </li>
              }

              <!-- Access Requests -->
              <li nz-menu-item routerLink="/access-requests" routerLinkActive="ant-menu-item-selected">
                <span nz-icon nzType="key"></span>
                <span>{{ t()('nav.access_requests') }}</span>
                @if (pendingAccessRequests().length > 0) {
                  <nz-badge [nzCount]="pendingAccessRequests().length" nzSize="small"></nz-badge>
                }
              </li>

              <!-- Analytics (Admin/Publisher) -->
              @if (isAdmin() || isPublisher()) {
                <li nz-menu-item routerLink="/analytics" routerLinkActive="ant-menu-item-selected">
                  <span nz-icon nzType="bar-chart"></span>
                  <span>{{ t()('nav.analytics') }}</span>
                </li>
              }

              <!-- Administration (Admin only) -->
              @if (isAdmin()) {
                <li nz-submenu nzTitle="{{ t()('nav.admin') }}" nzIcon="setting">
                  <ul>
                    <li nz-menu-item routerLink="/admin/users">
                      <span>{{ t()('admin.users') }}</span>
                    </li>
                    <li nz-menu-item routerLink="/admin/roles">
                      <span>{{ t()('admin.roles') }}</span>
                    </li>
                    <li nz-menu-item routerLink="/admin/licenses">
                      <span>{{ t()('admin.licenses') }}</span>
                    </li>
                  </ul>
                </li>
              }
            </ul>
          </nz-sider>
        }

        <!-- Main content area -->
        <nz-layout class="content-layout">
          <nz-content class="main-content">
            <div class="content-wrapper" [class.no-sidebar]="!isAuthenticated()">
              <!-- Skip link for accessibility -->
              <a class="skip-link" href="#main-content">
                {{ currentLanguage() === 'ar' ? 'انتقل إلى المحتوى الرئيسي' : 'Skip to main content' }}
              </a>
              
              <!-- Main content -->
              <main id="main-content" [attr.lang]="currentLanguage()">
                <router-outlet></router-outlet>
              </main>
            </div>
          </nz-content>

          <!-- Footer -->
          <nz-footer class="islamic-footer">
            <div class="footer-content">
              <div class="footer-section">
                <h4>{{ t()('islamic.bismillah') }}</h4>
                <p class="footer-description">
                  {{ currentLanguage() === 'ar' 
                    ? 'نظام إتقان لإدارة المحتوى القرآني - منصة شاملة لنشر وتوزيع المحتوى الإسلامي المعتمد'
                    : 'Itqan Quranic Content Management System - Comprehensive platform for verified Islamic content distribution'
                  }}
                </p>
              </div>
              
              <div class="footer-links">
                <a href="/about">{{ currentLanguage() === 'ar' ? 'حول النظام' : 'About' }}</a>
                <a href="/privacy">{{ currentLanguage() === 'ar' ? 'سياسة الخصوصية' : 'Privacy Policy' }}</a>
                <a href="/terms">{{ currentLanguage() === 'ar' ? 'شروط الاستخدام' : 'Terms of Use' }}</a>
                <a href="/contact">{{ currentLanguage() === 'ar' ? 'اتصل بنا' : 'Contact' }}</a>
              </div>
              
              <div class="footer-copyright">
                <p>&copy; {{ currentYear() }} {{ currentLanguage() === 'ar' ? 'جميع الحقوق محفوظة' : 'All rights reserved' }}</p>
              </div>
            </div>
          </nz-footer>
        </nz-layout>
      </nz-layout>
    </nz-layout>
  `,
  styles: [`
    .islamic-layout {
      min-height: 100vh;
    }

    .islamic-header {
      background: linear-gradient(135deg, #669B80 0%, #22433D 100%);
      padding: 0;
      height: 64px;
      line-height: 64px;
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
      position: fixed;
      top: 0;
      left: 0;
      right: 0;
      z-index: 1000;
    }

    .header-content {
      display: flex;
      align-items: center;
      justify-content: space-between;
      height: 100%;
      padding: 0 24px;
    }

    .logo-section {
      display: flex;
      align-items: center;
      gap: 16px;
    }

    .sidebar-trigger {
      color: rgba(255, 255, 255, 0.85);
      
      &:hover {
        color: white;
        background-color: rgba(255, 255, 255, 0.1);
      }
    }

    .logo {
      display: flex;
      align-items: center;
      gap: 8px;
      color: white;
      font-weight: bold;
      text-decoration: none;
      
      .logo-icon {
        font-size: 24px;
      }
      
      .logo-text {
        font-size: 20px;
        font-family: 'Amiri', 'Noto Sans Arabic', sans-serif;
      }
      
      .logo-subtitle {
        font-size: 12px;
        opacity: 0.8;
        font-weight: normal;
      }
    }

    .header-actions {
      .lang-select {
        min-width: 100px;
        
        :deep(.ant-select-selector) {
          background: rgba(255, 255, 255, 0.1);
          border: 1px solid rgba(255, 255, 255, 0.2);
          color: white;
        }
        
        :deep(.ant-select-arrow) {
          color: rgba(255, 255, 255, 0.8);
        }
      }
      
      .user-info {
        display: flex;
        align-items: center;
        gap: 8px;
        color: white;
        cursor: pointer;
        padding: 8px 12px;
        border-radius: 6px;
        transition: background-color 0.3s;
        
        &:hover {
          background-color: rgba(255, 255, 255, 0.1);
        }
        
        .user-name {
          max-width: 120px;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }
      }
    }

    .main-layout {
      margin-top: 64px;
    }

    .sidebar {
      position: fixed;
      left: 0;
      top: 64px;
      bottom: 0;
      z-index: 999;
      box-shadow: 2px 0 8px rgba(0, 0, 0, 0.1);
      
      :deep(.ant-layout-sider-children) {
        overflow-y: auto;
        overflow-x: hidden;
      }
      
      :deep(.ant-menu) {
        border-right: none;
        
        .ant-menu-item {
          margin: 4px 8px;
          border-radius: 6px;
          
          &:hover {
            background-color: rgba(102, 155, 128, 0.1);
          }
          
          &.ant-menu-item-selected {
            background-color: rgba(102, 155, 128, 0.15);
            color: #669B80;
          }
        }
        
        .ant-menu-submenu-title {
          margin: 4px 8px;
          border-radius: 6px;
          
          &:hover {
            background-color: rgba(102, 155, 128, 0.1);
          }
        }
      }
    }

    .content-layout {
      margin-left: 240px;
      transition: margin-left 0.3s;
      
      &.collapsed {
        margin-left: 80px;
      }
    }

    .main-content {
      padding: 24px;
      background: #f0f2f5;
      min-height: calc(100vh - 64px - 70px);
    }

    .content-wrapper {
      background: white;
      padding: 24px;
      border-radius: 8px;
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
      min-height: calc(100vh - 64px - 70px - 48px);
      
      &.no-sidebar {
        margin-left: 0;
      }
    }

    .skip-link {
      position: absolute;
      top: -40px;
      left: 6px;
      background: #669B80;
      color: white;
      padding: 8px;
      text-decoration: none;
      border-radius: 4px;
      z-index: 1000;
      
      &:focus {
        top: 6px;
      }
    }

    .islamic-footer {
      background: #f8f9fa;
      border-top: 1px solid #e9ecef;
      padding: 24px 0;
      margin-left: 240px;
      transition: margin-left 0.3s;
      
      &.collapsed {
        margin-left: 80px;
      }
    }

    .footer-content {
      max-width: 1200px;
      margin: 0 auto;
      padding: 0 24px;
      
      .footer-section {
        margin-bottom: 16px;
        
        h4 {
          color: #22433D;
          font-family: 'Amiri', 'Noto Sans Arabic', sans-serif;
          margin-bottom: 8px;
        }
        
        .footer-description {
          color: #6c757d;
          line-height: 1.6;
          margin-bottom: 0;
        }
      }
      
      .footer-links {
        display: flex;
        gap: 24px;
        margin-bottom: 16px;
        flex-wrap: wrap;
        
        a {
          color: #669B80;
          text-decoration: none;
          
          &:hover {
            text-decoration: underline;
          }
        }
      }
      
      .footer-copyright {
        color: #6c757d;
        font-size: 12px;
        
        p {
          margin: 0;
        }
      }
    }

    // RTL Support
    [dir="rtl"] {
      .sidebar {
        left: auto;
        right: 0;
      }
      
      .content-layout {
        margin-left: 0;
        margin-right: 240px;
        
        &.collapsed {
          margin-left: 0;
          margin-right: 80px;
        }
      }
      
      .islamic-footer {
        margin-left: 0;
        margin-right: 240px;
        
        &.collapsed {
          margin-left: 0;
          margin-right: 80px;
        }
      }
      
      .footer-links {
        justify-content: flex-end;
      }
      
      .logo {
        flex-direction: row-reverse;
      }
      
      .header-actions {
        .user-info {
          flex-direction: row-reverse;
        }
      }
    }

    // Mobile responsiveness
    @media (max-width: 768px) {
      .content-layout,
      .islamic-footer {
        margin-left: 0 !important;
        margin-right: 0 !important;
      }
      
      .sidebar {
        transform: translateX(-100%);
        transition: transform 0.3s;
        
        &.mobile-open {
          transform: translateX(0);
        }
      }
      
      [dir="rtl"] .sidebar {
        transform: translateX(100%);
        
        &.mobile-open {
          transform: translateX(0);
        }
      }
      
      .header-content {
        padding: 0 16px;
      }
      
      .logo-text {
        display: none;
      }
      
      .user-name {
        display: none;
      }
      
      .footer-links {
        justify-content: center;
      }
    }
  `]
})
export class IslamicLayoutComponent {
  private readonly stateService = inject(StateService);
  private readonly authService = inject(AuthService);
  private readonly i18nService = inject(I18nService);

  // State signals
  readonly currentUser = this.stateService.currentUser;
  readonly isAuthenticated = this.stateService.isAuthenticated;
  readonly currentLanguage = this.stateService.currentLanguage;
  readonly sidebarCollapsed = this.stateService.sidebarCollapsed;
  readonly userDisplayName = this.stateService.userDisplayName;
  readonly isAdmin = this.stateService.isAdmin;
  readonly isPublisher = this.stateService.isPublisher;
  readonly isDeveloper = this.stateService.isDeveloper;
  readonly pendingAccessRequests = this.stateService.pendingAccessRequests;

  // Translation function
  readonly t = this.i18nService.t;

  // Computed values
  readonly currentYear = signal(new Date().getFullYear());
  readonly pendingNotifications = computed(() => {
    // This would be connected to a notifications service
    return this.pendingAccessRequests().length;
  });

  getUserInitials(): string {
    const user = this.currentUser();
    if (!user) return 'U';
    
    const firstInitial = user.first_name?.charAt(0) || '';
    const lastInitial = user.last_name?.charAt(0) || '';
    
    if (firstInitial && lastInitial) {
      return `${firstInitial}${lastInitial}`.toUpperCase();
    }
    
    return user.email?.charAt(0).toUpperCase() || 'U';
  }

  toggleSidebar(): void {
    this.stateService.toggleSidebar();
  }

  toggleLanguage(): void {
    this.i18nService.toggleLanguage();
  }

  async logout(): Promise<void> {
    await this.authService.logout();
  }
}
