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
import { I18nService } from '../../core/services/i18n.service';

/**
 * AUTH-001: Login Page Component
 * 
 * Implements wireframe-matching UI that redirects to Auth0 Universal Login
 * for GitHub SSO, Google OAuth, and email/password authentication
 */
@Component({
  selector: 'app-login',
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
    <div class="login-container">
      <div class="login-card-wrapper">
        <nz-card class="login-card" [nzBordered]="false">
          <!-- Header Section -->
          <div class="login-header">
            <div class="logo-section">
              <img 
                src="assets/images/itqan-logo.png" 
                alt="Itqan CMS" 
                class="logo"
                (error)="onLogoError($event)"
              />
            </div>
            <h1 class="login-title">{{ t('auth.welcome') }}</h1>
            <p class="login-subtitle">
              {{ t('auth.login_title') }}
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

          <!-- Login Options -->
          <div class="login-options">
            <!-- GitHub SSO (Primary) -->
            <nz-space nzDirection="vertical" nzSize="middle" class="w-full">
              <button
                nz-button
                nzType="primary"
                nzSize="large"
                nzBlock
                [nzLoading]="isLoading()"
                (click)="loginWithGitHub()"
                class="github-button"
              >
                <span nz-icon nzType="github" nzTheme="outline"></span>
                {{ t('auth.continue_github') }}
              </button>

              <!-- Divider -->
              <nz-divider [nzText]="t('common.or')" nzOrientation="center" class="divider"/>

              <!-- Google OAuth (Secondary) -->
              <button
                nz-button
                nzType="default"
                nzSize="large"
                nzBlock
                [nzLoading]="isLoading()"
                (click)="loginWithGoogle()"
                class="google-button"
              >
                <span nz-icon nzType="google" nzTheme="outline"></span>
                {{ t('auth.continue_google') }}
              </button>

              <!-- Email/Password (Fallback) -->
              <button
                nz-button
                nzType="default"
                nzSize="large"
                nzBlock
                [nzLoading]="isLoading()"
                (click)="loginWithEmail()"
                class="email-button"
              >
                <span nz-icon nzType="mail" nzTheme="outline"></span>
                {{ t('auth.continue_email') }}
              </button>
            </nz-space>
          </div>

          <!-- Additional Options -->
          <div class="additional-options">
            <div class="options-row">
              <a 
                class="forgot-link"
                (click)="forgotPassword()"
                role="button"
                tabindex="0"
              >
                {{ t('auth.forgot_password_link') }}
              </a>
            </div>
          </div>

          <!-- Terms and Privacy -->
          <div class="terms-section">
            <p class="terms-text">
              {{ t('auth.terms_agreement') }}
              <a href="/terms" target="_blank" class="terms-link">{{ t('auth.terms_service') }}</a>
              {{ t('common.and') }}
              <a href="/privacy" target="_blank" class="terms-link">{{ t('auth.privacy_policy') }}</a>
            </p>
          </div>

          <!-- Register Link -->
          <div class="register-section">
            <p class="register-text">
              {{ t('auth.no_account') }}
              <a 
                class="register-link"
                (click)="navigateToRegister()"
                role="button"
                tabindex="0"
              >
                {{ t('auth.register_free') }}
              </a>
            </p>
          </div>
        </nz-card>
      </div>
    </div>
  `,
  styleUrls: ['./login.component.scss']
})
export class LoginComponent {
  private readonly authService = inject(AuthService);
  private readonly stateService = inject(StateService);
  private readonly router = inject(Router);
  private readonly i18nService = inject(I18nService);

  // Reactive state
  readonly isLoading = this.stateService.authLoading;
  readonly errorMessage = this.stateService.globalError;

  /**
   * Translation helper method
   */
  t(key: string): string {
    return this.i18nService.translate(key);
  }

  /**
   * Login with GitHub SSO (Primary option)
   */
  async loginWithGitHub(): Promise<void> {
    try {
      this.clearError();
      // Direct to GitHub OAuth
      await this.authService.loginWithGitHub('/dashboard');
    } catch (error) {
      console.error('GitHub login error:', error);
      this.stateService.setError('Failed to initiate GitHub login');
    }
  }

  /**
   * Login with Google OAuth (Secondary option)
   */
  async loginWithGoogle(): Promise<void> {
    try {
      this.clearError();
      // Direct to Google OAuth
      await this.authService.loginWithGoogle('/dashboard');
    } catch (error) {
      console.error('Google login error:', error);
      this.stateService.setError('Failed to initiate Google login');
    }
  }

  /**
   * Login with Email/Password (Fallback option)
   */
  async loginWithEmail(): Promise<void> {
    try {
      this.clearError();
      // Auth0 Universal Login with email/password
      await this.authService.login('/dashboard');
    } catch (error) {
      console.error('Email login error:', error);
      this.stateService.setError('Failed to initiate email login');
    }
  }

  /**
   * Handle forgot password
   */
  forgotPassword(): void {
    // Redirect to Auth0 password reset
    const auth0Domain = 'dev-itqan.eu.auth0.com'; // Should come from environment
    const clientId = 'N3S0JhhYSWaLuhVMuBb9ZTX4gEPJ0G8f'; // Should come from environment
    
    const resetUrl = `https://${auth0Domain}/login?` +
      `client=${clientId}&` +
      `screen_hint=forgot_password&` +
      `connection=Username-Password-Authentication`;
    
    window.location.href = resetUrl;
  }

  /**
   * Navigate to registration page
   */
  navigateToRegister(): void {
    this.router.navigate(['/auth/register']);
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
