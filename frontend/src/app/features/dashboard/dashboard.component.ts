import { Component, OnInit, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router } from '@angular/router';
import { NzLayoutModule } from 'ng-zorro-antd/layout';
import { NzMenuModule } from 'ng-zorro-antd/menu';
import { NzIconModule } from 'ng-zorro-antd/icon';
import { NzCardModule } from 'ng-zorro-antd/card';
import { NzButtonModule } from 'ng-zorro-antd/button';
import { NzProgressModule } from 'ng-zorro-antd/progress';
import { NzTagModule } from 'ng-zorro-antd/tag';
import { NzEmptyModule } from 'ng-zorro-antd/empty';
import { NzGridModule } from 'ng-zorro-antd/grid';
import { NzTypographyModule } from 'ng-zorro-antd/typography';
import { NzStatisticModule } from 'ng-zorro-antd/statistic';
import { NzBadgeModule } from 'ng-zorro-antd/badge';
import { NzAvatarModule } from 'ng-zorro-antd/avatar';

import { AuthService } from '../../core/services/auth.service';
import { StateService } from '../../core/services/state.service';

interface ProfileChecklistItem {
  id: string;
  title: string;
  description: string;
  completed: boolean;
  required: boolean;
}

interface AccessRequest {
  id: string;
  resourceName: string;
  licenseType: string;
  status: 'pending' | 'approved' | 'rejected';
  requestedAt: string;
}

interface DeveloperQuota {
  used: number;
  limit: number;
  resetDate: string;
}

/**
 * DASH-001: Dashboard Welcome Component
 * 
 * First-time user dashboard with onboarding checklist and status overview
 */
