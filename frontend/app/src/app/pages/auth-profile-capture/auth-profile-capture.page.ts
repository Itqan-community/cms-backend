import { Component, inject } from '@angular/core';
import { InputTextModule } from 'primeng/inputtext';
import { DropdownModule } from 'primeng/dropdown';
import { ButtonModule } from 'primeng/button';
import { CardModule } from 'primeng/card';
import { InputTextarea } from 'primeng/inputtextarea';
import { RouterLink } from '@angular/router';
import { TranslationService } from '../../shared/translation.service';

@Component({
  standalone: true,
  selector: 'app-profile-capture',
  imports: [InputTextModule, DropdownModule, ButtonModule, CardModule, InputTextarea, RouterLink],
  template: `
    <div class="auth-profile-capture-page">
      <div class="container">
        <div class="profile-container">
          <div class="row items-center min-h-screen">
            <!-- Left Side - Progress & Info -->
            <div class="col-6 profile-branding">
              <div class="branding-content">
                <div class="progress-indicator mb-4">
                  <div class="step completed">
                    <div class="step-number">1</div>
                    <span class="step-label">Account Created</span>
                  </div>
                  <div class="step-line"></div>
                  <div class="step active">
                    <div class="step-number">2</div>
                    <span class="step-label">Profile Setup</span>
                  </div>
                  <div class="step-line"></div>
                  <div class="step">
                    <div class="step-number">3</div>
                    <span class="step-label">Get Started</span>
                  </div>
                </div>
                
                <h1 class="brand-title text-dark mb-3">Complete Your Profile</h1>
                <p class="brand-subtitle text-muted mb-4">
                  Help us personalize your experience by providing some additional information about yourself and your work.
                </p>
                
                <div class="feature-list">
                  <div class="feature-item">
                    <i class="pi pi-check-circle text-success me-2"></i>
                    <span>Personalized Content Recommendations</span>
                  </div>
                  <div class="feature-item">
                    <i class="pi pi-check-circle text-success me-2"></i>
                    <span>Connect with Relevant Publishers</span>
                  </div>
                  <div class="feature-item">
                    <i class="pi pi-check-circle text-success me-2"></i>
                    <span>Access Role-Specific Features</span>
                  </div>
                </div>
              </div>
            </div>
            
            <!-- Right Side - Profile Form -->
            <div class="col-6 profile-form-section">
              <div class="profile-form-container">
                <p-card class="profile-card">
                  <div class="profile-header text-center mb-4">
                    <h2 class="text-dark mb-2">{{ t('auth.profile.title') }}</h2>
                    <p class="text-muted">Tell us more about yourself</p>
                  </div>
                  
                  <!-- Profile Form -->
                  <form class="profile-form">
                    <div class="form-group mb-3">
                      <label for="fullName" class="form-label">{{ t('auth.profile.fullName') }}</label>
                      <input pInputText id="fullName" type="text" class="w-full" 
                             placeholder="Enter your full name" />
                    </div>
                    
                    <div class="form-group mb-3">
                      <label for="role" class="form-label">{{ t('auth.profile.role') }}</label>
                      <p-dropdown id="role" [options]="roles" optionLabel="label" 
                                  [placeholder]="t('auth.profile.role')" class="w-full"></p-dropdown>
                    </div>
                    
                    <div class="form-group mb-3">
                      <label for="organization" class="form-label">{{ t('auth.profile.organization') }}</label>
                      <input pInputText id="organization" type="text" class="w-full" 
                             placeholder="Enter your organization or company" />
                    </div>
                    
                    <div class="form-group mb-3">
                      <label for="country" class="form-label">Country</label>
                      <p-dropdown id="country" [options]="countries" optionLabel="label" 
                                  placeholder="Select your country" class="w-full"></p-dropdown>
                    </div>
                    
                    <div class="form-group mb-3">
                      <label for="interests" class="form-label">Areas of Interest</label>
                      <p-dropdown id="interests" [options]="interests" optionLabel="label" 
                                  placeholder="Select your primary interest" class="w-full"></p-dropdown>
                    </div>
                    
                    <div class="form-group mb-4">
                      <label for="bio" class="form-label">Bio (Optional)</label>
                      <textarea pInputTextarea id="bio" rows="3" class="w-full" 
                                placeholder="Tell us a bit about yourself and your work..."></textarea>
                    </div>
                    
                    <div class="form-actions">
                      <button pButton [label]="t('auth.profile.save')" 
                              class="w-full profile-btn mb-3"></button>
                      
                      <div class="skip-option text-center">
                        <a routerLink="/home-auth" class="text-muted skip-link">
                          Skip for now - I'll complete this later
                        </a>
                      </div>
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
    .auth-profile-capture-page {
      min-height: 100vh;
      background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
    }
    
    .profile-container {
      min-height: 100vh;
    }
    
    .min-h-screen {
      min-height: 100vh;
    }
    
    .profile-branding {
      padding: 3rem;
      display: flex;
      align-items: center;
      justify-content: center;
    }
    
    .branding-content {
      max-width: 400px;
    }
    
    /* Progress Indicator */
    .progress-indicator {
      display: flex;
      align-items: center;
      margin-bottom: 2rem;
    }
    
    .step {
      display: flex;
      flex-direction: column;
      align-items: center;
      text-align: center;
    }
    
    .step-number {
      width: 40px;
      height: 40px;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: 600;
      margin-bottom: 0.5rem;
      background: #e9ecef;
      color: #6c757d;
    }
    
    .step.completed .step-number {
      background: #28a745;
      color: white;
    }
    
    .step.active .step-number {
      background: var(--p-primary-500);
      color: white;
    }
    
    .step-label {
      font-size: 0.75rem;
      color: #6c757d;
      white-space: nowrap;
    }
    
    .step-line {
      width: 40px;
      height: 2px;
      background: #e9ecef;
      margin: 0 10px;
      margin-top: -20px;
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
    
    .profile-form-section {
      padding: 3rem;
      display: flex;
      align-items: center;
      justify-content: center;
    }
    
    .profile-form-container {
      width: 100%;
      max-width: 450px;
    }
    
    .profile-card {
      box-shadow: 0 10px 30px rgba(0,0,0,0.1);
      border-radius: 1rem;
    }
    
    .profile-header h2 {
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
    .form-group p-dropdown,
    .form-group textarea {
      height: 48px;
    }
    
    .form-group textarea {
      height: auto;
      min-height: 80px;
    }
    
    .profile-btn {
      height: 48px;
      font-weight: 600;
      font-size: 1rem;
    }
    
    .skip-link {
      text-decoration: none;
      font-size: 0.875rem;
    }
    
    .skip-link:hover {
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
      
      .profile-branding {
        padding: 2rem 1rem;
        text-align: center;
      }
      
      .profile-form-section {
        padding: 1rem;
      }
      
      .brand-title {
        font-size: 2rem;
      }
      
      .progress-indicator {
        justify-content: center;
      }
      
      .step-line {
        width: 30px;
      }
    }
    
    /* RTL Adjustments */
    [dir="rtl"] .me-2 {
      margin-left: 0.5rem;
      margin-right: 0;
    }
  `]
})
export class ProfileCapturePage {
  private translationService = inject(TranslationService);
  t = this.translationService.t;
  
