import { Component, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router } from '@angular/router';
import { FormBuilder, FormGroup, Validators, ReactiveFormsModule } from '@angular/forms';

// NG-ZORRO Imports
import { NzCardModule } from 'ng-zorro-antd/card';
import { NzFormModule } from 'ng-zorro-antd/form';
import { NzInputModule } from 'ng-zorro-antd/input';
import { NzButtonModule } from 'ng-zorro-antd/button';
import { NzSpaceModule } from 'ng-zorro-antd/space';
import { NzIconModule } from 'ng-zorro-antd/icon';
import { NzTypographyModule } from 'ng-zorro-antd/typography';
import { NzAlertModule } from 'ng-zorro-antd/alert';
import { NzDividerModule } from 'ng-zorro-antd/divider';

import { AuthService } from '../../core/services/auth.service';
import { StateService } from '../../core/services/state.service';
import { I18nService } from '../../core/services/i18n.service';

/**
 * Custom Registration Component
 * 
 * Collects comprehensive user information (Name, Phone, Title, Email, Password)
 * before proceeding with Auth0 registration and profile completion
 */
@Component({
  selector: 'app-custom-register',
  standalone: true,
  imports: [
    CommonModule,
    ReactiveFormsModule,
    NzCardModule,
    NzFormModule,
    NzInputModule,
    NzButtonModule,
    NzSpaceModule,
    NzIconModule,
    NzTypographyModule,
    NzAlertModule,
    NzDividerModule
  ],
  template: `
    <div class="custom-register-container">
      <div class="register-form-wrapper">
        <nz-card class="register-form-card" [nzBordered]="false">
          <!-- Header -->
          <div class="form-header">
            <h1 class="form-title">Create Account</h1>
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

          <!-- Registration Form -->
          <form nz-form [formGroup]="registerForm" (ngSubmit)="onSubmit()" class="register-form">
            <nz-space nzDirection="vertical" nzSize="large" class="w-full">
              <!-- First Name -->
              <nz-form-item>
                <nz-form-label nzRequired>First Name</nz-form-label>
                <nz-form-control>
                  <input
                    nz-input
                    formControlName="firstName"
                    placeholder="Ahmed"
                    class="form-input"
                  />
                </nz-form-control>
              </nz-form-item>

              <!-- Last Name -->
              <nz-form-item>
                <nz-form-label nzRequired>Last Name</nz-form-label>
                <nz-form-control>
                  <input
                    nz-input
                    formControlName="lastName"
                    placeholder="AlRajhy"
                    class="form-input"
                  />
                </nz-form-control>
              </nz-form-item>

              <!-- Phone -->
              <nz-form-item>
                <nz-form-label>Phone</nz-form-label>
                <nz-form-control>
                  <input
                    nz-input
                    formControlName="phone"
                    placeholder="009650000000"
                    class="form-input"
                  />
                </nz-form-control>
              </nz-form-item>

              <!-- Title -->
              <nz-form-item>
                <nz-form-label>Title</nz-form-label>
                <nz-form-control>
                  <input
                    nz-input
                    formControlName="title"
                    placeholder="Software Engineer"
                    class="form-input"
                  />
                </nz-form-control>
              </nz-form-item>

              <!-- Email -->
              <nz-form-item>
                <nz-form-label nzRequired>Email Address</nz-form-label>
                <nz-form-control>
                  <input
                    nz-input
                    formControlName="email"
                    type="email"
                    placeholder="you@example.com"
                    class="form-input"
                  />
                </nz-form-control>
              </nz-form-item>

              <!-- Password -->
              <nz-form-item>
                <nz-form-label nzRequired>Password</nz-form-label>
                <nz-form-control>
                  <input
                    nz-input
                    formControlName="password"
                    type="password"
                    placeholder="********"
                    class="form-input"
                  />
                </nz-form-control>
              </nz-form-item>

              <!-- Sign Up Button -->
              <button
                nz-button
                nzType="primary"
                nzSize="large"
                nzBlock
                [nzLoading]="isLoading()"
                [disabled]="!registerForm.valid"
                type="submit"
                class="signup-button"
              >
                Sign Up
              </button>
            </nz-space>
          </form>

          <!-- Login Link -->
          <div class="login-link-section">
            <p class="login-text">
              Already have an account?
              <a 
                class="login-link"
                (click)="navigateToLogin()"
                role="button"
                tabindex="0"
              >
                Log In
              </a>
            </p>
          </div>
        </nz-card>
      </div>
    </div>
  `,
  styles: [`
    .custom-register-container {
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
      padding: 24px;
    }

    .register-form-wrapper {
      width: 100%;
      max-width: 400px;
    }

    .register-form-card {
      box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
      border-radius: 12px;
      background: white;
    }

    .form-header {
      text-align: center;
      margin-bottom: 32px;
    }

    .form-title {
      font-size: 28px;
      font-weight: 600;
      color: #262626;
      margin: 0;
    }

    .register-form {
      width: 100%;
    }

    .form-input {
      height: 48px;
      border-radius: 8px;
      border: 1px solid #e0e0e0;
      padding: 0 16px;
      font-size: 15px;
      transition: all 0.2s ease;
    }

    .form-input:focus {
      border-color: #4285f4;
      box-shadow: 0 0 0 2px rgba(66, 133, 244, 0.1);
    }

    ::ng-deep .ant-form-item {
      margin-bottom: 0 !important;
    }

    ::ng-deep .ant-form-item-label {
      padding-bottom: 4px;
    }

    ::ng-deep .ant-form-item-label > label {
      color: #666;
      font-size: 14px;
      font-weight: 500;
    }

    .signup-button {
      height: 48px !important;
      background: #4285f4 !important;
      border-color: #4285f4 !important;
      border-radius: 8px !important;
      font-size: 16px;
      font-weight: 600;
      margin-top: 8px;
    }

    .signup-button:hover:not([disabled]) {
      background: #3367d6 !important;
      border-color: #3367d6 !important;
    }

    .signup-button:disabled {
      background: #e0e0e0 !important;
      border-color: #e0e0e0 !important;
      color: #999 !important;
    }

    .login-link-section {
      text-align: center;
      margin-top: 24px;
      padding-top: 24px;
      border-top: 1px solid #f0f0f0;
    }

    .login-text {
      color: #666;
      font-size: 14px;
      margin: 0;
    }

    .login-link {
      color: #4285f4;
      text-decoration: none;
      font-weight: 500;
      cursor: pointer;
      margin-left: 4px;
    }

    .login-link:hover {
      color: #3367d6;
      text-decoration: underline;
    }

    .error-alert {
      margin-bottom: 24px;
    }

    /* RTL Support */
    :host-context([dir="rtl"]) .login-link {
      margin-left: 0;
      margin-right: 4px;
    }

    /* Mobile Responsive */
    @media (max-width: 768px) {
      .custom-register-container {
        padding: 16px;
      }

      .register-form-wrapper {
        max-width: none;
      }

      .form-title {
        font-size: 24px;
      }

      .form-header {
        margin-bottom: 24px;
      }
    }
  `]
})
export class CustomRegisterComponent {
  private readonly authService = inject(AuthService);
  private readonly stateService = inject(StateService);
  private readonly i18nService = inject(I18nService);
  private readonly router = inject(Router);
  private readonly fb = inject(FormBuilder);