@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [
    CommonModule,
    NzLayoutModule,
    NzMenuModule,
    NzIconModule,
    NzCardModule,
    NzButtonModule,
    NzProgressModule,
    NzTagModule,
    NzEmptyModule,
    NzGridModule,
    NzTypographyModule,
    NzStatisticModule,
    NzBadgeModule,
    NzAvatarModule
  ],
  template: `
    <nz-layout class="dashboard-layout">
      <!-- Sidebar -->
      <nz-sider 
        nzCollapsible 
        [(nzCollapsed)]="isCollapsed" 
        [nzWidth]="250"
        class="dashboard-sidebar"
      >
        <div class="sidebar-logo">
          <img src="/assets/images/itqan-logo.png" alt="Itqan CMS" class="logo" />
          <span *ngIf="!isCollapsed" class="logo-text">Itqan CMS</span>
        </div>
        
        <ul nz-menu nzMode="inline" [nzInlineCollapsed]="isCollapsed" class="sidebar-menu">
          <li nz-menu-item nzSelected>
            <nz-icon nzType="dashboard"></nz-icon>
            <span>Dashboard</span>
          </li>
          <li nz-menu-item>
            <nz-icon nzType="file-text"></nz-icon>
            <span>Content</span>
          </li>
          <li nz-menu-item>
            <nz-icon nzType="api"></nz-icon>
            <span>API Keys</span>
          </li>
          <li nz-menu-item>
            <nz-icon nzType="setting"></nz-icon>
            <span>Settings</span>
          </li>
        </ul>
      </nz-sider>

      <!-- Main Layout -->
      <nz-layout class="main-layout">
        <!-- Header -->
        <nz-header class="dashboard-header">
          <div class="header-content">
            <div class="header-left">
              <nz-icon 
                [nzType]="isCollapsed ? 'menu-unfold' : 'menu-fold'" 
                (click)="isCollapsed = !isCollapsed"
                class="sidebar-trigger"
              ></nz-icon>
              <h1 class="page-title">Welcome to Itqan CMS</h1>
            </div>
            
            <div class="header-right">
              <nz-badge [nzCount]="pendingAccessRequests().length" nzSize="small">
                <nz-icon nzType="bell" class="notification-icon"></nz-icon>
              </nz-badge>
              
              <div class="user-profile" (click)="showUserMenu()">
                <nz-avatar [nzText]="getUserInitials()" nzSize="small"></nz-avatar>
                <span class="user-name">{{ getUserDisplayName() }}</span>
              </div>
            </div>
          </div>
        </nz-header>

        <!-- Content -->
        <nz-content class="dashboard-content">
          <div class="content-wrapper">
            
      <!-- Welcome Section -->
            <div class="welcome-section">
              <h2 class="welcome-title">
                Welcome back, {{ getUserDisplayName() }}!
              </h2>
              <p class="welcome-description">
                Get started with Itqan CMS by completing your profile and exploring our verified Quranic content.
              </p>
            </div>

            <!-- Profile Completion Card -->
            <nz-card 
              *ngIf="showProfileCompletion()" 
              nzTitle="Complete Your Profile" 
              class="profile-completion-card"
              [nzExtra]="profileCompletionExtra"
            >
              <div class="completion-progress">
                <nz-progress 
                  [nzPercent]="getProfileCompletionPercentage()" 
                  nzStatus="active"
                  [nzStrokeColor]="'#669B80'"
                ></nz-progress>
                <p class="completion-text">
                  {{ getCompletedItems() }} of {{ getTotalItems() }} steps completed
            </p>
          </div>

              <div class="checklist-items">
                <div 
                  *ngFor="let item of profileChecklist()" 
                  class="checklist-item"
                  [class.completed]="item.completed"
                  [class.required]="item.required"
                >
                  <nz-icon 
                    [nzType]="item.completed ? 'check-circle' : 'clock-circle'" 
                    [class.completed-icon]="item.completed"
                    [class.pending-icon]="!item.completed"
                  ></nz-icon>
                  
                  <div class="item-content">
                    <h4 class="item-title">{{ item.title }}</h4>
                    <p class="item-description">{{ item.description }}</p>
                  </div>
                  
                  <nz-tag 
                    *ngIf="item.required" 
                    nzColor="orange"
                    class="required-tag"
                  >
                    Required
                  </nz-tag>
          </div>
        </div>

              <ng-template #profileCompletionExtra>
                <button 
                  nz-button 
                  nzType="primary" 
                  (click)="completeProfile()"
                  class="complete-button"
                >
                  Complete Profile
                </button>
              </ng-template>
      </nz-card>

            <!-- Main Dashboard Grid -->
            <div nz-row [nzGutter]="[24, 24]" class="dashboard-grid">
              
              <!-- Access Requests Card -->
              <div nz-col nzXs="24" nzMd="12" nzLg="8">
                <nz-card nzTitle="Access Requests" class="requests-card">
                  <div *ngIf="pendingAccessRequests().length > 0; else noRequests">
                    <div 
                      *ngFor="let request of pendingAccessRequests()" 
                      class="request-item"
                    >
                      <div class="request-info">
                        <h4 class="request-resource">{{ request.resourceName }}</h4>
                        <p class="request-license">{{ request.licenseType }} License</p>
                        <span class="request-date">{{ formatDate(request.requestedAt) }}</span>
                      </div>
                      <nz-tag 
                        [nzColor]="getStatusColor(request.status)"
                        class="request-status"
                      >
                        {{ request.status | titlecase }}
                      </nz-tag>
        </div>

                    <button 
                      nz-button 
                      nzType="link" 
                      class="view-all-button"
                      (click)="viewAllRequests()"
                    >
                      View All Requests
                    </button>
        </div>

                  <ng-template #noRequests>
                    <nz-empty 
                      nzNotFoundImage="simple"
                      nzNotFoundContent="No access requests yet"
                      class="empty-requests"
                    >
                      <button 
                        nz-button 
                        nzType="primary" 
                        (click)="browseContent()"
                        nz-empty-footer
                      >
                        Browse Content
                      </button>
                    </nz-empty>
                  </ng-template>
          </nz-card>
        </div>

              <!-- Developer Quota Card -->
              <div nz-col nzXs="24" nzMd="12" nzLg="8">
                <nz-card nzTitle="API Usage" class="quota-card">
                  <div class="quota-stats">
                    <nz-statistic 
                      nzTitle="Requests Used" 
                      [nzValue]="developerQuota().used"
                      [nzValueStyle]="{ color: '#669B80' }"
                    ></nz-statistic>
                    
            <nz-statistic
                      nzTitle="Monthly Limit" 
                      [nzValue]="developerQuota().limit"
                      [nzValueStyle]="{ color: '#999' }"
                    ></nz-statistic>
        </div>
                  
                  <div class="quota-progress">
                    <nz-progress 
                      [nzPercent]="getQuotaPercentage()" 
                      [nzStrokeColor]="getQuotaColor()"
                      nzSize="small"
                    ></nz-progress>
                    <p class="quota-reset">
                      Resets on {{ formatDate(developerQuota().resetDate) }}
                    </p>
      </div>

                  <button 
                    nz-button 
                    nzType="default" 
                    class="view-api-button"
                    (click)="manageApiKeys()"
                  >
                    Manage API Keys
            </button>
                </nz-card>
              </div>

              <!-- Quick Actions Card -->
              <div nz-col nzXs="24" nzMd="24" nzLg="8">
                <nz-card nzTitle="Quick Actions" class="actions-card">
                  <div class="action-buttons">
                    <button 
                      nz-button 
                      nzType="primary" 
                      nzSize="large"
                      class="action-button primary-action"
                      (click)="createFirstArticle()"
                    >
                      <nz-icon nzType="plus"></nz-icon>
                      Create First Article
            </button>
                    
                    <button 
                      nz-button 
                      nzType="default" 
                      nzSize="large"
                      class="action-button"
                      (click)="browseContent()"
                    >
                      <nz-icon nzType="search"></nz-icon>
                      Browse Content
          </button>

                    <button 
                      nz-button 
                      nzType="default" 
                      nzSize="large"
                      class="action-button"
                      (click)="viewDocumentation()"
                    >
                      <nz-icon nzType="book"></nz-icon>
                      API Documentation
            </button>
                  </div>
                </nz-card>
                </div>

            </div>

          </div>
        </nz-content>
      </nz-layout>
    </nz-layout>
  `,
  styles: [`
    .dashboard-layout {
      min-height: 100vh;
    }

    /* Sidebar Styles */
    .dashboard-sidebar {
      background: #fff;
      border-right: 1px solid #f0f0f0;
    }

    .sidebar-logo {
      height: 64px;
      padding: 16px;
      display: flex;
      align-items: center;
      gap: 12px;
      border-bottom: 1px solid #f0f0f0;
    }

    .logo {
      height: 32px;
      width: auto;
    }

    .logo-text {
      font-weight: 600;
      font-size: 16px;
      color: #22433D;
    }

    .sidebar-menu {
      height: calc(100vh - 64px);
      border-right: 0;
    }

    /* Header Styles */
    .dashboard-header {
      background: #fff;
      padding: 0 24px;
      border-bottom: 1px solid #f0f0f0;
    }

    .header-content {
        display: flex;
        justify-content: space-between;
        align-items: center;
      height: 100%;
    }

    .header-left {
      display: flex;
      align-items: center;
      gap: 16px;
    }

    .sidebar-trigger {
      font-size: 18px;
      cursor: pointer;
      transition: color 0.3s;
      color: #666;
    }

    .sidebar-trigger:hover {
      color: #669B80;
    }

    .page-title {
      margin: 0;
      font-size: 20px;
      font-weight: 600;
          color: #22433D;
    }

    .header-right {
      display: flex;
      align-items: center;
      gap: 16px;
    }

    .notification-icon {
      font-size: 18px;
      color: #666;
      cursor: pointer;
      transition: color 0.3s;
    }

    .notification-icon:hover {
      color: #669B80;
    }

    .user-profile {
      display: flex;
      align-items: center;
      gap: 8px;
      cursor: pointer;
      padding: 8px;
      border-radius: 6px;
      transition: background-color 0.3s;
    }

    .user-profile:hover {
      background-color: #f5f5f5;
    }

    .user-name {
      font-weight: 500;
      color: #333;
    }

    /* Content Styles */
    .dashboard-content {
      padding: 24px;
      background: #f5f5f5;
      min-height: calc(100vh - 64px);
    }

    .content-wrapper {
      max-width: 1200px;
      margin: 0 auto;
    }

    /* Welcome Section */
    .welcome-section {
      margin-bottom: 24px;
    }

    .welcome-title {
      font-size: 28px;
        font-weight: 600;
        color: #22433D;
      margin: 0 0 8px 0;
    }

    .welcome-description {
      font-size: 16px;
      color: #666;
      margin: 0;
    }

    /* Profile Completion Card */
    .profile-completion-card {
      margin-bottom: 24px;
      border: 1px solid #669B80;
    }

    .completion-progress {
      margin-bottom: 24px;
    }

    .completion-text {
      margin: 8px 0 0 0;
      color: #666;
      font-size: 14px;
    }

    .checklist-items {
      display: flex;
      flex-direction: column;
      gap: 16px;
    }

    .checklist-item {
          display: flex;
          align-items: flex-start;
          gap: 12px;
      padding: 12px;
      border-radius: 8px;
      background: #f9f9f9;
      transition: all 0.3s;
    }

    .checklist-item.completed {
      background: #f6ffed;
      border: 1px solid #b7eb8f;
    }

    .completed-icon {
      color: #52c41a;
    }

    .pending-icon {
      color: #faad14;
    }

    .item-content {
      flex: 1;
    }

    .item-title {
      margin: 0 0 4px 0;
      font-size: 14px;
      font-weight: 600;
      color: #333;
    }

    .item-description {
      margin: 0;
      font-size: 13px;
      color: #666;
    }

    .required-tag {
      align-self: flex-start;
    }

    .complete-button {
      background-color: #669B80;
      border-color: #669B80;
    }

    .complete-button:hover {
      background-color: #5a8571;
      border-color: #5a8571;
    }

    /* Dashboard Grid */
    .dashboard-grid {
      margin-top: 0;
    }

    /* Card Styles */
    .requests-card,
    .quota-card,
    .actions-card {
      height: 100%;
    }

    /* Request Items */
    .request-item {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
          padding: 12px 0;
          border-bottom: 1px solid #f0f0f0;
    }
          
    .request-item:last-child {
            border-bottom: none;
          }
          
    .request-info {
      flex: 1;
    }

    .request-resource {
      margin: 0 0 4px 0;
      font-size: 14px;
      font-weight: 600;
      color: #333;
    }

    .request-license {
              margin: 0 0 4px 0;
      font-size: 13px;
      color: #666;
            }
            
    .request-date {
              font-size: 12px;
      color: #999;
    }

    .request-status {
      align-self: flex-start;
    }

    .view-all-button {
      padding: 0;
      margin-top: 8px;
    }

    .empty-requests {
      padding: 20px 0;
    }

    /* Quota Stats */
    .quota-stats {
      display: flex;
      justify-content: space-between;
      margin-bottom: 16px;
    }

    .quota-progress {
          margin-bottom: 16px;
        }

    .quota-reset {
      margin: 8px 0 0 0;
      font-size: 12px;
      color: #999;
    }

    .view-api-button {
      width: 100%;
    }

    /* Action Buttons */
    .action-buttons {
      display: flex;
      flex-direction: column;
      gap: 12px;
    }

    .action-button {
      width: 100%;
      height: 48px;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
    }

    .primary-action {
      background-color: #669B80;
      border-color: #669B80;
    }

    .primary-action:hover {
      background-color: #5a8571;
      border-color: #5a8571;
    }

    /* Responsive */
    @media (max-width: 768px) {
      .dashboard-content {
        padding: 16px;
      }

      .welcome-title {
        font-size: 24px;
      }

      .header-content {
        padding: 0 16px;
      }

      .page-title {
        font-size: 18px;
      }

      .user-name {
        display: none;
      }
    }

    /* NG-ZORRO Overrides */
    :host ::ng-deep .ant-layout-sider-collapsed .sidebar-logo .logo-text {
      display: none;
    }

    :host ::ng-deep .ant-card-head {
      border-bottom: 1px solid #669B80;
    }

    :host ::ng-deep .ant-card-head-title {
      color: #22433D;
      font-weight: 600;
    }

    :host ::ng-deep .ant-progress-bg {
      background-color: #669B80;
    }

    :host ::ng-deep .ant-statistic-title {
      color: #666;
      font-size: 12px;
    }

    :host ::ng-deep .ant-statistic-content {
      font-size: 20px;
      font-weight: 600;
    }
  `]
})
export class DashboardComponent implements OnInit {
  private authService = inject(AuthService);
  private stateService = inject(StateService);
  private router = inject(Router);

