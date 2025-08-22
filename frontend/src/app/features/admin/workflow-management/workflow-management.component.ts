import { Component, OnInit, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { FormsModule } from '@angular/forms';
import { NzLayoutModule } from 'ng-zorro-antd/layout';
import { NzBreadCrumbModule } from 'ng-zorro-antd/breadcrumb';
import { NzButtonModule } from 'ng-zorro-antd/button';
import { NzCardModule } from 'ng-zorro-antd/card';
import { NzGridModule } from 'ng-zorro-antd/grid';
import { NzIconModule } from 'ng-zorro-antd/icon';
import { NzTableModule } from 'ng-zorro-antd/table';
import { NzTagModule } from 'ng-zorro-antd/tag';
import { NzStatisticModule } from 'ng-zorro-antd/statistic';
import { NzTimelineModule } from 'ng-zorro-antd/timeline';
import { NzSpinModule } from 'ng-zorro-antd/spin';
import { NzMessageModule, NzMessageService } from 'ng-zorro-antd/message';
import { NzModalModule, NzModalService } from 'ng-zorro-antd/modal';
import { NzTabsModule } from 'ng-zorro-antd/tabs';
import { NzSelectModule } from 'ng-zorro-antd/select';
import { NzInputModule } from 'ng-zorro-antd/input';
import { NzFormModule } from 'ng-zorro-antd/form';
import { NzTypographyModule } from 'ng-zorro-antd/typography';
import { NzDescriptionsModule } from 'ng-zorro-antd/descriptions';
import { NzDividerModule } from 'ng-zorro-antd/divider';
import { NzBadgeModule } from 'ng-zorro-antd/badge';
import { NzToolTipModule } from 'ng-zorro-antd/tooltip';
import { NzEmptyModule } from 'ng-zorro-antd/empty';
import { NzAlertModule } from 'ng-zorro-antd/alert';

import { environment } from '../../../../environments/environment';

/**
 * ADMIN-004: Workflow Management Component
 * 
 * Implements comprehensive workflow management interface for Islamic content review
 * following the ADMIN-004 wireframe design with NG-ZORRO components
 */

interface WorkflowStats {
  stats: {
    draft: number;
    in_review: number;
    reviewed: number;
    published: number;
    rejected: number;
  };
  user_role: string;
  permissions: {
    can_review: boolean;
    can_publish: boolean;
    can_create: boolean;
  };
}

interface Resource {
  id: string;
  title: string;
  title_en: string;
  title_ar: string;
  description: string;
  resource_type: string;
  language: string;
  workflow_status: string;
  publisher: string;
  publisher_name: string;
  reviewed_by?: string;
  reviewed_at?: string;
  review_notes?: string;
  submitted_for_review_at?: string;
  published_at?: string;
  created_at: string;
  updated_at: string;
}

interface WorkflowHistory {
  history: {
    status: string;
    timestamp: string;
    user: string;
    user_email: string;
    notes: string;
  }[];
}

@Component({
  selector: 'app-workflow-management',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    NzLayoutModule,
    NzBreadCrumbModule,
    NzButtonModule,
    NzCardModule,
    NzGridModule,
    NzIconModule,
    NzTableModule,
    NzTagModule,
    NzStatisticModule,
    NzTimelineModule,
    NzSpinModule,
    NzMessageModule,
    NzModalModule,
    NzTabsModule,
    NzSelectModule,
    NzInputModule,
    NzFormModule,
    NzTypographyModule,
    NzDescriptionsModule,
    NzDividerModule,
    NzBadgeModule,
    NzToolTipModule,
    NzEmptyModule,
    NzAlertModule
  ],
  template: `
    <nz-layout class="workflow-management">
      <!-- Header -->
      <nz-header class="workflow-header">
        <nz-breadcrumb>
          <nz-breadcrumb-item>
            <span nz-icon nzType="home"></span>
            Admin
          </nz-breadcrumb-item>
          <nz-breadcrumb-item>
            <span nz-icon nzType="flow-chart"></span>
            Workflow Management
          </nz-breadcrumb-item>
        </nz-breadcrumb>

        <div class="header-actions">
          <button nz-button nzType="primary" (click)="refreshData()">
            <span nz-icon nzType="reload"></span>
            Refresh
          </button>
          @if (workflowStats()?.permissions?.can_create) {
            <button nz-button nzType="default" routerLink="/admin/content/create">
              <span nz-icon nzType="plus"></span>
              Create Content
            </button>
          }
        </div>
      </nz-header>

      <nz-content class="workflow-content">
        <!-- Workflow Statistics -->
        <nz-card nzTitle="Workflow Overview" class="stats-card">
          @if (isLoadingStats()) {
            <nz-spin nzSimple></nz-spin>
          } @else if (workflowStats()) {
            <div nz-row [nzGutter]="[24, 24]">
              <div nz-col [nzSpan]="4">
                <nz-statistic 
                  nzTitle="Draft" 
                  [nzValue]="workflowStats()!.stats.draft"
                  [nzValueStyle]="{ color: '#8c8c8c' }"
                  nzPrefix="📝">
                </nz-statistic>
              </div>
              <div nz-col [nzSpan]="4">
                <nz-statistic 
                  nzTitle="In Review" 
                  [nzValue]="workflowStats()!.stats.in_review"
                  [nzValueStyle]="{ color: '#1890ff' }"
                  nzPrefix="👁️">
                </nz-statistic>
              </div>
              <div nz-col [nzSpan]="4">
                <nz-statistic 
                  nzTitle="Reviewed" 
                  [nzValue]="workflowStats()!.stats.reviewed"
                  [nzValueStyle]="{ color: '#52c41a' }"
                  nzPrefix="✅">
                </nz-statistic>
              </div>
              <div nz-col [nzSpan]="4">
                <nz-statistic 
                  nzTitle="Published" 
                  [nzValue]="workflowStats()!.stats.published"
                  [nzValueStyle]="{ color: '#669B80' }"
                  nzPrefix="🚀">
                </nz-statistic>
              </div>
              <div nz-col [nzSpan]="4">
                <nz-statistic 
                  nzTitle="Rejected" 
                  [nzValue]="workflowStats()!.stats.rejected"
                  [nzValueStyle]="{ color: '#ff4d4f' }"
                  nzPrefix="❌">
                </nz-statistic>
              </div>
              <div nz-col [nzSpan]="4">
                <div class="user-role">
                  <h4>Your Role</h4>
                  <nz-tag [nzColor]="getUserRoleColor()">
                    {{ workflowStats()?.user_role | titlecase }}
                  </nz-tag>
                </div>
              </div>
            </div>
          }
        </nz-card>

        <!-- Workflow Tabs -->
        <nz-card class="workflow-tabs-card">
          <nz-tabs [(nzSelectedIndex)]="selectedTabIndex()" (nzSelectedIndexChange)="onTabChange($event)">
            <!-- All Resources Tab -->
            <nz-tab-pane nzTab="All Resources">
              <div class="tab-content">
                @if (isLoadingResources()) {
                  <nz-spin nzSimple></nz-spin>
                } @else {
                  <nz-table 
                    #resourcesTable 
                    [nzData]="allResources()" 
                    [nzPageSize]="20"
                    nzSize="middle"
                    [nzLoading]="isLoadingResources()">
                    <thead>
                      <tr>
                        <th>Title</th>
                        <th>Type</th>
                        <th>Language</th>
                        <th>Status</th>
                        <th>Publisher</th>
                        <th>Last Updated</th>
                        <th>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      @for (resource of allResources(); track resource.id) {
                        <tr>
                          <td>
                            <div class="resource-title">
                              <strong>{{ resource.title_en }}</strong>
                              @if (resource.title_ar) {
                                <div class="arabic-title">{{ resource.title_ar }}</div>
                              }
                            </div>
                          </td>
                          <td>
                            <nz-tag>{{ resource.resource_type | titlecase }}</nz-tag>
                          </td>
                          <td>{{ getLanguageDisplay(resource.language) }}</td>
                          <td>
                            <nz-tag [nzColor]="getStatusColor(resource.workflow_status)">
                              {{ getStatusDisplay(resource.workflow_status) }}
                            </nz-tag>
                          </td>
                          <td>{{ resource.publisher_name }}</td>
                          <td>{{ resource.updated_at | date:'short' }}</td>
                          <td>
                            <div class="action-buttons">
                              <button 
                                nz-button 
                                nzType="text" 
                                nzSize="small"
                                (click)="viewResource(resource)"
                                nz-tooltip
                                nzTooltipTitle="View Details">
                                <span nz-icon nzType="eye"></span>
                              </button>
                              <button 
                                nz-button 
                                nzType="text" 
                                nzSize="small"
                                (click)="viewWorkflowHistory(resource)"
                                nz-tooltip
                                nzTooltipTitle="View History">
                                <span nz-icon nzType="history"></span>
                              </button>
                              @if (canReviewResource(resource)) {
                                <button 
                                  nz-button 
                                  nzType="text" 
                                  nzSize="small"
                                  (click)="reviewResource(resource)"
                                  nz-tooltip
                                  nzTooltipTitle="Review">
                                  <span nz-icon nzType="check-circle"></span>
                                </button>
                              }
                              @if (canPublishResource(resource)) {
                                <button 
                                  nz-button 
                                  nzType="text" 
                                  nzSize="small"
                                  (click)="publishResource(resource)"
                                  nz-tooltip
                                  nzTooltipTitle="Publish">
                                  <span nz-icon nzType="rocket"></span>
                                </button>
                              }
                            </div>
                          </td>
                        </tr>
                      }
                    </tbody>
                  </nz-table>
                }
              </div>
            </nz-tab-pane>

            <!-- Review Queue Tab -->
            @if (workflowStats()?.permissions?.can_review) {
              <nz-tab-pane>
                <ng-container *nzTabPaneTitle>
                  Review Queue
                  @if (workflowStats()?.stats?.in_review) {
                    <nz-badge [nzCount]="workflowStats()!.stats.in_review" [nzOffset]="[10, 0]"></nz-badge>
                  }
                </ng-container>
                
                <div class="tab-content">
                  @if (isLoadingReviewQueue()) {
                    <nz-spin nzSimple></nz-spin>
                  } @else if (reviewQueue().length === 0) {
                    <nz-empty nzNotFoundContent="No resources pending review">
                      <div nz-empty-footer>
                        <p>All resources have been reviewed!</p>
                      </div>
                    </nz-empty>
                  } @else {
                    <nz-table 
                      #reviewTable 
                      [nzData]="reviewQueue()" 
                      [nzPageSize]="10"
                      nzSize="middle">
                      <thead>
                        <tr>
                          <th>Title</th>
                          <th>Type</th>
                          <th>Publisher</th>
                          <th>Submitted</th>
                          <th>Actions</th>
                        </tr>
                      </thead>
                      <tbody>
                        @for (resource of reviewQueue(); track resource.id) {
                          <tr>
                            <td>
                              <div class="resource-title">
                                <strong>{{ resource.title_en }}</strong>
                                @if (resource.title_ar) {
                                  <div class="arabic-title">{{ resource.title_ar }}</div>
                                }
                              </div>
                            </td>
                            <td>
                              <nz-tag>{{ resource.resource_type | titlecase }}</nz-tag>
                            </td>
                            <td>{{ resource.publisher_name }}</td>
                            <td>{{ resource.submitted_for_review_at | date:'short' }}</td>
                            <td>
                              <div class="review-actions">
                                <button 
                                  nz-button 
                                  nzType="primary"
                                  nzSize="small"
                                  (click)="approveResource(resource)">
                                  <span nz-icon nzType="check"></span>
                                  Approve
                                </button>
                                <button 
                                  nz-button 
                                  nzDanger
                                  nzSize="small"
                                  (click)="rejectResource(resource)">
                                  <span nz-icon nzType="close"></span>
                                  Reject
                                </button>
                              </div>
                            </td>
                          </tr>
                        }
                      </tbody>
                    </nz-table>
                  }
                </div>
              </nz-tab-pane>
            }

            <!-- My Content Tab -->
            <nz-tab-pane nzTab="My Content">
              <div class="tab-content">
                @if (isLoadingMyContent()) {
                  <nz-spin nzSimple></nz-spin>
                } @else {
                  <nz-table 
                    #myContentTable 
                    [nzData]="myContent()" 
                    [nzPageSize]="15"
                    nzSize="middle">
                    <thead>
                      <tr>
                        <th>Title</th>
                        <th>Type</th>
                        <th>Status</th>
                        <th>Last Updated</th>
                        <th>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      @for (resource of myContent(); track resource.id) {
                        <tr>
                          <td>
                            <div class="resource-title">
                              <strong>{{ resource.title_en }}</strong>
                              @if (resource.title_ar) {
                                <div class="arabic-title">{{ resource.title_ar }}</div>
                              }
                            </div>
                          </td>
                          <td>
                            <nz-tag>{{ resource.resource_type | titlecase }}</nz-tag>
                          </td>
                          <td>
                            <nz-tag [nzColor]="getStatusColor(resource.workflow_status)">
                              {{ getStatusDisplay(resource.workflow_status) }}
                            </nz-tag>
                          </td>
                          <td>{{ resource.updated_at | date:'short' }}</td>
                          <td>
                            <div class="action-buttons">
                              @if (resource.workflow_status === 'draft') {
                                <button 
                                  nz-button 
                                  nzType="primary"
                                  nzSize="small"
                                  (click)="submitForReview(resource)">
                                  <span nz-icon nzType="send"></span>
                                  Submit for Review
                                </button>
                              }
                              @if (resource.workflow_status === 'rejected') {
                                <button 
                                  nz-button 
                                  nzType="default"
                                  nzSize="small"
                                  (click)="resetToDraft(resource)">
                                  <span nz-icon nzType="edit"></span>
                                  Reset to Draft
                                </button>
                              }
                              <button 
                                nz-button 
                                nzType="text" 
                                nzSize="small"
                                (click)="viewWorkflowHistory(resource)">
                                <span nz-icon nzType="history"></span>
                                History
                              </button>
                            </div>
                          </td>
                        </tr>
                      }
                    </tbody>
                  </nz-table>
                }
              </div>
            </nz-tab-pane>
          </nz-tabs>
        </nz-card>
      </nz-content>
    </nz-layout>

    <!-- Resource Detail Modal -->
    <nz-modal
      [(nzVisible)]="isResourceModalVisible"
      nzTitle="Resource Details"
      [nzFooter]="null"
      [nzWidth]="800"
      (nzOnCancel)="closeResourceModal()">
      
      <div *nzModalContent>
        @if (selectedResource()) {
          <nz-descriptions nzBordered [nzColumn]="2">
            <nz-descriptions-item nzTitle="English Title" [nzSpan]="2">
              {{ selectedResource()?.title_en }}
            </nz-descriptions-item>
            <nz-descriptions-item nzTitle="Arabic Title" [nzSpan]="2">
              {{ selectedResource()?.title_ar }}
            </nz-descriptions-item>
            <nz-descriptions-item nzTitle="Resource Type">
              {{ selectedResource()?.resource_type | titlecase }}
            </nz-descriptions-item>
            <nz-descriptions-item nzTitle="Language">
              {{ getLanguageDisplay(selectedResource()?.language) }}
            </nz-descriptions-item>
            <nz-descriptions-item nzTitle="Current Status">
              <nz-tag [nzColor]="getStatusColor(selectedResource()?.workflow_status)">
                {{ getStatusDisplay(selectedResource()?.workflow_status) }}
              </nz-tag>
            </nz-descriptions-item>
            <nz-descriptions-item nzTitle="Publisher">
              {{ selectedResource()?.publisher_name }}
            </nz-descriptions-item>
            @if (selectedResource()?.review_notes) {
              <nz-descriptions-item nzTitle="Review Notes" [nzSpan]="2">
                {{ selectedResource()?.review_notes }}
              </nz-descriptions-item>
            }
            <nz-descriptions-item nzTitle="Created">
              {{ selectedResource()?.created_at | date:'full' }}
            </nz-descriptions-item>
            <nz-descriptions-item nzTitle="Last Updated">
              {{ selectedResource()?.updated_at | date:'full' }}
            </nz-descriptions-item>
          </nz-descriptions>
        }
      </div>
    </nz-modal>

    <!-- Workflow History Modal -->
    <nz-modal
      [(nzVisible)]="isHistoryModalVisible"
      nzTitle="Workflow History"
      [nzFooter]="null"
      [nzWidth]="700"
      (nzOnCancel)="closeHistoryModal()">
      
      <div *nzModalContent>
        @if (isLoadingHistory()) {
          <nz-spin nzSimple></nz-spin>
        } @else if (workflowHistory()?.history) {
          <nz-timeline>
            @for (entry of workflowHistory()!.history; track $index) {
              <nz-timeline-item [nzColor]="getStatusColor(entry.status)">
                <div class="timeline-content">
                  <div class="timeline-header">
                    <strong>{{ getStatusDisplay(entry.status) }}</strong>
                    <span class="timeline-time">{{ entry.timestamp | date:'short' }}</span>
                  </div>
                  <div class="timeline-user">by {{ entry.user }}</div>
                  @if (entry.notes) {
                    <div class="timeline-notes">{{ entry.notes }}</div>
                  }
                </div>
              </nz-timeline-item>
            }
          </nz-timeline>
        }
      </div>
    </nz-modal>

    <!-- Review Action Modal -->
    <nz-modal
      [(nzVisible)]="isReviewModalVisible"
      [nzTitle]="reviewAction() === 'approve' ? 'Approve Resource' : 'Reject Resource'"
      [nzOkText]="reviewAction() === 'approve' ? 'Approve' : 'Reject'"
      [nzOkType]="reviewAction() === 'approve' ? 'primary' : 'danger'"
      [nzCancelText]="'Cancel'"
      (nzOnOk)="confirmReviewAction()"
      (nzOnCancel)="closeReviewModal()">
      
      <div *nzModalContent>
        <form nz-form [nzLayout]="'vertical'">
          <nz-form-item>
            <nz-form-label [nzRequired]="reviewAction() === 'reject'">
              {{ reviewAction() === 'approve' ? 'Review Notes (Optional)' : 'Rejection Reason (Required)' }}
            </nz-form-label>
            <nz-form-control>
              <textarea 
                nz-input 
                rows="4" 
                [(ngModel)]="reviewNotes"
                name="reviewNotes"
                [placeholder]="reviewAction() === 'approve' ? 'Add any notes about the approval...' : 'Please explain why this resource is being rejected...'">
              </textarea>
            </nz-form-control>
          </nz-form-item>
        </form>
      </div>
    </nz-modal>
  `,
  styleUrls: ['./workflow-management.component.scss']
})
export class WorkflowManagementComponent implements OnInit {
  private readonly http = inject(HttpClient);
  private readonly message = inject(NzMessageService);
  private readonly modal = inject(NzModalService);

