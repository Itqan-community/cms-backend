import { Component, inject } from '@angular/core';
import { CardModule } from 'primeng/card';
import { ButtonModule } from 'primeng/button';
import { InputTextModule } from 'primeng/inputtext';
import { PasswordModule } from 'primeng/password';
import { CheckboxModule } from 'primeng/checkbox';
import { DividerModule } from 'primeng/divider';
import { RouterLink } from '@angular/router';
import { TranslationService } from '../../shared/translation.service';

@Component({
  standalone: true,
  selector: 'app-login',
  imports: [CardModule, ButtonModule, InputTextModule, PasswordModule, CheckboxModule, DividerModule, RouterLink],
  template: `
    <div class="auth-login-page">
      <div class="container">
        <div class="login-container">
          <div class="row items-center min-h-screen">
            <!-- Left Side - Branding -->
            <div class="col-6 login-branding">
              <div class="branding-content">
                <div class="brand-logo mb-4">
                  <i class="pi pi-book brand-icon"></i>
                </div>
                <h1 class="brand-title text-dark mb-3">{{ t('auth.login.welcome') }}</h1>
                <p class="brand-subtitle text-muted mb-4">
                  Access your Quranic content management dashboard and explore thousands of verified resources.
                </p>
                <div class="feature-list">
                  <div class="feature-item">
                    <i class="pi pi-check-circle text-success me-2"></i>
                    <span>Verified Quranic Resources</span>
                  </div>
                  <div class="feature-item">
                    <i class="pi pi-check-circle text-success me-2"></i>
                    <span>Multiple License Options</span>
                  </div>
                  <div class="feature-item">
                    <i class="pi pi-check-circle text-success me-2"></i>
                    <span>Publisher Network Access</span>
                  </div>
                </div>
              </div>
            </div>
            
            <!-- Right Side - Login Form -->
            <div class="col-6 login-form-section">
              <div class="login-form-container">
                <p-card class="login-card">
                  <div class="login-header text-center mb-4">
                    <h2 class="text-dark mb-2">{{ t('auth.login.title') }}</h2>
                    <p class="text-muted">Enter your credentials to access your account</p>
                  </div>
                  
                  <!-- Social Login -->
                  <div class="social-login mb-4">
                    <button pButton label="Continue with Google" icon="pi pi-google" 
                            [outlined]="true" class="w-full mb-2 social-btn google-btn"></button>
                    <button pButton label="Continue with GitHub" icon="pi pi-github" 
                            [outlined]="true" class="w-full social-btn github-btn"></button>
                  </div>
                  
                  <p-divider align="center">
                    <span class="text-muted">or</span>
                  </p-divider>
                  
                  <!-- Email Login Form -->
                  <form class="login-form">
                    <div class="form-group mb-4">
                      <label for="email" class="form-label">{{ t('auth.login.email') }}</label>
                      <input pInputText id="email" type="email" class="w-full" 
                             placeholder="Enter your email address" />
                    </div>
                    
                    <div class="form-group mb-4">
                      <label for="password" class="form-label">{{ t('auth.login.password') }}</label>
                      <p-password id="password" [feedback]="false" class="w-full" 
                                  placeholder="Enter your password" [toggleMask]="true"></p-password>
                    </div>
                    
                    <div class="form-options flex justify-between items-center mb-4">
                      <div class="remember-me flex items-center">
                        <p-checkbox inputId="remember" [binary]="true"></p-checkbox>
                        <label for="remember" class="ms-2">Remember me</label>
                      </div>
                      <a href="#" class="forgot-password text-primary">Forgot password?</a>
                    </div>
                    
                    <button pButton [label]="t('auth.login.loginButton')" class="w-full login-btn mb-4"></button>
                    
                    <div class="register-link text-center">
                      <span class="text-muted">Don't have an account? </span>
                      <a routerLink="/auth/register-email" class="text-primary">{{ t('auth.login.register') }}</a>
                    </div>
                  </form>
                </p-card>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .auth-login-page {
      min-height: 100vh;
      background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
    }
    
    .login-container {
      min-height: 100vh;
    }
    
    .min-h-screen {
      min-height: 100vh;
    }
    
    .login-branding {
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
    
    .login-form-section {
      padding: 3rem;
      display: flex;
      align-items: center;
      justify-content: center;
    }
    
    .login-form-container {
      width: 100%;
      max-width: 400px;
    }
    
    .login-card {
      box-shadow: 0 10px 30px rgba(0,0,0,0.1);
      border-radius: 1rem;
    }
    
    .login-header h2 {
      font-size: 1.75rem;
      font-weight: 600;
    }
    
    .social-btn {
      height: 48px;
      font-weight: 500;
    }
    
    .google-btn {
      border-color: #db4437;
      color: #db4437;
    }
    
    .google-btn:hover {
      background: #db4437;
      color: white;
    }
    
    .github-btn {
      border-color: #333;
      color: #333;
    }
    
    .github-btn:hover {
      background: #333;
      color: white;
    }
    
    .form-label {
      display: block;
      margin-bottom: 0.5rem;
      font-weight: 500;
      color: #374151;
    }
    
    .form-group input,
    .form-group p-password {
      height: 48px;
    }
    
    .login-btn {
      height: 48px;
      font-weight: 600;
      font-size: 1rem;
    }
    
    .forgot-password {
      text-decoration: none;
      font-size: 0.875rem;
    }
    
    .forgot-password:hover {
      text-decoration: underline;
    }
    
    .register-link a {
      text-decoration: none;
      font-weight: 500;
    }
    
    .register-link a:hover {
      text-decoration: underline;
    }
    
    .text-success {
      color: #28a745 !important;
    }
    
    .text-primary {
      color: var(--p-primary-500) !important;
    }
    
    /* Responsive */
    @media (max-width: 768px) {
      .col-6 {
        flex: 0 0 100%;
        max-width: 100%;
      }
      
      .login-branding {
        padding: 2rem 1rem;
        text-align: center;
      }
      
      .login-form-section {
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
    
    [dir="rtl"] .ms-2 {
      margin-right: 0.5rem;
      margin-left: 0;
    }
  `]
})
export class LoginPage {
  private translationService = inject(TranslationService);
  t = this.translationService.t;
}