  // Reactive form
  registerForm: FormGroup = this.fb.group({
    firstName: ['', [Validators.required, Validators.minLength(2)]],
    lastName: ['', [Validators.required, Validators.minLength(2)]],
    phone: [''],
    title: [''],
    email: ['', [Validators.required, Validators.email]],
    password: ['', [Validators.required, Validators.minLength(8)]]
  });

  // Loading state
  private readonly _isLoading = signal<boolean>(false);
  readonly isLoading = this._isLoading.asReadonly();

  // Error handling
  readonly errorMessage = this.stateService.globalError;

  /**
   * Handle form submission
   */
  async onSubmit(): Promise<void> {
    if (!this.registerForm.valid) {
      this.markFormGroupTouched();
      return;
    }

    try {
      this._isLoading.set(true);
      this.clearError();

      const formData = this.registerForm.value;
      
      // Store registration data in session for post-Auth0 processing
      this.storeRegistrationData(formData);

      // Redirect to social registration options (as per flow diagram)
      // User should choose authentication method after providing profile info
      await this.router.navigate(['/auth/register/social']);

    } catch (error) {
      console.error('Registration navigation error:', error);
      this.stateService.setError('Registration failed. Please try again.');
    } finally {
      this._isLoading.set(false);
    }
  }

  /**
   * Store registration data in session storage for Auth0 callback
   */
  private storeRegistrationData(data: any): void {
    if (typeof window !== 'undefined') {
      sessionStorage.setItem('pendingRegistrationData', JSON.stringify({
        firstName: data.firstName,
        lastName: data.lastName,
        phone: data.phone,
        title: data.title,
        email: data.email,
        timestamp: Date.now()
      }));
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
   * Mark all form controls as touched for validation display
   */
  private markFormGroupTouched(): void {
    Object.keys(this.registerForm.controls).forEach(key => {
      const control = this.registerForm.get(key);
      if (control) {
        control.markAsTouched();
        control.updateValueAndValidity();
      }
    });
  }

  /**
   * Translation helper
   */
  t(key: string): string {
    return this.i18nService.translate(key);
  }
}