  // Reactive state
  workflowStats = signal<WorkflowStats | null>(null);
  allResources = signal<Resource[]>([]);
  reviewQueue = signal<Resource[]>([]);
  myContent = signal<Resource[]>([]);
  selectedResource = signal<Resource | null>(null);
  workflowHistory = signal<WorkflowHistory | null>(null);
  
  // Loading states
  isLoadingStats = signal(false);
  isLoadingResources = signal(false);
  isLoadingReviewQueue = signal(false);
  isLoadingMyContent = signal(false);
  isLoadingHistory = signal(false);
  
  // UI state
  selectedTabIndex = signal(0);
  isResourceModalVisible = false;
  isHistoryModalVisible = false;
  isReviewModalVisible = false;
  reviewAction = signal<'approve' | 'reject'>('approve');
  reviewNotes = '';
  resourceToReview: Resource | null = null;

  ngOnInit(): void {
    this.loadWorkflowStats();
    this.loadAllResources();
  }

  loadWorkflowStats(): void {
    this.isLoadingStats.set(true);
    this.http.get<WorkflowStats>(`${environment.apiUrl}/workflow/dashboard/`)
      .subscribe({
        next: (stats) => {
          this.workflowStats.set(stats);
          this.isLoadingStats.set(false);
        },
        error: (error) => {
          console.error('Error loading workflow stats:', error);
          this.message.error('Failed to load workflow statistics');
          this.isLoadingStats.set(false);
        }
      });
  }

