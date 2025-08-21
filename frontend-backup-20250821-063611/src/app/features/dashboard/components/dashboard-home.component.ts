import { Component, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { NzCardModule } from 'ng-zorro-antd/card';
import { NzGridModule } from 'ng-zorro-antd/grid';
import { NzButtonModule } from 'ng-zorro-antd/button';
import { NzIconModule } from 'ng-zorro-antd/icon';
import { NzStatisticModule } from 'ng-zorro-antd/statistic';
import { NzListModule } from 'ng-zorro-antd/list';
import { NzProgressModule } from 'ng-zorro-antd/progress';
import { NzTagModule } from 'ng-zorro-antd/tag';
import { NzEmptyModule } from 'ng-zorro-antd/empty';

import { AuthService } from '../../../core/services/auth.service';

@Component({
  selector: 'app-dashboard-home',
  standalone: true,
  imports: [
    CommonModule,
    RouterLink,
    NzCardModule,
    NzGridModule,
    NzButtonModule,
    NzIconModule,
    NzStatisticModule,
    NzListModule,
    NzProgressModule,
    NzTagModule,
    NzEmptyModule
  ],
  template: `
    <div class="dashboard-container">
      <!-- Welcome Header -->
      <div class="welcome-header">
        <h1>Welcome back, {{ getUserDisplayName() }}!</h1>
        <p>Here's what's happening with your Quranic content management.</p>
      </div>

      <!-- Quick Stats -->
      <div nz-row [nzGutter]="[16, 16]" class="stats-row">
        <div nz-col nzXs="24" nzSm="12" nzMd="6">
          <nz-card>
            <nz-statistic
              nzTitle="Resources"
              nzValue="0"
              nzPrefix="📚"
              [nzValueStyle]="{ color: 'var(--itqan-primary)' }"
            ></nz-statistic>
          </nz-card>
        </div>
        <div nz-col nzXs="24" nzSm="12" nzMd="6">
          <nz-card>
            <nz-statistic
              nzTitle="Access Requests"
              nzValue="0"
              nzPrefix="📋"
              [nzValueStyle]="{ color: 'var(--itqan-primary)' }"
            ></nz-statistic>
          </nz-card>
        </div>
        <div nz-col nzXs="24" nzSm="12" nzMd="6">
          <nz-card>
            <nz-statistic
              nzTitle="API Calls"
              nzValue="0"
              nzPrefix="🔗"
              [nzValueStyle]="{ color: 'var(--itqan-primary)' }"
            ></nz-statistic>
          </nz-card>
        </div>
        <div nz-col nzXs="24" nzSm="12" nzMd="6">
          <nz-card>
            <nz-statistic
              nzTitle="Quota Used"
              nzValue="0"
              nzSuffix="/ 1000"
              nzPrefix="⚡"
              [nzValueStyle]="{ color: 'var(--itqan-primary)' }"
            ></nz-statistic>
          </nz-card>
        </div>
      </div>

      <!-- Main Content Grid -->
      <div nz-row [nzGutter]="[16, 16]" class="main-content">
        <!-- Profile Completion -->
        <div nz-col nzXs="24" nzLg="12">
          <nz-card nzTitle="Complete Your Profile" class="profile-completion-card">
            <div class="profile-progress">
              <nz-progress 
                [nzPercent]="profileCompletionPercentage()" 
                nzStatus="active"
                [nzStrokeColor]="'var(--itqan-primary)'"
              ></nz-progress>
              <p class="progress-text">{{ profileCompletionPercentage() }}% Complete</p>
            </div>

            <nz-list nzSize="small" [nzDataSource]="profileChecklist" [nzRenderItem]="checklistItem">
              <ng-template #checklistItem let-item>
                <nz-list-item>
                  <nz-list-item-meta>
                    <nz-list-item-meta-title>
                      <span [class.completed]="item.completed">
                        {{ item.completed ? '✅' : '⏳' }} {{ item.title }}
                      </span>
                    </nz-list-item-meta-title>
                    <nz-list-item-meta-description>
                      {{ item.description }}
                    </nz-list-item-meta-description>
                  </nz-list-item-meta>
                  <ul nz-list-item-actions>
                    <nz-list-item-action>
                      <button nz-button nzType="link" nzSize="small" [routerLink]="item.link">
                        {{ item.completed ? 'Edit' : 'Complete' }}
                      </button>
                    </nz-list-item-action>
                  </ul>
                </nz-list-item>
              </ng-template>
            </nz-list>
          </nz-card>
        </div>

        <!-- Recent Activity -->
        <div nz-col nzXs="24" nzLg="12">
          <nz-card nzTitle="Recent Activity">
            <nz-empty 
              nzNotFoundImage="simple"
              nzNotFoundContent="No recent activity"
              nzNotFoundFooter="Start by creating your first resource or making an access request."
            >
              <button nz-button nzType="primary" nz-empty-footer>
                Get Started
              </button>
            </nz-empty>
          </nz-card>
        </div>

        <!-- Pending Access Requests -->
        <div nz-col nzXs="24" nzLg="12">
          <nz-card nzTitle="Pending Access Requests">
            <nz-empty 
              nzNotFoundImage="simple"
              nzNotFoundContent="No pending requests"
              nzNotFoundFooter="Your access requests will appear here."
            >
            </nz-empty>
          </nz-card>
        </div>

        <!-- Quick Actions -->
        <div nz-col nzXs="24" nzLg="12">
          <nz-card nzTitle="Quick Actions">
            <div class="quick-actions">
              <button nz-button nzType="primary" nzBlock>
                <span nz-icon nzType="plus"></span>
                Create Resource
              </button>
              <button nz-button nzType="default" nzBlock>
                <span nz-icon nzType="search"></span>
                Browse Content
              </button>
              <button nz-button nzType="default" nzBlock>
                <span nz-icon nzType="key"></span>
                Request API Access
              </button>
              <button nz-button nzType="default" nzBlock>
                <span nz-icon nzType="file-text"></span>
                View Documentation
              </button>
            </div>
          </nz-card>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .dashboard-container {
      max-width: 1200px;
      margin: 0 auto;
    }

    .welcome-header {
      margin-bottom: 24px;
      text-align: center;
    }

    .welcome-header h1 {
      color: var(--itqan-primary);
      margin-bottom: 8px;
    }

    .welcome-header p {
      color: var(--itqan-text-secondary);
      font-size: 16px;
    }

    .stats-row {
      margin-bottom: 24px;
    }

    .main-content {
      margin-bottom: 24px;
    }

    .profile-progress {
      margin-bottom: 16px;
      text-align: center;
    }

    .progress-text {
      margin-top: 8px;
      color: var(--itqan-text-secondary);
      font-size: 14px;
    }

    .completed {
      color: var(--itqan-text-secondary);
      text-decoration: line-through;
    }

    .quick-actions {
      display: flex;
      flex-direction: column;
      gap: 12px;
    }

    .quick-actions button {
      height: auto;
      padding: 12px 16px;
      text-align: left;
      display: flex;
      align-items: center;
      gap: 8px;
    }

    @media (max-width: 768px) {
      .dashboard-container {
        padding: 0 12px;
      }
    }
  `]
})
export class DashboardHomeComponent {
  profileChecklist = [
    {
      title: 'Email Verification',
      description: 'Verify your email address to secure your account',
      completed: true, // Assuming Auth0 handles this
      link: '/dashboard/profile'
    },
    {
      title: 'Complete Profile Information',
      description: 'Add your organization details and preferences',
      completed: false,
      link: '/dashboard/profile'
    },
    {
      title: 'Set Up API Keys',
      description: 'Generate API keys for accessing Quranic content',
      completed: false,
      link: '/admin/api-keys'
    },
    {
      title: 'Review License Agreements',
      description: 'Accept license terms for content you want to access',
      completed: false,
      link: '/licensing'
    }
  ];

  constructor(private authService: AuthService) {}

  getUserDisplayName(): string {
    const user = this.authService.user();
    return user?.name || user?.email || 'User';
  }

  profileCompletionPercentage = computed(() => {
    const completed = this.profileChecklist.filter(item => item.completed).length;
    return Math.round((completed / this.profileChecklist.length) * 100);
  });
}
