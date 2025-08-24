import { Component, inject } from '@angular/core';
import { InputTextModule } from 'primeng/inputtext';
import { PasswordModule } from 'primeng/password';
import { ButtonModule } from 'primeng/button';
import { CardModule } from 'primeng/card';
import { CheckboxModule } from 'primeng/checkbox';
import { RouterLink } from '@angular/router';
import { TranslationService } from '../../shared/translation.service';

@Component({
  standalone: true,
  selector: 'app-register-email',
  imports: [InputTextModule, PasswordModule, ButtonModule, CardModule, CheckboxModule, RouterLink],
  template: `
    <div class="auth-register-email-page">
      <div class="container">
        <div class="register-container">
          <div class="row items-center min-h-screen">
            <!-- Left Side - Branding -->
            <div class="col-6 register-branding">
              <div class="branding-content">
                <div class="brand-logo mb-4">
                  <i class="pi pi-envelope brand-icon"></i>
                </div>
                <h1 class="brand-title text-dark mb-3">Create Your Account</h1>
                <p class="brand-subtitle text-muted mb-4">
                  Start your journey with Quranic content management. Create an account to access thousands of verified resources.
                </p>
                <div class="feature-list">
                  <div class="feature-item">
                    <i class="pi pi-check-circle text-success me-2"></i>
                    <span>Free Account Creation</span>
                  </div>
                  <div class="feature-item">
                    <i class="pi pi-check-circle text-success me-2"></i>
                    <span>Email Verification</span>
                  </div>
                  <div class="feature-item">
                    <i class="pi pi-check-circle text-success me-2"></i>
                    <span>Full Platform Access</span>
                  </div>
                </div>
              </div>
            </div>
            
            <!-- Right Side - Email Registration Form -->
            <div class="col-6 register-form-section">
              <div class="register-form-container">
                <p-card class="register-card">
                  <div class="register-header text-center mb-4">
                    <h2 class="text-dark mb-2">{{ t('auth.register.email.title') }}</h2>
                    <p class="text-muted">Fill in your details to create your account</p>
                  </div>
                  
                  <!-- Registration Form -->
                  <form class="register-form">
                    <div class="form-group mb-3">
                      <label for="firstName" class="form-label">First Name</label>
                      <input pInputText id="firstName" type="text" class="w-full" 
                             placeholder="Enter your first name" />
                    </div>
                    
                    <div class="form-group mb-3">
                      <label for="lastName" class="form-label">Last Name</label>
                      <input pInputText id="lastName" type="text" class="w-full" 
                             placeholder="Enter your last name" />
                    </div>
                    
                    <div class="form-group mb-3">
                      <label for="email" class="form-label">{{ t('auth.login.email') }}</label>
                      <input pInputText id="email" type="email" class="w-full" 
                             placeholder="Enter your email address" />
                    </div>
                    
                    <div class="form-group mb-3">
                      <label for="password" class="form-label">{{ t('auth.login.password') }}</label>
                      <p-password id="password" [feedback]="true" class="w-full" 
                                  placeholder="Create a strong password" [toggleMask]="true"></p-password>
                    </div>
                    
                    <div class="form-group mb-3">
                      <label for="confirmPassword" class="form-label">Confirm Password</label>
                      <p-password id="confirmPassword" [feedback]="false" class="w-full" 
                                  placeholder="Confirm your password" [toggleMask]="true"></p-password>
                    </div>
                    
                    <div class="form-options mb-4">
                      <div class="terms-agreement flex items-start">
                        <p-checkbox inputId="terms" [binary]="true" class="me-2"></p-checkbox>
                        <label for="terms" class="terms-label">
                          I agree to the <a href="#" class="text-primary">Terms of Service</a> 
                          and <a href="#" class="text-primary">Privacy Policy</a>
                        </label>
                      </div>
                    </div>
                    
                    <button pButton [label]="t('auth.register.email.createAccount')" 
                            class="w-full register-btn mb-4"></button>
                    
                    <div class="oauth-alternative text-center mb-4">
                      <p class="text-muted mb-3">Or register with</p>
                      <div class="oauth-buttons flex gap-2">
                        <a routerLink="/auth/register-oauth" 
                           pButton icon="pi pi-github" [outlined]="true" 
                           class="flex-1 oauth-btn-small"></a>
                        <a routerLink="/auth/register-oauth" 
                           pButton icon="pi pi-google" [outlined]="true" 
                           class="flex-1 oauth-btn-small"></a>
                      </div>
                    </div>
                    
                    <div class="login-link text-center">
                      <span class="text-muted">Already have an account? </span>
                      <a routerLink="/auth/login" class="text-primary">Sign in here</a>
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
    .auth-register-email-page {
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
      max-width: 450px;
    }
    
    .register-card {
      box-shadow: 0 10px 30px rgba(0,0,0,0.1);
      border-radius: 1rem;
    }
    
    .register-header h2 {
      font-size: 1.75rem;
      font-weight: 600;
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
    
    .register-btn {
      height: 48px;
      font-weight: 600;
      font-size: 1rem;
    }
    
    .terms-agreement {
      gap: 0.5rem;
    }
    
    .terms-label {
      font-size: 0.875rem;
      line-height: 1.4;
      color: #6b7280;
    }
    
    .terms-label a {
      text-decoration: none;
    }
    
    .terms-label a:hover {
      text-decoration: underline;
    }
    
    .oauth-buttons {
      justify-content: center;
    }
    
    .oauth-btn-small {
      height: 40px;
      width: 60px;
    }
    
    .flex-1 {
      flex: 1;
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
      
      .oauth-buttons {
        flex-direction: column;
      }
    }
    
    /* RTL Adjustments */
    [dir="rtl"] .me-2 {
      margin-left: 0.5rem;
      margin-right: 0;
    }
  `]
})
export class RegisterEmailPage {
  private translationService = inject(TranslationService);
  t = this.translationService.t;
}


