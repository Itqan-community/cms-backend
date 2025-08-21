import { Component, inject, OnInit, OnDestroy, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router } from '@angular/router';
import { NzCardModule } from 'ng-zorro-antd/card';
import { NzButtonModule } from 'ng-zorro-antd/button';
import { NzResultModule } from 'ng-zorro-antd/result';
import { NzSpinModule } from 'ng-zorro-antd/spin';
import { NzAlertModule } from 'ng-zorro-antd/alert';
import { NzIconModule } from 'ng-zorro-antd/icon';
import { NzTypographyModule } from 'ng-zorro-antd/typography';

import { AuthService } from '../../core/services/auth.service';
import { StateService } from '../../core/services/state.service';

/**
 * REG-002: Email Verification Component
 * 
 * Shows email verification status and provides resend functionality
 * Blocks dashboard access until email is verified via Auth0
 */
@Component({
  selector: 'app-email-verification',
  standalone: true,
  imports: [
    CommonModule,
    NzCardModule,
    NzButtonModule,
    NzResultModule,
    NzSpinModule,
    NzAlertModule,
    NzIconModule,
    NzTypographyModule
  ],
  template: `
    <div class="verification-container">
      <div class="verification-card-wrapper">
        <nz-card class="verification-card" [nzBordered]="false">
          
          <!-- Loading State -->
          <div *ngIf="isChecking()" class="checking-state">
            <nz-spin nzSize="large">
              <div class="checking-content">
                <h2>Checking Email Verification Status</h2>
                <p>Please wait while we verify your email status...</p>
              </div>
            </nz-spin>
          </div>

          <!-- Email Verification Required -->
          <div *ngIf="!isChecking() && !isVerified()" class="verification-required">
            <nz-result
              nzStatus="info"
              nzTitle="Email Verification Required"
              [nzSubTitle]="getVerificationMessage()"
              class="verification-result"
            >
              <div nz-result-icon>
                <span nz-icon nzType="mail" nzTheme="outline" class="verification-icon"></span>
              </div>

              <div nz-result-content>
                <!-- Error Alert -->
                <nz-alert
                  *ngIf="errorMessage()"
                  [nzMessage]="errorMessage()"
                  nzType="error"
                  nzShowIcon
                  nzClosable
                  (nzOnClose)="clearError()"
                  class="error-alert"
                />

                <!-- Success Alert -->
                <nz-alert
                  *ngIf="resendSuccess"
                  nzMessage="Verification email sent successfully!"
                  nzDescription="Please check your inbox and spam folder. The link will expire in 24 hours."
                  nzType="success"
                  nzShowIcon
                  nzClosable
                  (nzOnClose)="resendSuccess = false"
                  class="success-alert"
                />

                <!-- Action Buttons -->
                <div class="verification-actions">
                  <button
                    nz-button
                    nzType="primary"
                    nzSize="large"
                    [nzLoading]="isResending"
                    (click)="resendVerificationEmail()"
                    [disabled]="resendCooldown > 0"
                    class="resend-button"
                  >
                    <span nz-icon nzType="send" nzTheme="outline"></span>
                    {{ getResendButtonText() }}
                  </button>

                  <button
                    nz-button
                    nzType="default"
                    nzSize="large"
                    [nzLoading]="isChecking()"
                    (click)="checkVerificationStatus()"
                    class="check-button"
                  >
                    <span nz-icon nzType="reload" nzTheme="outline"></span>
                    Check Status
                  </button>

                  <button
                    nz-button
                    nzType="text"
                    nzSize="large"
                    (click)="changeEmail()"
                    class="change-email-button"
                  >
                    <span nz-icon nzType="edit" nzTheme="outline"></span>
                    Use Different Email
                  </button>
                </div>

                <!-- Help Text -->
                <div class="help-section">
                  <h4>Didn't receive the email?</h4>
                  <ul class="help-list">
                    <li>Check your spam or junk folder</li>
                    <li>Make sure {{ userEmail }} is correct</li>
                    <li>Add no-reply&#64;itqan-cms.com to your contacts</li>
                    <li>Wait a few minutes before requesting another email</li>
                  </ul>
                </div>
              </div>
            </nz-result>
          </div>

          <!-- Email Verified Success -->
          <div *ngIf="!isChecking() && isVerified()" class="verification-success">
            <nz-result
              nzStatus="success"
              nzTitle="Email Verified Successfully!"
              nzSubTitle="Your account is now fully activated. Welcome to Itqan CMS."
              class="success-result"
            >
              <div nz-result-content>
                <button
                  nz-button
                  nzType="primary"
                  nzSize="large"
                  (click)="goToDashboard()"
                  class="dashboard-button"
                >
                  <span nz-icon nzType="dashboard" nzTheme="outline"></span>
                  Go to Dashboard
                </button>
              </div>
            </nz-result>
          </div>

        </nz-card>
      </div>
    </div>
  `,
  styleUrls: ['./email-verification.component.scss']
})
export class EmailVerificationComponent implements OnInit, OnDestroy {
  private readonly authService = inject(AuthService);
  private readonly stateService = inject(StateService);
  private readonly router = inject(Router);