  isCollapsed = false;

  // Profile completion checklist
  profileChecklist = signal<ProfileChecklistItem[]>([
    {
      id: 'profile_info',
      title: 'Complete Basic Information',
      description: 'Add your name, organization, and contact details',
      completed: false,
      required: true
    },
    {
      id: 'verify_email',
      title: 'Verify Email Address',
      description: 'Confirm your email to receive important notifications',
      completed: true, // This should be true if user is logged in
      required: true
    },
    {
      id: 'api_key',
      title: 'Generate API Key',
      description: 'Create your first API key to access our services',
      completed: false,
      required: false
    },
    {
      id: 'first_request',
      title: 'Submit Access Request',
      description: 'Request access to your first Quranic resource',
      completed: false,
      required: false
    }
  ]);

  // Mock data - in real app, these would come from backend APIs
  pendingAccessRequests = signal<AccessRequest[]>([]);
  
  developerQuota = signal<DeveloperQuota>({
    used: 0,
    limit: 1000,
    resetDate: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString() // 30 days from now
  });

  ngOnInit(): void {
    this.loadDashboardData();
  }

  private async loadDashboardData(): Promise<void> {
    try {
      // TODO: Load real data from backend APIs
      // - User profile completion status
      // - Pending access requests
      // - Developer quota information
      
      // For now, simulate some data based on user state
      const isAuthenticated = await this.authService.isAuthenticated();
      if (isAuthenticated) {
        // Update profile completion based on available user data
        this.updateProfileCompletion();
      }
    } catch (error) {
      console.error('Failed to load dashboard data:', error);
    }
  }

