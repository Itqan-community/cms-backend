import { Component, effect, inject } from '@angular/core';
import { RouterOutlet, RouterLink, Router } from '@angular/router';
import { LanguageService } from './shared/language.service';
import { TranslationService } from './shared/translation.service';
import { ButtonModule } from 'primeng/button';
import { MenubarModule } from 'primeng/menubar';
import { MenuItem } from 'primeng/api';

@Component({
  selector: 'app-root',
  imports: [RouterOutlet, RouterLink, ButtonModule, MenubarModule],
  template: `
    <header class="app-header">
      <!-- Top Bar -->
      <div class="top-bar bg-surface px-4 py-3">
        <div class="container flex justify-between items-center">
          <div class="logo-section">
            <h1 class="text-dark mb-0">{{ t('header.title') }}</h1>
            <small class="text-muted">{{ t('header.subtitle') }}</small>
          </div>
          <div class="header-actions flex items-center gap-3">
            <!-- Language Toggle -->
            <div class="language-toggle flex items-center gap-2">
              <button pButton [label]="t('header.ltr')" (click)="lang.set('en')" 
                      [outlined]="lang.current()!=='en'" size="small"></button>
              <button pButton [label]="t('header.rtl')" (click)="lang.set('ar')" 
                      [outlined]="lang.current()!=='ar'" size="small"></button>
            </div>
            <!-- User Actions -->
            <div class="user-actions flex items-center gap-2">
              <button pButton label="Login" [outlined]="true" size="small" (click)="navigate('/auth/login')"></button>
              <button pButton label="Register" size="small" (click)="navigate('/auth/register-email')"></button>
            </div>
          </div>
        </div>
      </div>
      
      <!-- Navigation Menu -->
      <nav class="main-nav border-bottom">
        <div class="container">
          <p-menubar [model]="menuItems" [style]="{'border': 'none', 'background': 'transparent'}">
            <ng-template pTemplate="start">
              <a routerLink="/demo" class="nav-brand">
                <i class="pi pi-home me-2"></i>
                Demo Gallery
              </a>
            </ng-template>
          </p-menubar>
        </div>
      </nav>
    </header>
    
    <main class="app-content">
      <router-outlet></router-outlet>
    </main>
  `,
  styles: [`
    .app-header {
      position: sticky;
      top: 0;
      z-index: 1000;
      background: white;
      box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    
    .top-bar {
      border-bottom: 1px solid rgba(0,0,0,0.1);
    }
    
    .logo-section h1 {
      font-size: 1.5rem;
      margin: 0;
      line-height: 1.2;
    }
    
    .logo-section small {
      font-size: 0.875rem;
    }
    
    .main-nav {
      background: #f8f9fa;
    }
    
    .nav-brand {
      display: flex;
      align-items: center;
      text-decoration: none;
      color: var(--p-primary-500);
      font-weight: 600;
      padding: 0.5rem 1rem;
      border-radius: 0.25rem;
      transition: background-color 0.2s;
    }
    
    .nav-brand:hover {
      background: rgba(102, 155, 128, 0.1);
    }
    
    .border-bottom {
      border-bottom: 1px solid rgba(0,0,0,0.1);
    }
    
    .app-content {
      min-height: calc(100vh - 120px);
    }
    
    /* RTL Adjustments */
    [dir="rtl"] .me-2 {
      margin-left: 0.5rem;
      margin-right: 0;
    }
  `]
})
export class AppComponent {
  lang = inject(LanguageService);
  private translationService = inject(TranslationService);
  private router = inject(Router);
  
  t = this.translationService.t;
  
  menuItems: MenuItem[] = [
    {
      label: 'Content',
      icon: 'pi pi-file-text',
      items: [
        { label: 'Content Standards', routerLink: '/content-standards', icon: 'pi pi-check-square' },
        { label: 'Resources', routerLink: '/resources/123', icon: 'pi pi-database' },
        { label: 'Publishers', routerLink: '/publishers/itqan', icon: 'pi pi-users' }
      ]
    },
    {
      label: 'Authentication',
      icon: 'pi pi-user',
      items: [
        { label: 'Login', routerLink: '/auth/login', icon: 'pi pi-sign-in' },
        { label: 'Register (OAuth)', routerLink: '/auth/register-oauth', icon: 'pi pi-github' },
        { label: 'Register (Email)', routerLink: '/auth/register-email', icon: 'pi pi-envelope' },
        { label: 'Profile Setup', routerLink: '/auth/profile-capture', icon: 'pi pi-user-edit' }
      ]
    },
    {
      label: 'Pages',
      icon: 'pi pi-window-maximize',
      items: [
        { label: 'Home (Unauth)', routerLink: '/home-unauth', icon: 'pi pi-home' },
        { label: 'Home (Auth)', routerLink: '/home-auth', icon: 'pi pi-home' },
        { label: 'License Details', routerLink: '/licenses/cc0', icon: 'pi pi-file' }
      ]
    },
    {
      label: 'Dialogs',
      icon: 'pi pi-window-maximize',
      items: [
        { label: 'Resource Dialog', routerLink: '/demo/resource-dialog', icon: 'pi pi-info-circle' },
        { label: 'License Terms', routerLink: '/demo/license-terms-dialog', icon: 'pi pi-file-text' },
        { label: 'License Confirm', routerLink: '/demo/license-terms-confirm', icon: 'pi pi-check' }
      ]
    }
  ];
  
  constructor() {
    effect(() => {
      const rtl = this.lang.isRtl();
      document.documentElement.setAttribute('dir', rtl ? 'rtl' : 'ltr');
      document.documentElement.lang = this.lang.current();
    });
  }
  
  navigate(route: string) {
    this.router.navigate([route]);
  }
}