  loadAllResources(): void {
    this.isLoadingResources.set(true);
    this.http.get<{results: Resource[]}>(`${environment.apiUrl}/resources/`)
      .subscribe({
        next: (response) => {
          this.allResources.set(response.results);
          this.isLoadingResources.set(false);
        },
        error: (error) => {
          console.error('Error loading resources:', error);
          this.message.error('Failed to load resources');
          this.isLoadingResources.set(false);
        }
      });
  }

  loadReviewQueue(): void {
    this.isLoadingReviewQueue.set(true);
    this.http.get<{results: Resource[]}>(`${environment.apiUrl}/workflow/by_status/?status=in_review`)
      .subscribe({
        next: (response) => {
          this.reviewQueue.set(response.results);
          this.isLoadingReviewQueue.set(false);
        },
        error: (error) => {
          console.error('Error loading review queue:', error);
          this.message.error('Failed to load review queue');
          this.isLoadingReviewQueue.set(false);
        }
      });
  }

  loadMyContent(): void {
    this.isLoadingMyContent.set(true);
    // This will load current user's resources
    this.http.get<{results: Resource[]}>(`${environment.apiUrl}/resources/?publisher=me`)
      .subscribe({
        next: (response) => {
          this.myContent.set(response.results);
          this.isLoadingMyContent.set(false);
        },
        error: (error) => {
          console.error('Error loading my content:', error);
          this.message.error('Failed to load my content');
          this.isLoadingMyContent.set(false);
        }
      });
  }