  // Component state
  private readonly _isChecking = signal<boolean>(true);
  private readonly _isVerified = signal<boolean>(false);
  
  readonly isChecking = this._isChecking.asReadonly();
  readonly isVerified = this._isVerified.asReadonly();
  readonly errorMessage = this.stateService.globalError;

  isResending = false;
  resendSuccess = false;
  resendCooldown = 0;
  userEmail = '';
  
  private cooldownInterval?: any;

  ngOnInit(): void {
    this.initializeVerificationCheck();
  }

  ngOnDestroy(): void {
    if (this.cooldownInterval) {
      clearInterval(this.cooldownInterval);
    }
  }

  /**
   * Initialize verification status check
   */
  private async initializeVerificationCheck(): Promise<void> {
    try {
      // Get current user info from Auth0
      const auth0User = await this.authService.getAuth0User();
      
      if (auth0User) {
        this.userEmail = auth0User.email || '';
        this._isVerified.set(auth0User.email_verified || false);
      }

      // If already verified, proceed to dashboard
      if (this.isVerified()) {
        setTimeout(() => this.goToDashboard(), 2000);
      }
      
    } catch (error) {
      console.error('Failed to check verification status:', error);
      this.stateService.setError('Failed to check email verification status');
    } finally {
      this._isChecking.set(false);
    }
  }

  /**
   * Check verification status by re-fetching user info
   */
  async checkVerificationStatus(): Promise<void> {
    this._isChecking.set(true);
    this.clearError();

    try {
      // Force token refresh to get latest user info
      await this.authService.refreshToken();
      
      // Get updated user info
      const auth0User = await this.authService.getAuth0User();
      
      if (auth0User) {
        this._isVerified.set(auth0User.email_verified || false);
        
        if (this.isVerified()) {
          // Update Django backend with verified status
          await this.authService.refreshUserProfile();
        }
      }
      
    } catch (error) {
      console.error('Failed to check verification status:', error);
      this.stateService.setError('Failed to refresh verification status');
    } finally {
      this._isChecking.set(false);
    }
  }

  /**
   * Resend verification email via Auth0
   */
  async resendVerificationEmail(): Promise<void> {
    if (this.resendCooldown > 0) return;

    this.isResending = true;
    this.clearError();

    try {
      // In a real implementation, you'd call Auth0 Management API
      // For now, we'll simulate the call
      await new Promise(resolve => setTimeout(resolve, 2000));
      
      this.resendSuccess = true;
      this.startResendCooldown();
      
    } catch (error) {
      console.error('Failed to resend verification email:', error);
      this.stateService.setError('Failed to send verification email. Please try again.');
    } finally {
      this.isResending = false;
    }
  }

  /**
   * Start cooldown timer for resend button
   */
  private startResendCooldown(): void {
    this.resendCooldown = 60; // 60 seconds cooldown
    
    this.cooldownInterval = setInterval(() => {
      this.resendCooldown--;
      
      if (this.resendCooldown <= 0) {
        clearInterval(this.cooldownInterval);
      }
    }, 1000);
  }

  /**
   * Navigate to dashboard
   */
  goToDashboard(): void {
    this.router.navigate(['/dashboard']);
  }

  /**
   * Change email address (logout and re-register)
   */
  changeEmail(): void {
    this.authService.logout();
  }

  /**
   * Clear error message
   */
  clearError(): void {
    this.stateService.clearError();
  }

  /**
   * Get verification message based on email
   */
  getVerificationMessage(): string {
    if (this.userEmail) {
      return `We've sent a verification link to ${this.userEmail}. Please check your inbox and click the link to verify your account.`;
    }
    return 'Please check your email for a verification link to activate your account.';
  }

  /**
   * Get resend button text based on cooldown
   */
  getResendButtonText(): string {
    if (this.resendCooldown > 0) {
      return `Resend in ${this.resendCooldown}s`;
    }
    return 'Resend Email';
  }
}