  get roles() {
    return [
      {label: this.t('auth.profile.developer'), value: 'developer'},
      {label: this.t('auth.profile.publisher'), value: 'publisher'},
      {label: 'Researcher', value: 'researcher'},
      {label: 'Student', value: 'student'},
      {label: 'Other', value: 'other'}
    ];
  }
  
  get countries() {
    return [
      {label: 'United States', value: 'us'},
      {label: 'United Kingdom', value: 'uk'},
      {label: 'Canada', value: 'ca'},
      {label: 'Saudi Arabia', value: 'sa'},
      {label: 'UAE', value: 'ae'},
      {label: 'Egypt', value: 'eg'},
      {label: 'Pakistan', value: 'pk'},
      {label: 'Indonesia', value: 'id'},
      {label: 'Malaysia', value: 'my'},
      {label: 'Turkey', value: 'tr'},
      {label: 'Other', value: 'other'}
    ];
  }
  
  get interests() {
    return [
      {label: 'Quran Text & Translation', value: 'quran_text'},
      {label: 'Tafsir & Commentary', value: 'tafsir'},
      {label: 'Hadith Collections', value: 'hadith'},
      {label: 'Islamic Audio/Recitation', value: 'audio'},
      {label: 'Educational Content', value: 'education'},
      {label: 'Research & Academia', value: 'research'},
      {label: 'Mobile App Development', value: 'mobile'},
      {label: 'Web Development', value: 'web'},
      {label: 'Other', value: 'other'}
    ];
  }
}


