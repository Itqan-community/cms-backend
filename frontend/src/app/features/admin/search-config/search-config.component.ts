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
import { NzProgressModule } from 'ng-zorro-antd/progress';
import { NzSpinModule } from 'ng-zorro-antd/spin';
import { NzMessageModule, NzMessageService } from 'ng-zorro-antd/message';
import { NzModalModule, NzModalService } from 'ng-zorro-antd/modal';
import { NzFormModule } from 'ng-zorro-antd/form';
import { NzInputModule } from 'ng-zorro-antd/input';
import { NzInputNumberModule } from 'ng-zorro-antd/input-number';
import { NzSwitchModule } from 'ng-zorro-antd/switch';
import { NzSelectModule } from 'ng-zorro-antd/select';
import { NzDividerModule } from 'ng-zorro-antd/divider';
import { NzTypographyModule } from 'ng-zorro-antd/typography';
import { NzListModule } from 'ng-zorro-antd/list';
import { NzDescriptionsModule } from 'ng-zorro-antd/descriptions';
import { NzAlertModule } from 'ng-zorro-antd/alert';

import { environment } from '../../../../environments/environment';

/**
 * ADMIN-002: Search Configuration Component
 * 
 * Implements the MeiliSearch admin configuration interface
 * following the ADMIN-002 wireframe design with NG-ZORRO components
 */

interface SearchIndex {
  id: string;
  name: string;
  display_name: string;
  description: string;
  is_active: boolean;
  document_count: number;
  last_indexed: string | null;
  created_by: string;
  searchable_attributes: string[];
  filterable_attributes: string[];
  sortable_attributes: string[];
  ranking_rules: string[];
}

interface SearchConfiguration {
  id: string;
  default_limit: number;
  max_limit: number;
  suggestions_enabled: boolean;
  suggestion_min_chars: number;
  suggestion_limit: number;
  highlighting_enabled: boolean;
  highlight_pre_tag: string;
  highlight_post_tag: string;
  faceting_enabled: boolean;
  search_timeout: number;
  track_searches: boolean;
  updated_by: string;
  updated_at: string;
}

interface IndexStats {
  numberOfDocuments: number;
  isIndexing: boolean;
  fieldsDistribution: { [key: string]: number };
}

interface SearchStats {
  meilisearch_healthy: boolean;
  indexes: {
    name: string;
    stats: IndexStats | null;
    exists: boolean;
    config: any;
  }[];
  error?: string;
}

interface IndexingTask {
  id: string;
  task_id: string;
  task_type: string;
  status: string;
  index_name: string;
  total_documents: number;
  processed_documents: number;
  progress_percentage: number;
  error_message: string;
  started_by: string;
  created_at: string;
}

