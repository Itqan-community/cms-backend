import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { NzSpinModule } from 'ng-zorro-antd/spin';
import { NzResultModule } from 'ng-zorro-antd/result';
import { NzButtonModule } from 'ng-zorro-antd/button';
import { NzAlertModule } from 'ng-zorro-antd/alert';

import { AuthService } from '../../core/services/auth.service';
import { StateService } from '../../core/services/state.service';
import { environment } from '../../../environments/environment';

/**
 * AUTH-002: Token Exchange Loading Component
 * 
 * Handles Auth0 callback and shows loading UI while exchanging tokens
 */
@Component({
  selector: 'app-auth-callback',
  standalone: true,
  imports: [
    CommonModule,
    NzSpinModule,
    NzResultModule,
    NzButtonModule,
    NzAlertModule
  ],
  template: `
    <div class="auth-callback-container">
      <div class="callback-card">
        
        <!-- Loading State -->
        <div *ngIf="isLoading" class="loading-section">
          <nz-spin nzSize="large">
            <div class="loading-content">
              <div class="loading-icon">
                <img src="/assets/images/itqan-logo.png" alt="Itqan CMS" class="logo" />
              </div>
              
              <h2 class="loading-title">{{ loadingMessage }}</h2>
              <p class="loading-description">
                {{ loadingDescription }}
              </p>
              
              <!-- Progress Steps -->
              <div class="progress-steps">
                <div class="step" [class.active]="currentStep >= 1" [class.completed]="currentStep > 1">
                  <div class="step-number">1</div>
                  <div class="step-text">Validating credentials</div>
                </div>
                <div class="step" [class.active]="currentStep >= 2" [class.completed]="currentStep > 2">
                  <div class="step-number">2</div>
                  <div class="step-text">Exchanging tokens</div>
                </div>
                <div class="step" [class.active]="currentStep >= 3" [class.completed]="currentStep > 3">
                  <div class="step-number">3</div>
                  <div class="step-text">Setting up profile</div>
                </div>
              </div>
            </div>
          </nz-spin>
        </div>

        <!-- Error State -->
        <div *ngIf="hasError && !isLoading" class="error-section">
          <nz-result
            nzStatus="error"
            nzTitle="Authentication Failed"
            [nzSubTitle]="errorMessage"
          >
            <div nz-result-extra>
              <button nz-button nzType="primary" (click)="retryAuthentication()">
                Try Again
              </button>
              <button nz-button nzType="default" (click)="goToLogin()">
                Back to Login
              </button>
            </div>
          </nz-result>
        </div>

        <!-- Success State (Brief) -->
        <div *ngIf="isSuccess && !isLoading" class="success-section">
          <nz-result
            nzStatus="success"
            nzTitle="Authentication Successful"
            nzSubTitle="Redirecting to your dashboard..."
          >
          </nz-result>
        </div>

      </div>
    </div>
  `,
  styles: [`
    .auth-callback-container {
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      background: linear-gradient(135deg, #669B80 0%, #22433D 100%);
      padding: 24px;
    }

    .callback-card {
      background: white;
      border-radius: 12px;
      padding: 48px;
      box-shadow: 0 8px 32px rgba(0, 0, 0, 0.12);
      max-width: 500px;
      width: 100%;
      text-align: center;
    }

    .loading-section {
      display: flex;
      flex-direction: column;
      align-items: center;
    }

    .loading-content {
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 16px;
    }

    .loading-icon {
      margin-bottom: 16px;
    }

    .logo {
      height: 60px;
      width: auto;
    }

    .loading-title {
      color: #22433D;
      font-size: 24px;
      font-weight: 600;
      margin: 0;
    }

    .loading-description {
      color: #666;
      font-size: 16px;
      margin: 0;
      line-height: 1.5;
    }

    .progress-steps {
      display: flex;
      flex-direction: column;
      gap: 16px;
      margin-top: 32px;
      width: 100%;
      max-width: 300px;
    }

    .step {
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 12px;
      border-radius: 8px;
      transition: all 0.3s ease;
      background: #f5f5f5;
    }

    .step.active {
      background: #669B80;
      color: white;
    }

    .step.completed {
      background: #52c41a;
      color: white;
    }

    .step-number {
      width: 28px;
      height: 28px;
      border-radius: 50%;
      background: rgba(255, 255, 255, 0.2);
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: 600;
      font-size: 14px;
    }

    .step.active .step-number,
    .step.completed .step-number {
      background: rgba(255, 255, 255, 0.3);
    }

    .step-text {
      font-size: 14px;
      font-weight: 500;
    }

    .error-section,
    .success-section {
      min-height: 300px;
      display: flex;
      align-items: center;
      justify-content: center;
    }

    :host ::ng-deep .ant-spin-nested-loading {
      width: 100%;
    }

    :host ::ng-deep .ant-spin-container {
      width: 100%;
    }

    :host ::ng-deep .ant-result {
      padding: 24px 0;
    }

    @media (max-width: 768px) {
      .callback-card {
        padding: 32px 24px;
        margin: 16px;
      }

      .loading-title {
        font-size: 20px;
      }

      .loading-description {
        font-size: 14px;
      }
    }
  `]
})
export class AuthCallbackComponent implements OnInit {
  private authService = inject(AuthService);
  private stateService = inject(StateService);
  private router = inject(Router);
  private http = inject(HttpClient);