  onTabChange(index: number): void {
    this.selectedTabIndex.set(index);
    
    switch (index) {
      case 0:
        // All Resources - already loaded
        break;
      case 1:
        // Review Queue
        if (this.workflowStats()?.permissions?.can_review) {
          this.loadReviewQueue();
        }
        break;
      case 2:
        // My Content
        this.loadMyContent();
        break;
    }
  }

  refreshData(): void {
    this.loadWorkflowStats();
    this.loadAllResources();
    
    const currentTab = this.selectedTabIndex();
    if (currentTab === 1 && this.workflowStats()?.permissions?.can_review) {
      this.loadReviewQueue();
    } else if (currentTab === 2) {
      this.loadMyContent();
    }
  }

  // Resource actions
  viewResource(resource: Resource): void {
    this.selectedResource.set(resource);
    this.isResourceModalVisible = true;
  }

  closeResourceModal(): void {
    this.isResourceModalVisible = false;
    this.selectedResource.set(null);
  }

  viewWorkflowHistory(resource: Resource): void {
    this.selectedResource.set(resource);
    this.isHistoryModalVisible = true;
    this.loadWorkflowHistory(resource.id);
  }

  closeHistoryModal(): void {
    this.isHistoryModalVisible = false;
    this.selectedResource.set(null);
    this.workflowHistory.set(null);
  }