@Component({
  selector: 'app-search-config',
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
    NzProgressModule,
    NzSpinModule,
    NzMessageModule,
    NzModalModule,
    NzFormModule,
    NzInputModule,
    NzInputNumberModule,
    NzSwitchModule,
    NzSelectModule,
    NzDividerModule,
    NzTypographyModule,
    NzListModule,
    NzDescriptionsModule,
    NzAlertModule
  ],
  template: `
    <nz-layout class="search-config">
      <!-- Header -->
      <nz-header class="search-header">
        <nz-breadcrumb>
          <nz-breadcrumb-item>
            <span nz-icon nzType="home"></span>
            Admin
          </nz-breadcrumb-item>
          <nz-breadcrumb-item>
            <span nz-icon nzType="search"></span>
            Search Configuration
          </nz-breadcrumb-item>
        </nz-breadcrumb>

        <div class="header-actions">
          <button nz-button nzType="primary" (click)="checkHealth()">
            <span nz-icon nzType="heart"></span>
            Health Check
          </button>
          <button nz-button nzType="default" (click)="refreshStats()">
            <span nz-icon nzType="reload"></span>
            Refresh
          </button>
        </div>
      </nz-header>

      <nz-content class="search-content">
        <!-- Health Status Alert -->
        @if (searchStats()) {
          <nz-alert
            [nzType]="searchStats()?.meilisearch_healthy ? 'success' : 'error'"
            [nzMessage]="searchStats()?.meilisearch_healthy ? 'MeiliSearch is healthy and accessible' : 'MeiliSearch is not responding'"
            [nzShowIcon]="true"
            class="health-alert">
          </nz-alert>
        }

        @if (searchStats()?.error) {
          <nz-alert
            nzType="error"
            [nzMessage]="'Search service error: ' + searchStats()?.error"
            nzShowIcon
            class="error-alert">
          </nz-alert>
        }

        <!-- Overview Statistics -->
        <nz-card nzTitle="Search Overview" class="overview-card">
          @if (isLoadingStats()) {
            <nz-spin nzSimple></nz-spin>
          } @else {
            <div nz-row [nzGutter]="[24, 24]">
              <div nz-col [nzSpan]="6">
                <nz-statistic 
                  nzTitle="Total Indexes" 
                  [nzValue]="getTotalIndexes()"
                  [nzValueStyle]="{ color: '#669B80' }">
                </nz-statistic>
              </div>
              <div nz-col [nzSpan]="6">
                <nz-statistic 
                  nzTitle="Total Documents" 
                  [nzValue]="getTotalDocuments()"
                  [nzValueStyle]="{ color: '#1890ff' }">
                </nz-statistic>
              </div>
              <div nz-col [nzSpan]="6">
                <nz-statistic 
                  nzTitle="Active Indexes" 
                  [nzValue]="getActiveIndexes()"
                  [nzValueStyle]="{ color: '#52c41a' }">
                </nz-statistic>
              </div>
              <div nz-col [nzSpan]="6">
                <nz-statistic 
                  nzTitle="Search Status" 
                  [nzValue]="searchStats()?.meilisearch_healthy ? 'Healthy' : 'Error'"
                  [nzValueStyle]="{ color: searchStats()?.meilisearch_healthy ? '#52c41a' : '#ff4d4f' }">
                </nz-statistic>
              </div>
            </div>
          }
        </nz-card>

        <!-- Search Indexes Table -->
        <nz-card nzTitle="Search Indexes" class="indexes-card">
          <div class="card-actions" slot="extra">
            <button nz-button nzType="primary" (click)="showCreateIndexModal()">
              <span nz-icon nzType="plus"></span>
              Create Index
            </button>
          </div>

          @if (isLoadingStats()) {
            <nz-spin nzSimple></nz-spin>
          } @else {
            <nz-table 
              #indexesTable 
              [nzData]="getIndexesTableData()" 
              [nzPageSize]="10"
              [nzShowPagination]="false"
              nzSize="middle">
              <thead>
                <tr>
                  <th>Index Name</th>
                  <th>Status</th>
                  <th>Documents</th>
                  <th>Last Updated</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                @for (index of getIndexesTableData(); track index.name) {
                  <tr>
                    <td>
                      <div class="index-name">
                        <strong>{{ index.display_name || index.name }}</strong>
                        <div class="index-description">{{ index.name }}</div>
                      </div>
                    </td>
                    <td>
                      @if (index.exists) {
                        <nz-tag nzColor="green">
                          <span nz-icon nzType="check-circle"></span>
                          Active
                        </nz-tag>
                      } @else {
                        <nz-tag nzColor="red">
                          <span nz-icon nzType="close-circle"></span>
                          Missing
                        </nz-tag>
                      }
                      @if (index.stats?.isIndexing) {
                        <nz-tag nzColor="blue">
                          <span nz-icon nzType="loading"></span>
                          Indexing
                        </nz-tag>
                      }
                    </td>
                    <td>
                      {{ index.stats?.numberOfDocuments || 0 | number }}
                    </td>
                    <td>
                      {{ index.last_indexed ? (index.last_indexed | date:'short') : 'Never' }}
                    </td>
                    <td>
                      <div class="action-buttons">
                        <button 
                          nz-button 
                          nzType="text" 
                          nzSize="small"
                          (click)="reindexIndex(index.name)"
                          [nzLoading]="isReindexing(index.name)">
                          <span nz-icon nzType="reload"></span>
                        </button>
                        <button 
                          nz-button 
                          nzType="text" 
                          nzSize="small"
                          (click)="viewIndexDetails(index)">
                          <span nz-icon nzType="eye"></span>
                        </button>
                        <button 
                          nz-button 
                          nzType="text" 
                          nzSize="small"
                          nzDanger
                          (click)="clearIndex(index.name)">
                          <span nz-icon nzType="delete"></span>
                        </button>
                      </div>
                    </td>
                  </tr>
                }
              </tbody>
            </nz-table>
          }
        </nz-card>

        <!-- Search Configuration Form -->
        <nz-card nzTitle="Search Configuration" class="config-card">
          @if (isLoadingConfig()) {
            <nz-spin nzSimple></nz-spin>
          } @else if (searchConfig()) {
            <form nz-form [nzLayout]="'horizontal'" (ngSubmit)="saveConfiguration()">
              <div nz-row [nzGutter]="[24, 24]">
                <!-- Search Behavior -->
                <div nz-col [nzSpan]="12">
                  <h3>Search Behavior</h3>
                  <nz-form-item>
                    <nz-form-label [nzSpan]="8">Default Limit</nz-form-label>
                    <nz-form-control [nzSpan]="16">
                      <nz-input-number 
                        [(ngModel)]="searchConfig()!.default_limit" 
                        name="default_limit"
                        [nzMin]="1" 
                        [nzMax]="100">
                      </nz-input-number>
                    </nz-form-control>
                  </nz-form-item>

                  <nz-form-item>
                    <nz-form-label [nzSpan]="8">Max Limit</nz-form-label>
                    <nz-form-control [nzSpan]="16">
                      <nz-input-number 
                        [(ngModel)]="searchConfig()!.max_limit" 
                        name="max_limit"
                        [nzMin]="1" 
                        [nzMax]="1000">
                      </nz-input-number>
                    </nz-form-control>
                  </nz-form-item>

                  <nz-form-item>
                    <nz-form-label [nzSpan]="8">Search Timeout</nz-form-label>
                    <nz-form-control [nzSpan]="16">
                      <nz-input-number 
                        [(ngModel)]="searchConfig()!.search_timeout" 
                        name="search_timeout"
                        [nzMin]="1" 
                        [nzMax]="300"
                        nzAddonAfter="seconds">
                      </nz-input-number>
                    </nz-form-control>
                  </nz-form-item>
                </div>

                <!-- Search Features -->
                <div nz-col [nzSpan]="12">
                  <h3>Search Features</h3>
                  <nz-form-item>
                    <nz-form-label [nzSpan]="8">Suggestions</nz-form-label>
                    <nz-form-control [nzSpan]="16">
                      <nz-switch 
                        [(ngModel)]="searchConfig()!.suggestions_enabled" 
                        name="suggestions_enabled">
                      </nz-switch>
                    </nz-form-control>
                  </nz-form-item>

                  <nz-form-item>
                    <nz-form-label [nzSpan]="8">Min Chars</nz-form-label>
                    <nz-form-control [nzSpan]="16">
                      <nz-input-number 
                        [(ngModel)]="searchConfig()!.suggestion_min_chars" 
                        name="suggestion_min_chars"
                        [nzMin]="1" 
                        [nzMax]="10">
                      </nz-input-number>
                    </nz-form-control>
                  </nz-form-item>

                  <nz-form-item>
                    <nz-form-label [nzSpan]="8">Highlighting</nz-form-label>
                    <nz-form-control [nzSpan]="16">
                      <nz-switch 
                        [(ngModel)]="searchConfig()!.highlighting_enabled" 
                        name="highlighting_enabled">
                      </nz-switch>
                    </nz-form-control>
                  </nz-form-item>

                  <nz-form-item>
                    <nz-form-label [nzSpan]="8">Faceting</nz-form-label>
                    <nz-form-control [nzSpan]="16">
                      <nz-switch 
                        [(ngModel)]="searchConfig()!.faceting_enabled" 
                        name="faceting_enabled">
                      </nz-switch>
                    </nz-form-control>
                  </nz-form-item>
                </div>
              </div>

              <nz-divider></nz-divider>

              <div class="form-actions">
                <button 
                  nz-button 
                  nzType="primary" 
                  type="submit"
                  [nzLoading]="isSavingConfig()">
                  <span nz-icon nzType="save"></span>
                  Save Configuration
                </button>
                <button 
                  nz-button 
                  nzType="default" 
                  (click)="resetConfiguration()">
                  Reset
                </button>
              </div>
            </form>
          }
        </nz-card>

        <!-- Indexing Tasks -->
        <nz-card nzTitle="Recent Indexing Tasks" class="tasks-card">
          @if (isLoadingTasks()) {
            <nz-spin nzSimple></nz-spin>
          } @else {
            <nz-table 
              #tasksTable 
              [nzData]="indexingTasks()" 
              [nzPageSize]="5"
              nzSize="small">
              <thead>
                <tr>
                  <th>Task Type</th>
                  <th>Index</th>
                  <th>Status</th>
                  <th>Progress</th>
                  <th>Started</th>
                </tr>
              </thead>
              <tbody>
                @for (task of indexingTasks(); track task.id) {
                  <tr>
                    <td>{{ task.task_type | titlecase }}</td>
                    <td>{{ task.index_name }}</td>
                    <td>
                      <nz-tag [nzColor]="getTaskStatusColor(task.status)">
                        {{ task.status | titlecase }}
                      </nz-tag>
                    </td>
                    <td>
                      <nz-progress 
                        [nzPercent]="task.progress_percentage" 
                        [nzStatus]="task.status === 'failed' ? 'exception' : 'active'"
                        nzSize="small">
                      </nz-progress>
                    </td>
                    <td>{{ task.created_at | date:'short' }}</td>
                  </tr>
                }
              </tbody>
            </nz-table>
          }
        </nz-card>
      </nz-content>
    </nz-layout>

    <!-- Index Details Modal -->
    <nz-modal
      [(nzVisible)]="isIndexDetailsModalVisible"
      nzTitle="Index Details"
      [nzFooter]="null"
      [nzWidth]="800"
      (nzOnCancel)="closeIndexDetailsModal()">
      
      <div *nzModalContent>
        @if (selectedIndexDetails()) {
          <nz-descriptions nzBordered [nzColumn]="2">
            <nz-descriptions-item nzTitle="Index Name">
              {{ selectedIndexDetails()?.name }}
            </nz-descriptions-item>
            <nz-descriptions-item nzTitle="Display Name">
              {{ selectedIndexDetails()?.display_name }}
            </nz-descriptions-item>
            <nz-descriptions-item nzTitle="Document Count">
              {{ selectedIndexDetails()?.stats?.numberOfDocuments || 0 | number }}
            </nz-descriptions-item>
            <nz-descriptions-item nzTitle="Status">
              @if (selectedIndexDetails()?.exists) {
                <nz-tag nzColor="green">Active</nz-tag>
              } @else {
                <nz-tag nzColor="red">Missing</nz-tag>
              }
            </nz-descriptions-item>
          </nz-descriptions>

          <nz-divider nzText="Configuration"></nz-divider>

          <div class="index-config">
            <h4>Searchable Attributes</h4>
            <div class="attribute-tags">
              @for (attr of selectedIndexDetails()?.config?.searchable_attributes; track attr) {
                <nz-tag>{{ attr }}</nz-tag>
              }
            </div>

            <h4>Filterable Attributes</h4>
            <div class="attribute-tags">
              @for (attr of selectedIndexDetails()?.config?.filterable_attributes; track attr) {
                <nz-tag nzColor="blue">{{ attr }}</nz-tag>
              }
            </div>

            <h4>Sortable Attributes</h4>
            <div class="attribute-tags">
              @for (attr of selectedIndexDetails()?.config?.sortable_attributes; track attr) {
                <nz-tag nzColor="purple">{{ attr }}</nz-tag>
              }
            </div>
          </div>
        }
      </div>
    </nz-modal>
  `,
  styleUrls: ['./search-config.component.scss']
})
export class SearchConfigComponent implements OnInit {
  private readonly http = inject(HttpClient);
  private readonly message = inject(NzMessageService);
  private readonly modal = inject(NzModalService);

