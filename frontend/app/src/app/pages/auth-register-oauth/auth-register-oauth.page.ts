import { Component, inject } from '@angular/core';
import { ButtonModule } from 'primeng/button';
import { CardModule } from 'primeng/card';
import { RouterLink } from '@angular/router';
import { TranslationService } from '../../shared/translation.service';

@Component({
  standalone: true,
  selector: 'app-register-oauth',
  imports: [ButtonModule, CardModule, RouterLink],
  template: `
    <div class="auth-register-oauth-page">
      <div class="container">
        <div class="register-container">
          <div class="row items-center min-h-screen">
            <!-- Left Side - Branding -->
            <div class="col-6 register-branding">
              <div class="branding-content">
                <div class="brand-logo mb-4">
                  <i class="pi pi-users brand-icon"></i>
                </div>
                <h1 class="brand-title text-dark mb-3">Join Our Community</h1>
                <p class="brand-subtitle text-muted mb-4">
                  Connect with thousands of developers and publishers working with Quranic content worldwide.
                </p>
                <div class="feature-list">
                  <div class="feature-item">
                    <i class="pi pi-check-circle text-success me-2"></i>
                    <span>Quick OAuth Registration</span>
                  </div>
                  <div class="feature-item">
                    <i class="pi pi-check-circle text-success me-2"></i>
                    <span>Secure Account Creation</span>
                  </div>
                  <div class="feature-item">
                    <i class="pi pi-check-circle text-success me-2"></i>
                    <span>Instant Access to Resources</span>
                  </div>
                </div>
              </div>
            </div>
            
            <!-- Right Side - OAuth Registration -->
            <div class="col-6 register-form-section">
              <div class="register-form-container">
                <p-card class="register-card">
                  <div class="register-header text-center mb-4">
                    <h2 class="text-dark mb-2">{{ t('auth.register.oauth.title') }}</h2>
                    <p class="text-muted">Choose your preferred method to create an account</p>
                  </div>
                  
                  <!-- OAuth Registration Options -->
                  <div class="oauth-options">
                    <button pButton 
                            icon="pi pi-github" 
                            [label]="t('auth.register.oauth.github')" 
                            class="w-full mb-3 oauth-btn github-btn"
                            size="large">
                    </button>
                    
                    <button pButton 
                            icon="pi pi-google" 
                            [label]="t('auth.register.oauth.google')" 
                            class="w-full mb-4 oauth-btn google-btn"
                            size="large">
                    </button>
                  </div>
                  
                  <div class="divider-section mb-4">
                    <div class="divider-line"></div>
                    <span class="divider-text text-muted">or</span>
                    <div class="divider-line"></div>
                  </div>
                  
                  <div class="email-option text-center mb-4">
                    <a routerLink="/auth/register-email" 
                       pButton 
                       label="Register with Email" 
                       [outlined]="true" 
                       class="w-full email-register-btn">
                    </a>
                  </div>
                  
                  <div class="login-link text-center">
                    <span class="text-muted">Already have an account? </span>
                    <a routerLink="/auth/login" class="text-primary">Sign in here</a>
                  </div>
                </p-card>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .auth-register-oauth-page {
      min-height: 100vh;
      background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
    }
    
    .register-container {
      min-height: 100vh;
    }
    
    .min-h-screen {
      min-height: 100vh;
    }
    
    .register-branding {
      padding: 3rem;
      display: flex;
      align-items: center;
      justify-content: center;
    }
    
    .branding-content {
      max-width: 400px;
    }
    
    .brand-icon {
      font-size: 4rem;
      color: var(--p-primary-500);
    }
    
    .brand-title {
      font-size: 2.5rem;
      font-weight: 700;
    }
    
    .brand-subtitle {
      font-size: 1.125rem;
      line-height: 1.6;
    }
    
    .feature-list {
      display: flex;
      flex-direction: column;
      gap: 1rem;
    }
    
    .feature-item {
      display: flex;
      align-items: center;
      font-size: 1rem;
    }
    
    .register-form-section {
      padding: 3rem;
      display: flex;
      align-items: center;
      justify-content: center;
    }
    
    .register-form-container {
      width: 100%;
      max-width: 400px;
    }
    
    .register-card {
      box-shadow: 0 10px 30px rgba(0,0,0,0.1);
      border-radius: 1rem;
    }
    
    .register-header h2 {
      font-size: 1.75rem;
      font-weight: 600;
    }
    
    .oauth-btn {
      height: 56px;
      font-weight: 500;
      font-size: 1rem;
    }
    
    .github-btn {
      background: #333;
      border-color: #333;
      color: white;
    }
    
    .github-btn:hover {
      background: #24292e;
      border-color: #24292e;
    }
    
    .google-btn {
      background: #db4437;
      border-color: #db4437;
      color: white;
    }
    
    .google-btn:hover {
      background: #c23321;
      border-color: #c23321;
    }
    
    .divider-section {
      display: flex;
      align-items: center;
      margin: 1.5rem 0;
    }
    
    .divider-line {
      flex: 1;
      height: 1px;
      background: #dee2e6;
    }
    
    .divider-text {
      padding: 0 1rem;
      font-size: 0.875rem;
    }
    
    .email-register-btn {
      height: 48px;
      font-weight: 500;
    }
    
    .login-link a {
      text-decoration: none;
      font-weight: 500;
    }
    
    .login-link a:hover {
      text-decoration: underline;
    }
    
    .text-success {
      color: #28a745 !important;
    }
    
    .text-primary {
      color: var(--p-primary-500) !important;
    }
    
    .col-6 {
      flex: 0 0 50%;
      max-width: 50%;
    }
    
    /* Responsive */
    @media (max-width: 768px) {
      .col-6 {
        flex: 0 0 100%;
        max-width: 100%;
      }
      
      .register-branding {
        padding: 2rem 1rem;
        text-align: center;
      }
      
      .register-form-section {
        padding: 1rem;
      }
      
      .brand-title {
        font-size: 2rem;
      }
    }
    
    /* RTL Adjustments */
    [dir="rtl"] .me-2 {
      margin-left: 0.5rem;
      margin-right: 0;
    }
  `]
})
export class RegisterGithubGooglePage {
  private translationService = inject(TranslationService);
  t = this.translationService.t;
}