  loadWorkflowHistory(resourceId: string): void {
    this.isLoadingHistory.set(true);
    this.http.get<WorkflowHistory>(`${environment.apiUrl}/workflow/${resourceId}/history/`)
      .subscribe({
        next: (history) => {
          this.workflowHistory.set(history);
          this.isLoadingHistory.set(false);
        },
        error: (error) => {
          console.error('Error loading workflow history:', error);
          this.message.error('Failed to load workflow history');
          this.isLoadingHistory.set(false);
        }
      });
  }

  // Workflow actions
  submitForReview(resource: Resource): void {
    this.http.post(`${environment.apiUrl}/workflow/${resource.id}/submit_for_review/`, {})
      .subscribe({
        next: () => {
          this.message.success('Resource submitted for review');
          this.refreshData();
        },
        error: (error) => {
          console.error('Error submitting for review:', error);
          this.message.error('Failed to submit resource for review');
        }
      });
  }

  reviewResource(resource: Resource): void {
    this.resourceToReview = resource;
    this.reviewAction.set('approve');
    this.reviewNotes = '';
    this.isReviewModalVisible = true;
  }

  approveResource(resource: Resource): void {
    this.resourceToReview = resource;
    this.reviewAction.set('approve');
    this.reviewNotes = '';
    this.isReviewModalVisible = true;
  }