  // Reactive state
  searchStats = signal<SearchStats | null>(null);
  searchConfig = signal<SearchConfiguration | null>(null);
  indexingTasks = signal<IndexingTask[]>([]);
  selectedIndexDetails = signal<any>(null);
  
  // Loading states
  isLoadingStats = signal(false);
  isLoadingConfig = signal(false);
  isLoadingTasks = signal(false);
  isSavingConfig = signal(false);
  reindexingIndexes = signal<Set<string>>(new Set());
  
  // UI state
  isIndexDetailsModalVisible = false;

  ngOnInit(): void {
    this.loadSearchStats();
    this.loadSearchConfig();
    this.loadIndexingTasks();
  }

  loadSearchStats(): void {
    this.isLoadingStats.set(true);
    this.http.get<SearchStats>(`${environment.apiUrl}/search/stats/`)
      .subscribe({
        next: (stats) => {
          this.searchStats.set(stats);
          this.isLoadingStats.set(false);
        },
        error: (error) => {
          console.error('Error loading search stats:', error);
          this.message.error('Failed to load search statistics');
          this.isLoadingStats.set(false);
        }
      });
  }

  loadSearchConfig(): void {
    this.isLoadingConfig.set(true);
    this.http.get<SearchConfiguration>(`${environment.apiUrl}/search/configuration/`)
      .subscribe({
        next: (config) => {
          this.searchConfig.set(config);
          this.isLoadingConfig.set(false);
        },
        error: (error) => {
          console.error('Error loading search config:', error);
          this.message.error('Failed to load search configuration');
          this.isLoadingConfig.set(false);
        }
      });
  }

