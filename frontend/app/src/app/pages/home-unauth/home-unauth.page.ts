import { Component, inject } from '@angular/core';
import { CardModule } from 'primeng/card';
import { ButtonModule } from 'primeng/button';
import { RouterLink } from '@angular/router';
import { TranslationService } from '../../shared/translation.service';

@Component({
  standalone: true,
  selector: 'app-home-unauth',
  imports: [CardModule, ButtonModule, RouterLink],
  template: `
    <div class="home-unauth-page">
      <!-- Hero Section -->
      <section class="hero-section bg-surface py-6">
        <div class="container">
          <div class="row items-center">
            <div class="col-6">
              <div class="hero-content">
                <h1 class="hero-title text-dark mb-4">{{ t('home.unauth.title') }}</h1>
                <p class="hero-subtitle text-muted mb-6">{{ t('home.unauth.description') }}</p>
                <div class="hero-actions flex gap-3">
                  <a routerLink="/auth/register-email" pButton [label]="t('home.unauth.register')" 
                     class="primary-btn"></a>
                  <a routerLink="/auth/login" pButton [label]="t('home.unauth.login')" 
                     [outlined]="true" class="secondary-btn"></a>
                </div>
              </div>
            </div>
            <div class="col-6">
              <div class="hero-image">
                <div class="placeholder-image">
                  <i class="pi pi-book" style="font-size: 8rem; color: var(--p-primary-500); opacity: 0.3;"></i>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- Features Section -->
      <section class="features-section py-6">
        <div class="container">
          <div class="text-center mb-6">
            <h2 class="section-title text-dark mb-3">Key Features</h2>
            <p class="section-subtitle text-muted">Comprehensive Quranic content management platform</p>
          </div>
          
          <div class="row">
            <div class="col-4 mb-4">
              <p-card class="feature-card h-full">
                <div class="text-center">
                  <i class="pi pi-database feature-icon mb-3"></i>
                  <h3 class="feature-title mb-3">Resource Management</h3>
                  <p class="feature-description text-muted">
                    Upload, organize, and manage Quranic texts, translations, and audio resources
                  </p>
                </div>
              </p-card>
            </div>
            
            <div class="col-4 mb-4">
              <p-card class="feature-card h-full">
                <div class="text-center">
                  <i class="pi pi-shield feature-icon mb-3"></i>
                  <h3 class="feature-title mb-3">License Management</h3>
                  <p class="feature-description text-muted">
                    Flexible licensing system with CC0, Creative Commons, and custom licenses
                  </p>
                </div>
              </p-card>
            </div>
            
            <div class="col-4 mb-4">
              <p-card class="feature-card h-full">
                <div class="text-center">
                  <i class="pi pi-users feature-icon mb-3"></i>
                  <h3 class="feature-title mb-3">Publisher Network</h3>
                  <p class="feature-description text-muted">
                    Connect with trusted publishers and access verified Quranic content
                  </p>
                </div>
              </p-card>
            </div>
          </div>
        </div>
      </section>

      <!-- Stats Section -->
      <section class="stats-section bg-surface py-6">
        <div class="container">
          <div class="row text-center">
            <div class="col-3">
              <div class="stat-item">
                <h3 class="stat-number text-primary">1,200+</h3>
                <p class="stat-label text-muted">Resources</p>
              </div>
            </div>
            <div class="col-3">
              <div class="stat-item">
                <h3 class="stat-number text-primary">50+</h3>
                <p class="stat-label text-muted">Publishers</p>
              </div>
            </div>
            <div class="col-3">
              <div class="stat-item">
                <h3 class="stat-number text-primary">25</h3>
                <p class="stat-label text-muted">Languages</p>
              </div>
            </div>
            <div class="col-3">
              <div class="stat-item">
                <h3 class="stat-number text-primary">100%</h3>
                <p class="stat-label text-muted">Open Source</p>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- CTA Section -->
      <section class="cta-section py-6">
        <div class="container">
          <div class="text-center">
            <h2 class="cta-title text-dark mb-3">Ready to Get Started?</h2>
            <p class="cta-subtitle text-muted mb-4">
              Join our community of developers and publishers working with Quranic content
            </p>
            <div class="cta-actions flex justify-center gap-3">
              <a routerLink="/content-standards" pButton label="View Standards" [outlined]="true"></a>
              <a routerLink="/auth/register-email" pButton label="Create Account"></a>
            </div>
          </div>
        </div>
      </section>
    </div>
  `,
  styles: [`
    .home-unauth-page {
      min-height: 100vh;
    }
    
    .hero-section {
      min-height: 500px;
      display: flex;
      align-items: center;
    }
    
    .hero-title {
      font-size: 3rem;
      font-weight: 700;
      line-height: 1.2;
    }
    
    .hero-subtitle {
      font-size: 1.25rem;
      line-height: 1.6;
    }
    
    .placeholder-image {
      display: flex;
      justify-content: center;
      align-items: center;
      height: 400px;
      background: #f8f9fa;
      border-radius: 1rem;
      border: 2px dashed #dee2e6;
    }
    
    .section-title {
      font-size: 2.5rem;
      font-weight: 600;
    }
    
    .section-subtitle {
      font-size: 1.125rem;
    }
    
    .feature-card {
      transition: transform 0.2s, box-shadow 0.2s;
      height: 100%;
    }
    
    .feature-card:hover {
      transform: translateY(-4px);
      box-shadow: 0 8px 25px rgba(0,0,0,0.1);
    }
    
    .feature-icon {
      font-size: 3rem;
      color: var(--p-primary-500);
    }
    
    .feature-title {
      font-size: 1.25rem;
      font-weight: 600;
    }
    
    .feature-description {
      line-height: 1.6;
    }
    
    .stat-number {
      font-size: 2.5rem;
      font-weight: 700;
      margin-bottom: 0.5rem;
      color: var(--p-primary-500);
    }
    
    .stat-label {
      font-size: 1rem;
      font-weight: 500;
    }
    
    .cta-title {
      font-size: 2rem;
      font-weight: 600;
    }
    
    .cta-subtitle {
      font-size: 1.125rem;
      max-width: 600px;
      margin: 0 auto;
    }
    
    .col-3 {
      flex: 0 0 25%;
      max-width: 25%;
    }
    
    .col-4 {
      flex: 0 0 33.333333%;
      max-width: 33.333333%;
    }
    
    /* Responsive */
    @media (max-width: 768px) {
      .hero-title {
        font-size: 2rem;
      }
      
      .col-6, .col-4, .col-3 {
        flex: 0 0 100%;
        max-width: 100%;
      }
      
      .placeholder-image {
        height: 250px;
        margin-top: 2rem;
      }
    }
  `]
})
export class HomeUnauthPage {
  private translationService = inject(TranslationService);
  t = this.translationService.t;
}