  rejectResource(resource: Resource): void {
    this.resourceToReview = resource;
    this.reviewAction.set('reject');
    this.reviewNotes = '';
    this.isReviewModalVisible = true;
  }

  closeReviewModal(): void {
    this.isReviewModalVisible = false;
    this.resourceToReview = null;
    this.reviewNotes = '';
  }

  confirmReviewAction(): void {
    if (!this.resourceToReview) return;
    
    if (this.reviewAction() === 'reject' && !this.reviewNotes.trim()) {
      this.message.error('Rejection reason is required');
      return;
    }

    const endpoint = this.reviewAction() === 'approve' ? 'approve' : 'reject';
    const payload = { notes: this.reviewNotes };

    this.http.post(`${environment.apiUrl}/workflow/${this.resourceToReview.id}/${endpoint}/`, payload)
      .subscribe({
        next: () => {
          const action = this.reviewAction() === 'approve' ? 'approved' : 'rejected';
          this.message.success(`Resource ${action} successfully`);
          this.closeReviewModal();
          this.refreshData();
        },
        error: (error) => {
          console.error(`Error ${this.reviewAction()}ing resource:`, error);
          this.message.error(`Failed to ${this.reviewAction()} resource`);
        }
      });
  }

  publishResource(resource: Resource): void {
    this.modal.confirm({
      nzTitle: 'Publish Resource',
      nzContent: `Are you sure you want to publish "${resource.title_en}"?`,
      nzOkText: 'Publish',
      nzOkType: 'primary',
      nzOnOk: () => {
        this.http.post(`${environment.apiUrl}/workflow/${resource.id}/publish/`, {})
          .subscribe({
            next: () => {
              this.message.success('Resource published successfully');
              this.refreshData();
            },
            error: (error) => {
              console.error('Error publishing resource:', error);
              this.message.error('Failed to publish resource');
            }
          });
      }
    });
  }

