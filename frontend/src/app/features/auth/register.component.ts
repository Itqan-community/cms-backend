import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router } from '@angular/router';
import { NzCardModule } from 'ng-zorro-antd/card';
import { NzButtonModule } from 'ng-zorro-antd/button';
import { NzDividerModule } from 'ng-zorro-antd/divider';
import { NzSpaceModule } from 'ng-zorro-antd/space';
import { NzIconModule } from 'ng-zorro-antd/icon';
import { NzTypographyModule } from 'ng-zorro-antd/typography';
import { NzGridModule } from 'ng-zorro-antd/grid';
import { NzAlertModule } from 'ng-zorro-antd/alert';

import { AuthService } from '../../core/services/auth.service';
import { StateService } from '../../core/services/state.service';

/**
 * REG-001: Registration Page Component
 * 
 * Implements wireframe-matching UI that redirects to Auth0 Universal Login
 * for GitHub SSO, Google OAuth, and email/password registration
 */
@Component({
  selector: 'app-register',
  standalone: true,
  imports: [
    CommonModule,
    NzCardModule,
    NzButtonModule,
    NzDividerModule,
    NzSpaceModule,
    NzIconModule,
    NzTypographyModule,
    NzGridModule,
    NzAlertModule
  ],
  template: `
    <div class="register-container">
      <div class="register-card-wrapper">
        <nz-card class="register-card" [nzBordered]="false">
          <!-- Header Section -->
          <div class="register-header">
            <div class="logo-section">
              <img 
                src="assets/images/itqan-logo.png" 
                alt="Itqan CMS" 
                class="logo"
                (error)="onLogoError($event)"
              />
            </div>
            <h1 class="register-title">Create Your Account</h1>
            <p class="register-subtitle">
              Join Itqan CMS to access verified Quranic content and resources
            </p>
          </div>

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

          <!-- Registration Options -->
          <div class="register-options">
            <!-- GitHub SSO (Primary) -->
            <nz-space nzDirection="vertical" nzSize="middle" class="w-full">
              <button
                nz-button
                nzType="primary"
                nzSize="large"
                nzBlock
                [nzLoading]="isLoading()"
                (click)="registerWithGitHub()"
                class="github-button"
              >
                <span nz-icon nzType="github" nzTheme="outline"></span>
                Continue with GitHub
              </button>

              <!-- Divider -->
              <nz-divider nzText="or" nzOrientation="center" class="divider"/>

              <!-- Google OAuth (Secondary) -->
              <button
                nz-button
                nzType="default"
                nzSize="large"
                nzBlock
                [nzLoading]="isLoading()"
                (click)="registerWithGoogle()"
                class="google-button"
              >
                <span nz-icon nzType="google" nzTheme="outline"></span>
                Continue with Google
              </button>

              <!-- Email/Password (Fallback) -->
              <button
                nz-button
                nzType="default"
                nzSize="large"
                nzBlock
                [nzLoading]="isLoading()"
                (click)="registerWithEmail()"
                class="email-button"
              >
                <span nz-icon nzType="mail" nzTheme="outline"></span>
                Continue with Email
              </button>
            </nz-space>
          </div>

          <!-- Terms and Privacy -->
          <div class="terms-section">
            <p class="terms-text">
              By creating an account, you agree to our
              <a href="/terms" target="_blank" class="terms-link">Terms of Service</a>
              and
              <a href="/privacy" target="_blank" class="terms-link">Privacy Policy</a>
            </p>
          </div>

          <!-- Login Link -->
          <div class="login-section">
            <p class="login-text">
              Already have an account?
              <a 
                class="login-link"
                (click)="navigateToLogin()"
                role="button"
                tabindex="0"
              >
                Sign in
              </a>
            </p>
          </div>
        </nz-card>
      </div>
    </div>
  `,
  styleUrls: ['./register.component.scss']
})
export class RegisterComponent {
  private readonly authService = inject(AuthService);
  private readonly stateService = inject(StateService);
  private readonly router = inject(Router);

  // Reactive state
  readonly isLoading = this.stateService.authLoading;
  readonly errorMessage = this.stateService.globalError;

  /**
   * Register with GitHub SSO (Primary option)
   */
  async registerWithGitHub(): Promise<void> {
    try {
      this.clearError();
      // Auth0 Universal Login will prioritize GitHub based on configuration
      await this.authService.register();
    } catch (error) {
      console.error('GitHub registration error:', error);
      this.stateService.setError('Failed to initiate GitHub registration');
    }
  }

  /**
   * Register with Google OAuth (Secondary option)
   */
  async registerWithGoogle(): Promise<void> {
    try {
      this.clearError();
      // Auth0 Universal Login with Google connection
      await this.authService.register();
    } catch (error) {
      console.error('Google registration error:', error);
      this.stateService.setError('Failed to initiate Google registration');
    }
  }

  /**
   * Register with Email/Password (Fallback option)
   */
  async registerWithEmail(): Promise<void> {
    try {
      this.clearError();
      // Auth0 Universal Login with email/password
      await this.authService.register();
    } catch (error) {
      console.error('Email registration error:', error);
      this.stateService.setError('Failed to initiate email registration');
    }
  }

  /**
   * Navigate to login page
   */
  navigateToLogin(): void {
    this.router.navigate(['/auth/login']);
  }

  /**
   * Clear error message
   */
  clearError(): void {
    this.stateService.clearError();
  }

  /**
   * Handle logo loading error
   */
  onLogoError(event: Event): void {
    // Fallback to text logo if image fails to load
    const img = event.target as HTMLImageElement;
    img.style.display = 'none';
    
    // Create text fallback
    const textLogo = document.createElement('div');
    textLogo.textContent = 'Itqan CMS';
    textLogo.className = 'text-logo';
    img.parentNode?.insertBefore(textLogo, img);
  }
}
