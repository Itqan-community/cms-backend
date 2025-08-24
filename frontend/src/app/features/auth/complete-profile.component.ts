import { Component, inject, signal, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router, ActivatedRoute } from '@angular/router';
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
import { NzTagModule } from 'ng-zorro-antd/tag';

import { AuthService } from '../../core/services/auth.service';
import { StateService } from '../../core/services/state.service';
import { I18nService } from '../../core/services/i18n.service';
import { HttpClient } from '@angular/common/http';
import { environment } from '../../../environments/environment';

/**
 * Complete Profile Component
 * 
 * Shown after successful GitHub/Google social login to collect
 * additional professional information (Phone, Title) that wasn't 
 * available from the social provider
 */
@Component({
  selector: 'app-complete-profile',
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
    NzTagModule
  ],
  template: `
    <div class="complete-profile-container">
      <div class="profile-form-wrapper">
        <nz-card class="profile-form-card" [nzBordered]="false">
          <!-- Header -->
          <div class="form-header">
            <div class="welcome-section" *ngIf="userInfo()">
              <nz-tag [nzColor]="getProviderColor()" class="provider-tag">
                <span nz-icon [nzType]="getProviderIcon()" nzTheme="outline"></span>
                {{ getProviderName() }}
              </nz-tag>
              <h1 class="form-title">Complete Your Profile</h1>
              <p class="form-subtitle">
                Hi {{ userInfo()?.given_name || userInfo()?.name }}, 
                please provide some additional information to complete your registration.
              </p>
            </div>
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

          <!-- Profile Completion Form -->
          <form nz-form [formGroup]="profileForm" (ngSubmit)="onSubmit()" class="profile-form">
            <nz-space nzDirection="vertical" nzSize="large" class="w-full">
              <!-- First Name (Pre-filled from social) -->
              <nz-form-item>
                <nz-form-label nzRequired>First Name</nz-form-label>
                <nz-form-control>
                  <input
                    nz-input
                    formControlName="firstName"
                    class="form-input"
                    [readonly]="isFieldPrefilled('firstName')"
                  />
                  <small *ngIf="isFieldPrefilled('firstName')" class="prefilled-note">
                    From {{ getProviderName() }} account
                  </small>
                </nz-form-control>
              </nz-form-item>

              <!-- Last Name (Pre-filled from social) -->
              <nz-form-item>
                <nz-form-label nzRequired>Last Name</nz-form-label>
                <nz-form-control>
                  <input
                    nz-input
                    formControlName="lastName"
                    class="form-input"
                    [readonly]="isFieldPrefilled('lastName')"
                  />
                  <small *ngIf="isFieldPrefilled('lastName')" class="prefilled-note">
                    From {{ getProviderName() }} account
                  </small>
                </nz-form-control>
              </nz-form-item>

              <!-- Phone (New field to collect) -->
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

              <!-- Title (New field to collect) -->
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

              <!-- Email (Pre-filled, read-only) -->
              <nz-form-item>
                <nz-form-label nzRequired>Email Address</nz-form-label>
                <nz-form-control>
                  <input
                    nz-input
                    formControlName="email"
                    type="email"
                    class="form-input"
                    readonly
                  />
                  <small class="prefilled-note">
                    From {{ getProviderName() }} account
                  </small>
                </nz-form-control>
              </nz-form-item>

              <!-- Complete Registration Button -->
              <button
                nz-button
                nzType="primary"
                nzSize="large"
                nzBlock
                [nzLoading]="isLoading()"
                [disabled]="!profileForm.valid"
                type="submit"
                class="complete-button"
              >
                Complete Registration
              </button>

              <!-- Skip Button (Optional) -->
              <button
                nz-button
                nzType="text"
                nzSize="large"
                nzBlock
                (click)="skipProfileCompletion()"
                class="skip-button"
                type="button"
              >
                Skip for now
              </button>
            </nz-space>
          </form>
        </nz-card>
      </div>
    </div>
  `,
  styles: [`
    .complete-profile-container {
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
      padding: 24px;
    }

    .profile-form-wrapper {
      width: 100%;
      max-width: 400px;
    }

    .profile-form-card {
      box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
      border-radius: 12px;
      background: white;
    }

    .form-header {
      text-align: center;
      margin-bottom: 32px;
    }

    .welcome-section {
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 12px;
    }

    .provider-tag {
      font-size: 13px;
      padding: 4px 12px;
      border-radius: 16px;
    }

    .form-title {
      font-size: 24px;
      font-weight: 600;
      color: #262626;
      margin: 0;
    }

    .form-subtitle {
      font-size: 15px;
      color: #666;
      margin: 0;
      line-height: 1.5;
    }

    .profile-form {
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

    .form-input[readonly] {
      background-color: #f8f8f8;
      color: #666;
    }

    .prefilled-note {
      color: #999;
      font-size: 12px;
      font-style: italic;
      margin-top: 4px;
      display: block;
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

    .complete-button {
      height: 48px !important;
      background: #4285f4 !important;
      border-color: #4285f4 !important;
      border-radius: 8px !important;
      font-size: 16px;
      font-weight: 600;
      margin-top: 8px;
    }

    .complete-button:hover:not([disabled]) {
      background: #3367d6 !important;
      border-color: #3367d6 !important;
    }

    .complete-button:disabled {
      background: #e0e0e0 !important;
      border-color: #e0e0e0 !important;
      color: #999 !important;
    }

    .skip-button {
      height: 36px !important;
      color: #999 !important;
      font-size: 14px;
      margin-top: 8px;
    }

    .skip-button:hover {
      color: #666 !important;
    }

    .error-alert {
      margin-bottom: 24px;
    }

    /* Mobile Responsive */
    @media (max-width: 768px) {
      .complete-profile-container {
        padding: 16px;
      }

      .profile-form-wrapper {
        max-width: none;
      }

      .form-title {
        font-size: 20px;
      }

      .form-header {
        margin-bottom: 24px;
      }
    }
  `]
})
export class CompleteProfileComponent implements OnInit {
  private readonly authService = inject(AuthService);
  private readonly stateService = inject(StateService);
  private readonly i18nService = inject(I18nService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);
  private readonly fb = inject(FormBuilder);
  private readonly http = inject(HttpClient);