  loadIndexingTasks(): void {
    this.isLoadingTasks.set(true);
    this.http.get<{results: IndexingTask[]}>(`${environment.apiUrl}/search/indexing-tasks/?limit=20`)
      .subscribe({
        next: (response) => {
          this.indexingTasks.set(response.results);
          this.isLoadingTasks.set(false);
        },
        error: (error) => {
          console.error('Error loading indexing tasks:', error);
          this.indexingTasks.set([]);
          this.isLoadingTasks.set(false);
        }
      });
  }

  checkHealth(): void {
    this.http.get(`${environment.apiUrl}/search/health/`)
      .subscribe({
        next: () => {
          this.message.success('Health check initiated');
          setTimeout(() => this.loadSearchStats(), 2000);
        },
        error: () => {
          this.message.error('Health check failed');
        }
      });
  }

  refreshStats(): void {
    this.loadSearchStats();
    this.loadIndexingTasks();
  }

  reindexIndex(indexName: string): void {
    const currentIndexes = this.reindexingIndexes();
    currentIndexes.add(indexName);
    this.reindexingIndexes.set(new Set(currentIndexes));

    this.http.post(`${environment.apiUrl}/search/reindex/${indexName}/`, {})
      .subscribe({
        next: () => {
          this.message.success(`Reindexing ${indexName} started`);
          setTimeout(() => this.loadSearchStats(), 3000);
        },
        error: () => {
          this.message.error(`Failed to reindex ${indexName}`);
        },
        complete: () => {
          const updatedIndexes = this.reindexingIndexes();
          updatedIndexes.delete(indexName);
          this.reindexingIndexes.set(new Set(updatedIndexes));
        }
      });
  }

