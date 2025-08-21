import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { NzSpinModule } from 'ng-zorro-antd/spin';
import { NzResultModule } from 'ng-zorro-antd/result';
import { NzButtonModule } from 'ng-zorro-antd/button';
import { RouterLink } from '@angular/router';

import { AuthService } from '../../../core/services/auth.service';

@Component({
  selector: 'app-auth-callback',
  standalone: true,
  imports: [
    CommonModule,
    NzSpinModule,
    NzResultModule,
    NzButtonModule,
    RouterLink
  ],
  template: `
    <div class="auth-callback-container">
      @if (authService.isLoading()) {
        <div class="loading-state">
          <nz-spin nzSize="large">
            <div class="loading-content">
              <h3>Completing Authentication...</h3>
              <p>Please wait while we redirect you to your dashboard.</p>
            </div>
          </nz-spin>
        </div>
      } @else if (authService.error()) {
        <nz-result
          nzStatus="error"
          nzTitle="Authentication Failed"
          [nzSubTitle]="authService.error() || 'An unknown error occurred'"
        >
          <div nz-result-extra>
            <button nz-button nzType="primary" routerLink="/auth/login">
              Try Again
            </button>
            <button nz-button routerLink="/">
              Go Home
            </button>
          </div>
        </nz-result>
      } @else if (authService.isAuthenticated()) {
        <nz-result
          nzStatus="success"
          nzTitle="Welcome to Itqan CMS!"
          nzSubTitle="You have successfully logged in."
        >
          <div nz-result-extra>
            <button nz-button nzType="primary" routerLink="/dashboard">
              Go to Dashboard
            </button>
          </div>
        </nz-result>
      }
    </div>
  `,
  styles: [`
    .auth-callback-container {
      display: flex;
      justify-content: center;
      align-items: center;
      min-height: 60vh;
      padding: 24px;
    }

    .loading-state {
      text-align: center;
    }

    .loading-content {
      margin-top: 16px;
    }

    .loading-content h3 {
      color: var(--itqan-primary);
      margin-bottom: 8px;
    }

    .loading-content p {
      color: var(--itqan-text-secondary);
      margin: 0;
    }
  `]
})
export class AuthCallbackComponent implements OnInit {
  constructor(public authService: AuthService) {}

  ngOnInit(): void {
    // AuthService will automatically handle the callback
    // The template will reactively update based on auth state
  }
}