  isLoading = true;
  hasError = false;
  isSuccess = false;
  errorMessage = '';
  currentStep = 1;
  
  loadingMessage = 'Authenticating...';
  loadingDescription = 'Please wait while we securely log you in.';

  ngOnInit(): void {
    this.handleAuthCallback();
  }

  private async handleAuthCallback(): Promise<void> {
    try {
      this.setLoadingStep(1, 'Validating credentials', 'Verifying your authentication with Auth0...');
      
      // Small delay to show the loading state
      await this.delay(800);
      
      this.setLoadingStep(2, 'Exchanging tokens', 'Securing your session with our backend...');
      
      // Handle the Auth0 callback and token exchange
      await this.authService.handleAuthCallback();
      
      await this.delay(500);
      
      this.setLoadingStep(3, 'Setting up profile', 'Saving your information to our system...');
      
      await this.delay(800);
      
      // Save any pending registration data to Django backend (not Auth0)
      await this.savePendingRegistrationData();
      
      // Check if user needs to complete profile (for social login)
      const needsProfileCompletion = await this.checkIfProfileCompletionNeeded();
      
      if (needsProfileCompletion) {
        // Redirect to profile completion for social login users
        this.isLoading = false;
        this.isSuccess = true;
        
        await this.delay(1000);
        await this.router.navigate(['/auth/complete-profile']);
        return;
      }
      
      // Show success briefly before redirect
      this.isLoading = false;
      this.isSuccess = true;
      
      await this.delay(1000);
      
      // Redirect to Asset Store (home page) or intended page
      const targetUrl = sessionStorage.getItem('auth_redirect_url') || '/';
      sessionStorage.removeItem('auth_redirect_url');
      await this.router.navigate([targetUrl]);
      
    } catch (error: any) {
      console.error('Auth callback error:', error);
      
      this.isLoading = false;
      this.hasError = true;
      this.errorMessage = this.getErrorMessage(error);
      
      // Clear any auth state on error
      this.authService.logout();
    }
  }

  private setLoadingStep(step: number, title: string, description: string): void {
    this.currentStep = step;
    this.loadingMessage = title;
    this.loadingDescription = description;
  }

  private getErrorMessage(error: any): string {
    if (error?.message) {
      return error.message;
    }
    
    if (typeof error === 'string') {
      return error;
    }
    
    return 'An unexpected error occurred during authentication. Please try again.';
  }

  private delay(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  async retryAuthentication(): Promise<void> {
    this.hasError = false;
    this.isLoading = true;
    this.currentStep = 1;
    await this.handleAuthCallback();
  }

  async goToLogin(): Promise<void> {
    await this.router.navigate(['/auth/login']);
  }

  /**
   * Save pending registration data to Django backend (not Auth0)
   */
  private async savePendingRegistrationData(): Promise<void> {
    try {
      // Check for pending registration data from custom form
      const pendingDataStr = sessionStorage.getItem('pendingRegistrationData');
      if (!pendingDataStr) {
        return; // No pending data to save
      }

      const pendingData = JSON.parse(pendingDataStr);
      
      // Validate data age (max 30 minutes)
      const dataAge = Date.now() - (pendingData.timestamp || 0);
      if (dataAge > 30 * 60 * 1000) {
        console.warn('Pending registration data expired, skipping save');
        sessionStorage.removeItem('pendingRegistrationData');
        return;
      }

      // Save additional user information to Django backend
      const updateData = {
        first_name: pendingData.firstName,
        last_name: pendingData.lastName,
        profile_data: {
          phone: pendingData.phone || '',
          title: pendingData.title || '',
          registration_source: 'custom_form',
          registration_completed_at: new Date().toISOString()
        }
      };

      // Call Django API to update user profile using correct endpoint
      await this.http.put(
        `${environment.apiUrl}/auth/profile/`,
        updateData
      ).toPromise();

      // Clean up session storage
      sessionStorage.removeItem('pendingRegistrationData');
      
      console.log('✅ Additional user information saved to Django backend');

    } catch (error) {
      console.error('❌ Failed to save pending registration data:', error);
      // Don't throw error - continue with authentication flow
    }
  }

  /**
   * Check if user needs to complete profile after social login
   */
  private async checkIfProfileCompletionNeeded(): Promise<boolean> {
    try {
      // Get current user from state service
      const currentUser = this.stateService.currentUser();
      
      if (!currentUser) return false;

      // Check if user has completed professional profile fields
      const hasPhone = currentUser.profile_data?.['phone'];
      const hasTitle = currentUser.profile_data?.['title'];
      
      // Get Auth0 user to check if this was a social login
      const auth0User = await this.authService.getAuth0User();
      const isSocialLogin = auth0User && 
        (auth0User as any).identities?.some((identity: any) => 
          identity.provider === 'github' || identity.provider === 'google-oauth2'
        );

      // If social login and missing professional info, needs completion
      return isSocialLogin && (!hasPhone && !hasTitle);
      
    } catch (error) {
      console.error('Error checking profile completion need:', error);
      return false;
    }
  }
}