  private updateProfileCompletion(): void {
    // TODO: Update based on actual user profile data from backend
    const items = this.profileChecklist();
    
    // Mark email as verified if user is authenticated
    const emailItem = items.find(item => item.id === 'verify_email');
    if (emailItem) {
      emailItem.completed = true;
    }

    this.profileChecklist.set([...items]);
  }

  showProfileCompletion(): boolean {
    return this.getProfileCompletionPercentage() < 100;
  }

  getProfileCompletionPercentage(): number {
    const items = this.profileChecklist();
    const completed = items.filter(item => item.completed).length;
    return Math.round((completed / items.length) * 100);
  }

  getCompletedItems(): number {
    return this.profileChecklist().filter(item => item.completed).length;
  }

  getTotalItems(): number {
    return this.profileChecklist().length;
  }

  getQuotaPercentage(): number {
    const quota = this.developerQuota();
    return Math.round((quota.used / quota.limit) * 100);
  }

  getQuotaColor(): string {
    const percentage = this.getQuotaPercentage();
    if (percentage < 70) return '#669B80';
    if (percentage < 90) return '#faad14';
    return '#ff4d4f';
  }

  getStatusColor(status: string): string {
    switch (status) {
      case 'pending': return 'processing';
      case 'approved': return 'success';
      case 'rejected': return 'error';
      default: return 'default';
    }
  }