  // User information from Auth0
  private readonly _userInfo = signal<any>(null);
  readonly userInfo = this._userInfo.asReadonly();

  // Social provider info
  private readonly _socialProvider = signal<string>('');

  // Reactive form
  profileForm: FormGroup = this.fb.group({
    firstName: ['', [Validators.required, Validators.minLength(2)]],
    lastName: ['', [Validators.required, Validators.minLength(2)]],
    phone: [''],
    title: [''],
    email: ['', [Validators.required, Validators.email]]
  });

  // Loading state
  private readonly _isLoading = signal<boolean>(false);
  readonly isLoading = this._isLoading.asReadonly();

  // Error handling
  readonly errorMessage = this.stateService.globalError;

  async ngOnInit(): Promise<void> {
    await this.loadUserInfo();
    this.prefillForm();
  }

  /**
   * Load user information from Auth0
   */
  private async loadUserInfo(): Promise<void> {
    try {
      const user = await this.authService.getAuth0User();
      if (user) {
        this._userInfo.set(user);
        // Determine social provider from user identities
        const identities = (user as any).identities || [];
        if (identities.length > 0) {
          this._socialProvider.set(identities[0].provider || '');
        }
      }
    } catch (error) {
      console.error('Failed to load user info:', error);
    }
  }

  /**
   * Pre-fill form with data from social provider
   */
  private prefillForm(): void {
    const user = this.userInfo();
    if (!user) return;

    // Extract names from different possible fields
    const firstName = user.given_name || user.first_name || this.extractFirstName(user.name) || '';
    const lastName = user.family_name || user.last_name || this.extractLastName(user.name) || '';
    const email = user.email || '';

    this.profileForm.patchValue({
      firstName,
      lastName,
      email
    });
  }

