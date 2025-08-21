import { Component, OnInit, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { NzLayoutModule } from 'ng-zorro-antd/layout';
import { NzMenuModule } from 'ng-zorro-antd/menu';
import { NzButtonModule } from 'ng-zorro-antd/button';
import { NzCardModule } from 'ng-zorro-antd/card';
import { NzGridModule } from 'ng-zorro-antd/grid';
import { NzTypographyModule } from 'ng-zorro-antd/typography';
import { NzDividerModule } from 'ng-zorro-antd/divider';
import { NzIconModule } from 'ng-zorro-antd/icon';
import { NzSpaceModule } from 'ng-zorro-antd/space';
import { NzTagModule } from 'ng-zorro-antd/tag';
import { NzStatisticModule } from 'ng-zorro-antd/statistic';
import { NzAvatarModule } from 'ng-zorro-antd/avatar';

import { NzMessageService } from 'ng-zorro-antd/message';
import { NzMessageModule } from 'ng-zorro-antd/message';

import { AuthService } from '../../core/services/auth.service';
import { I18nService } from '../../core/services/i18n.service';
import { StateService } from '../../core/services/state.service';
import { environment } from '../../../environments/environment';

interface PlatformStatistics {
  totalResources: number;
  activeDevelopers: number;
  apiCalls: number;
  countries: number;
  totalDistributions?: number;
  approvedRequests?: number;
}

@Component({
  selector: 'app-landing-page',
  standalone: true,
  imports: [
    CommonModule,
    RouterModule,
    NzLayoutModule,
    NzMenuModule,
    NzButtonModule,
    NzCardModule,
    NzGridModule,
    NzTypographyModule,
    NzDividerModule,
    NzIconModule,
    NzSpaceModule,
    NzTagModule,
    NzStatisticModule,
    NzAvatarModule,
    NzMessageModule
  ],
  template: `
    <nz-layout class="landing-layout">
      <!-- Header Navigation -->
      <nz-header class="landing-header">
        <div class="header-content">
          <div class="logo">
            <img src="/assets/images/itqan-logo.png" alt="Itqan CMS" class="logo-img">
            <span class="logo-text">{{ i18n.t()('app.name') }}</span>
          </div>

          <!-- Navigation Menu -->
          <ul nz-menu nzMode="horizontal" nzTheme="light" class="main-nav">
            <li nz-menu-item>
              <a>{{ i18n.t()('nav.home') }}</a>
            </li>
            <li nz-menu-item>
              <a>{{ i18n.t()('nav.about') }}</a>
            </li>
            <li nz-menu-item>
              <a>{{ i18n.t()('nav.documentation') }}</a>
            </li>
            <li nz-menu-item>
              <a>{{ i18n.t()('nav.api_standards') }}</a>
            </li>
          </ul>

          <!-- Auth Actions -->
          <div class="auth-actions">
            @if (stateService.isAuthenticated()) {
              <!-- Authenticated User Menu (Simplified) -->
              <div class="user-info">
                <nz-avatar [nzText]="getUserInitials()" nzSize="small"></nz-avatar>
                <span class="username">{{ (stateService.currentUser()?.first_name + ' ' + stateService.currentUser()?.last_name).trim() || stateService.currentUser()?.email }}</span>
                <button nz-button nzType="text" routerLink="/dashboard">
                  <span nz-icon nzType="dashboard"></span>
                </button>
                <button nz-button nzType="text" (click)="logout()">
                  <span nz-icon nzType="logout"></span>
                </button>
              </div>
            } @else {
              <!-- Unauthenticated Actions -->
              <nz-space>
                <button *nzSpaceItem nz-button nzType="default" routerLink="/auth/login">
                  {{ i18n.t()('auth.login') }}
                </button>
                <button *nzSpaceItem nz-button nzType="primary" routerLink="/auth/register">
                  {{ i18n.t()('auth.get_started') }}
                </button>
              </nz-space>
            }

            <!-- Language Toggle -->
            <button nz-button nzType="text" (click)="i18n.toggleLanguage()">
              <span nz-icon nzType="global"></span>
              {{ i18n.currentLanguage() === 'ar' ? 'العربية' : 'English' }}
            </button>
          </div>
        </div>
      </nz-header>

      <!-- Main Content -->
      <nz-content class="landing-content">
        <!-- Hero Section -->
        <section class="hero-section">
          <div class="hero-content">
            <div nz-row [nzGutter]="[32, 32]" nzAlign="middle">
              <div nz-col [nzSpan]="12">
                <div class="hero-text">
                  <h1 nz-typography class="hero-title">
                    {{ i18n.t()('landing.hero.title') }}
                  </h1>
                  <p nz-typography class="hero-description">
                    {{ i18n.t()('landing.hero.description') }}
                  </p>
                  
                  @if (!stateService.isAuthenticated()) {
                    <nz-space size="large" class="hero-actions">
                      <button *nzSpaceItem nz-button nzType="primary" nzSize="large" routerLink="/auth/register">
                        <span nz-icon nzType="rocket"></span>
                        {{ i18n.t()('landing.hero.start_free') }}
                      </button>
                      <button *nzSpaceItem nz-button nzType="default" nzSize="large">
                        <span nz-icon nzType="play-circle"></span>
                        {{ i18n.t()('landing.hero.watch_demo') }}
                      </button>
                    </nz-space>
                  } @else {
                    <nz-space size="large" class="hero-actions">
                      <button *nzSpaceItem nz-button nzType="primary" nzSize="large" routerLink="/dashboard">
                        <span nz-icon nzType="dashboard"></span>
                        {{ i18n.t()('nav.dashboard') }}
                      </button>
                      <button *nzSpaceItem nz-button nzType="default" nzSize="large" routerLink="/resources">
                        <span nz-icon nzType="appstore"></span>
                        {{ i18n.t()('landing.hero.browse_content') }}
                      </button>
                    </nz-space>
                  }
                </div>
              </div>
              <div nz-col [nzSpan]="12">
                <div class="hero-visual">
                  <img src="/assets/images/islamic-pattern.svg" alt="Islamic Content Management" class="hero-image">
                </div>
              </div>
            </div>
          </div>
        </section>

        <!-- API Documentation Section (following ADMIN-002.png design) -->
        <section class="api-docs-section">
          <div class="docs-container">
            <div class="docs-header">
              <h2 nz-typography>{{ i18n.t()('landing.docs.title') }}</h2>
              <p nz-typography>{{ i18n.t()('landing.docs.subtitle') }}</p>
            </div>

            <div nz-row [nzGutter]="[24, 24]">
              <!-- API Usage Standards -->
              <div nz-col [nzSpan]="8">
                <nz-card [nzTitle]="i18n.t()('landing.docs.api_usage.title')" class="docs-card">
                  <div class="docs-content">
                    <ul class="docs-list">
                      <li>{{ i18n.t()('landing.docs.api_usage.correct_format') }}</li>
                      <li>{{ i18n.t()('landing.docs.api_usage.proper_indexing') }}</li>
                      <li>{{ i18n.t()('landing.docs.api_usage.verify_database') }}</li>
                    </ul>
                    <div class="code-example">
                      <code>getVerse('2:255')</code>
                      <p class="code-desc">{{ i18n.t()('landing.docs.api_usage.example_desc') }}</p>
                    </div>
                  </div>
                </nz-card>
              </div>

              <!-- Word Usage Standards -->
              <div nz-col [nzSpan]="8">
                <nz-card [nzTitle]="i18n.t()('landing.docs.word_usage.title')" class="docs-card">
                  <div class="docs-content">
                    <ul class="docs-list">
                      <li>{{ i18n.t()('landing.docs.word_usage.defined_keys') }}</li>
                      <li>{{ i18n.t()('landing.docs.word_usage.update_list') }}</li>
                      <li>{{ i18n.t()('landing.docs.word_usage.maintain_format') }}</li>
                    </ul>
                    <div class="code-example">
                      <code>getWord("الله")</code>
                      <p class="code-desc">{{ i18n.t()('landing.docs.word_usage.example_desc') }}</p>
                    </div>
                  </div>
                </nz-card>
              </div>

              <!-- Tafsir Usage Standards -->
              <div nz-col [nzSpan]="8">
                <nz-card [nzTitle]="i18n.t()('landing.docs.tafsir_usage.title')" class="docs-card">
                  <div class="docs-content">
                    <ul class="docs-list">
                      <li>{{ i18n.t()('landing.docs.tafsir_usage.correct_reference') }}</li>
                      <li>{{ i18n.t()('landing.docs.tafsir_usage.verify_accuracy') }}</li>
                      <li>{{ i18n.t()('landing.docs.tafsir_usage.modern_interpretations') }}</li>
                    </ul>
                    <div class="code-example">
                      <code>getTafsir('2:255')</code>
                      <p class="code-desc">{{ i18n.t()('landing.docs.tafsir_usage.example_desc') }}</p>
                    </div>
                  </div>
                </nz-card>
              </div>
            </div>
          </div>
        </section>

        <!-- Statistics Section -->
        @if (!stateService.isAuthenticated()) {
          <section class="stats-section">
            <div class="stats-container">
              <div nz-row [nzGutter]="[48, 24]" nzJustify="center">
                <div nz-col [nzSpan]="6">
                  <nz-statistic 
                    [nzValue]="platformStats().totalResources" 
                    [nzTitle]="i18n.t()('landing.stats.resources')"
                    [nzSuffix]="'+'"
                    [nzValueStyle]="{ color: '#669B80' }">
                  </nz-statistic>
                </div>
                <div nz-col [nzSpan]="6">
                  <nz-statistic 
                    [nzValue]="platformStats().activeDevelopers" 
                    [nzTitle]="i18n.t()('landing.stats.developers')"
                    [nzSuffix]="'+'"
                    [nzValueStyle]="{ color: '#669B80' }">
                  </nz-statistic>
                </div>
                <div nz-col [nzSpan]="6">
                  <nz-statistic 
                    [nzValue]="platformStats().apiCalls" 
                    [nzTitle]="i18n.t()('landing.stats.api_calls')"
                    [nzSuffix]="'M+'"
                    [nzValueStyle]="{ color: '#669B80' }">
                  </nz-statistic>
                </div>
                <div nz-col [nzSpan]="6">
                  <nz-statistic 
                    [nzValue]="platformStats().countries" 
                    [nzTitle]="i18n.t()('landing.stats.countries')"
                    [nzSuffix]="'+'"
                    [nzValueStyle]="{ color: '#669B80' }">
                  </nz-statistic>
                </div>
              </div>
            </div>
          </section>
        }

        <!-- Features Section -->
        <section class="features-section">
          <div class="features-container">
            <div class="section-header">
              <h2 nz-typography>{{ i18n.t()('landing.features.title') }}</h2>
              <p nz-typography>{{ i18n.t()('landing.features.subtitle') }}</p>
            </div>

            <div nz-row [nzGutter]="[24, 24]">
              <div nz-col [nzSpan]="8">
                <nz-card class="feature-card">
                  <div class="feature-icon">
                    <span nz-icon nzType="safety-certificate" nzTheme="outline"></span>
                  </div>
                  <h3 nz-typography>{{ i18n.t()('landing.features.authentic.title') }}</h3>
                  <p nz-typography>{{ i18n.t()('landing.features.authentic.description') }}</p>
                </nz-card>
              </div>
              <div nz-col [nzSpan]="8">
                <nz-card class="feature-card">
                  <div class="feature-icon">
                    <span nz-icon nzType="global" nzTheme="outline"></span>
                  </div>
                  <h3 nz-typography>{{ i18n.t()('landing.features.multilingual.title') }}</h3>
                  <p nz-typography>{{ i18n.t()('landing.features.multilingual.description') }}</p>
                </nz-card>
              </div>
              <div nz-col [nzSpan]="8">
                <nz-card class="feature-card">
                  <div class="feature-icon">
                    <span nz-icon nzType="api" nzTheme="outline"></span>
                  </div>
                  <h3 nz-typography>{{ i18n.t()('landing.features.api.title') }}</h3>
                  <p nz-typography>{{ i18n.t()('landing.features.api.description') }}</p>
                </nz-card>
              </div>
            </div>
          </div>
        </section>
      </nz-content>

      <!-- Footer -->
      <nz-footer class="landing-footer">
        <div class="footer-content">
          <div nz-row [nzGutter]="[48, 24]">
            <div nz-col [nzSpan]="8">
              <div class="footer-section">
                <h4>{{ i18n.t()('footer.about.title') }}</h4>
                <p>{{ i18n.t()('footer.about.description') }}</p>
              </div>
            </div>
            <div nz-col [nzSpan]="8">
              <div class="footer-section">
                <h4>{{ i18n.t()('footer.resources.title') }}</h4>
                <ul class="footer-links">
                  <li><a>{{ i18n.t()('footer.resources.documentation') }}</a></li>
                  <li><a>{{ i18n.t()('footer.resources.api_reference') }}</a></li>
                  <li><a>{{ i18n.t()('footer.resources.guides') }}</a></li>
                  <li><a>{{ i18n.t()('footer.resources.support') }}</a></li>
                </ul>
              </div>
            </div>
            <div nz-col [nzSpan]="8">
              <div class="footer-section">
                <h4>{{ i18n.t()('footer.legal.title') }}</h4>
                <ul class="footer-links">
                  <li><a>{{ i18n.t()('footer.legal.privacy') }}</a></li>
                  <li><a>{{ i18n.t()('footer.legal.terms') }}</a></li>
                  <li><a>{{ i18n.t()('footer.legal.licenses') }}</a></li>
                </ul>
              </div>
            </div>
          </div>
          <nz-divider></nz-divider>
          <div class="footer-bottom">
            <p>{{ i18n.t()('footer.copyright') }}</p>
          </div>
        </div>
      </nz-footer>
    </nz-layout>
  `,
  styleUrls: ['./landing-page.component.scss']
})
export class LandingPageComponent implements OnInit {
  private authService = inject(AuthService);
  public stateService = inject(StateService);
  private http = inject(HttpClient);
  private message = inject(NzMessageService);
  public i18n = inject(I18nService);

  // Platform statistics (loaded from backend)
  platformStats = signal<PlatformStatistics>({
    totalResources: 15000,
    activeDevelopers: 2500,
    apiCalls: 45,
    countries: 85
  });

  // Loading state
  statsLoading = signal(false);

  ngOnInit(): void {
    // Load platform statistics
    this.loadPlatformStats();
  }

  getUserInitials(): string {
    const user = this.stateService.currentUser();
    if (user?.first_name && user?.last_name) {
      return (user.first_name[0] + user.last_name[0]).toUpperCase();
    } else if (user?.first_name) {
      return user.first_name[0].toUpperCase();
    }
    return user?.email?.[0]?.toUpperCase() || 'U';
  }

  logout(): void {
    this.authService.logout();
  }

  private loadPlatformStats(): void {
    this.statsLoading.set(true);
    
    // Call backend API for platform statistics using full URL
    const apiUrl = `${environment.apiUrl}/landing/statistics/`;
    this.http.get<PlatformStatistics>(apiUrl)
      .subscribe({
        next: (stats) => {
          this.platformStats.set(stats);
          this.statsLoading.set(false);
        },
        error: (error) => {
          console.error('Error loading platform statistics:', error);
          // Keep default values on error
          this.statsLoading.set(false);
          
          // Show error message if in development
          if (typeof window !== 'undefined' && window.location.hostname === 'localhost') {
            this.message.warning(this.i18n.t()('error.network'));
          }
        }
      });
  }
}