  resetToDraft(resource: Resource): void {
    this.modal.confirm({
      nzTitle: 'Reset to Draft',
      nzContent: `Are you sure you want to reset "${resource.title_en}" to draft status?`,
      nzOkText: 'Reset',
      nzOkType: 'default',
      nzOnOk: () => {
        this.http.post(`${environment.apiUrl}/workflow/${resource.id}/reset_to_draft/`, {})
          .subscribe({
            next: () => {
              this.message.success('Resource reset to draft');
              this.refreshData();
            },
            error: (error) => {
              console.error('Error resetting resource:', error);
              this.message.error('Failed to reset resource');
            }
          });
      }
    });
  }

  // Permission checks
  canReviewResource(resource: Resource): boolean {
    return (
      resource.workflow_status === 'in_review' &&
      this.workflowStats()?.permissions?.can_review === true
    );
  }

  canPublishResource(resource: Resource): boolean {
    return (
      resource.workflow_status === 'reviewed' &&
      this.workflowStats()?.permissions?.can_publish === true
    );
  }

  // Helper methods
  getUserRoleColor(): string {
    const role = this.workflowStats()?.user_role?.toLowerCase();
    const colorMap: { [key: string]: string } = {
      'admin': 'red',
      'reviewer': 'blue',
      'publisher': 'green',
      'developer': 'orange'
    };
    return colorMap[role || ''] || 'default';
  }

  getStatusColor(status: string): string {
    const colorMap: { [key: string]: string } = {
      'draft': 'default',
      'in_review': 'processing',
      'reviewed': 'success',
      'published': 'green',
      'rejected': 'error'
    };
    return colorMap[status] || 'default';
  }

  getStatusDisplay(status: string): string {
    const displayMap: { [key: string]: string } = {
      'draft': 'Draft',
      'in_review': 'In Review',
      'reviewed': 'Reviewed',
      'published': 'Published',
      'rejected': 'Rejected'
    };
    return displayMap[status] || status;
  }

  getLanguageDisplay(code: string): string {
    const languageMap: { [key: string]: string } = {
      'ar': 'Arabic',
      'en': 'English',
      'ur': 'Urdu',
      'tr': 'Turkish',
      'id': 'Indonesian',
      'ms': 'Malay'
    };
    return languageMap[code] || code.toUpperCase();
  }
}