  clearIndex(indexName: string): void {
    this.modal.confirm({
      nzTitle: 'Clear Index',
      nzContent: `Are you sure you want to clear all documents from "${indexName}"?`,
      nzOkText: 'Clear',
      nzOkType: 'primary',
      nzOkDanger: true,
      nzOnOk: () => {
        this.http.post(`${environment.apiUrl}/search/clear/${indexName}/`, {})
          .subscribe({
            next: () => {
              this.message.success(`Index ${indexName} cleared`);
              this.loadSearchStats();
            },
            error: () => {
              this.message.error(`Failed to clear ${indexName}`);
            }
          });
      }
    });
  }

  viewIndexDetails(index: any): void {
    this.selectedIndexDetails.set(index);
    this.isIndexDetailsModalVisible = true;
  }

  closeIndexDetailsModal(): void {
    this.isIndexDetailsModalVisible = false;
    this.selectedIndexDetails.set(null);
  }

  saveConfiguration(): void {
    if (!this.searchConfig()) return;

    this.isSavingConfig.set(true);
    this.http.put(`${environment.apiUrl}/search/configuration/`, this.searchConfig())
      .subscribe({
        next: (config) => {
          this.searchConfig.set(config as SearchConfiguration);
          this.message.success('Configuration saved successfully');
          this.isSavingConfig.set(false);
        },
        error: () => {
          this.message.error('Failed to save configuration');
          this.isSavingConfig.set(false);
        }
      });
  }

  resetConfiguration(): void {
    this.loadSearchConfig();
  }

  showCreateIndexModal(): void {
    this.message.info('Create index feature coming soon');
  }

  // Helper methods
  getTotalIndexes(): number {
    return this.searchStats()?.indexes?.length || 0;
  }

  getTotalDocuments(): number {
    return this.searchStats()?.indexes?.reduce((total, index) => 
      total + (index.stats?.numberOfDocuments || 0), 0) || 0;
  }

  getActiveIndexes(): number {
    return this.searchStats()?.indexes?.filter(index => index.exists)?.length || 0;
  }

  getIndexesTableData(): any[] {
    return this.searchStats()?.indexes || [];
  }

  isReindexing(indexName: string): boolean {
    return this.reindexingIndexes().has(indexName);
  }

  getTaskStatusColor(status: string): string {
    const colorMap: { [key: string]: string } = {
      'pending': 'blue',
      'running': 'processing',
      'completed': 'success',
      'failed': 'error',
      'cancelled': 'default'
    };
    return colorMap[status] || 'default';
  }
}