  /**
   * Extract first name from full name
   */
  private extractFirstName(fullName: string): string {
    if (!fullName) return '';
    return fullName.split(' ')[0] || '';
  }

  /**
   * Extract last name from full name
   */
  private extractLastName(fullName: string): string {
    if (!fullName) return '';
    const parts = fullName.split(' ');
    return parts.length > 1 ? parts[parts.length - 1] : '';
  }

  /**
   * Check if field is pre-filled from social provider
   */
  isFieldPrefilled(fieldName: string): boolean {
    const user = this.userInfo();
    if (!user) return false;

    switch (fieldName) {
      case 'firstName':
        return !!(user.given_name || user.first_name || user.name);
      case 'lastName':
        return !!(user.family_name || user.last_name || user.name);
      case 'email':
        return !!user.email;
      default:
        return false;
    }
  }

  /**
   * Get provider name for display
   */
  getProviderName(): string {
    const provider = this._socialProvider();
    switch (provider) {
      case 'github':
        return 'GitHub';
      case 'google-oauth2':
        return 'Google';
      default:
        return 'Social';
    }
  }

  /**
   * Get provider icon
   */
  getProviderIcon(): string {
    const provider = this._socialProvider();
    switch (provider) {
      case 'github':
        return 'github';
      case 'google-oauth2':
        return 'google';
      default:
        return 'user';
    }
  }

  /**
   * Get provider color
   */
  getProviderColor(): string {
    const provider = this._socialProvider();
    switch (provider) {
      case 'github':
        return '#24292e';
      case 'google-oauth2':
        return '#4285f4';
      default:
        return '#666';
    }
  }

  /**
   * Handle form submission
   */
  async onSubmit(): Promise<void> {
    if (!this.profileForm.valid) {
      this.markFormGroupTouched();
      return;
    }

    try {
      this._isLoading.set(true);
      this.clearError();

      const formData = this.profileForm.value;

      // Update user metadata in backend
      await this.updateUserProfile(formData);

      // Navigate to Asset Store (home)
      await this.router.navigate(['/']);

    } catch (error) {
      console.error('Profile completion error:', error);
      this.stateService.setError('Failed to complete profile. Please try again.');
    } finally {
      this._isLoading.set(false);
    }
  }

  /**
   * Skip profile completion (minimal required info only)
   */
  async skipProfileCompletion(): Promise<void> {
    try {
      this._isLoading.set(true);
      
      // Just update with minimal info
      const minimalData = {
        firstName: this.profileForm.get('firstName')?.value || '',
        lastName: this.profileForm.get('lastName')?.value || '',
        email: this.profileForm.get('email')?.value || ''
      };

      await this.updateUserProfile(minimalData);
      await this.router.navigate(['/']);

    } catch (error) {
      console.error('Skip profile error:', error);
      this.stateService.setError('Failed to complete registration. Please try again.');
    } finally {
      this._isLoading.set(false);
    }
  }

  /**
   * Update user profile in Django backend (not Auth0)
   */
  private async updateUserProfile(profileData: any): Promise<void> {
    const updateData = {
      first_name: profileData.firstName,
      last_name: profileData.lastName,
      profile_data: {
        phone: profileData.phone || '',
        title: profileData.title || '',
        registration_source: 'social_login',
        social_provider: this.getProviderName(),
        profile_completed_at: new Date().toISOString()
      }
    };

    // Call Django backend API to update user profile (not Auth0) using correct endpoint
    await this.http.put(
      `${environment.apiUrl}/auth/profile/`,
      updateData
    ).toPromise();
    
    console.log('✅ Profile information saved to Django backend');
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
    Object.keys(this.profileForm.controls).forEach(key => {
      const control = this.profileForm.get(key);
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