  getUserDisplayName(): string {
    return this.stateService.userDisplayName();
  }

  getUserFirstName(): string {
    const user = this.stateService.currentUser();
    return user?.first_name || user?.email?.split('@')[0] || 'User';
  }

  getUserInitials(): string {
    const user = this.stateService.currentUser();
    if (!user) return 'U';
    
    const firstName = user.first_name || '';
    const lastName = user.last_name || '';
    
    if (firstName && lastName) {
      return `${firstName.charAt(0)}${lastName.charAt(0)}`.toUpperCase();
    } else if (firstName) {
      return firstName.charAt(0).toUpperCase();
    } else if (user.email) {
      return user.email.charAt(0).toUpperCase();
    }
    
    return 'U';
  }

  formatDate(dateString: string): string {
    return new Date(dateString).toLocaleDateString();
  }

  // Action Methods
  completeProfile(): void {
    this.router.navigate(['/profile']);
  }

  createFirstArticle(): void {
    this.router.navigate(['/admin/content/create']);
  }

  browseContent(): void {
    this.router.navigate(['/content']);
  }

  viewDocumentation(): void {
    window.open('/api/docs', '_blank');
  }

  manageApiKeys(): void {
    this.router.navigate(['/admin/api-keys']);
  }

  viewAllRequests(): void {
    this.router.navigate(['/access-requests']);
  }

  showUserMenu(): void {
    // TODO: Implement user menu dropdown
    console.log('Show user menu');
  }
}