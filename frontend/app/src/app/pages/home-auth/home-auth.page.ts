import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { CardModule } from 'primeng/card';
import { ButtonModule } from 'primeng/button';
import { RouterLink } from '@angular/router';
import { TableModule } from 'primeng/table';
import { ChipModule } from 'primeng/chip';
import { TranslationService } from '../../shared/translation.service';

@Component({
  standalone: true,
  selector: 'app-home-auth',
  imports: [CommonModule, CardModule, ButtonModule, RouterLink, TableModule, ChipModule],
  template: `
    <div class="home-auth-page">
      <div class="container py-6">
        <!-- Welcome Header -->
        <div class="welcome-header mb-6">
          <div class="flex justify-between items-center">
            <div>
              <h1 class="text-dark mb-2">{{ t('home.auth.title') }}</h1>
              <p class="text-muted">{{ t('home.auth.description') }}</p>
            </div>
            <div class="header-actions">
              <a routerLink="/auth/profile-capture" pButton label="Edit Profile" [outlined]="true" class="me-2"></a>
              <a [routerLink]="['/publishers','itqan']" pButton [label]="t('home.auth.goToPublisher')"></a>
            </div>
          </div>
        </div>

        <!-- Dashboard Stats -->
        <div class="dashboard-stats mb-6">
          <div class="row">
            <div class="col-3 mb-4">
              <p-card class="stat-card">
                <div class="stat-content">
                  <div class="stat-icon">
                    <i class="pi pi-database"></i>
                  </div>
                  <div class="stat-info">
                    <h3 class="stat-number">24</h3>
                    <p class="stat-label">My Resources</p>
                  </div>
                </div>
              </p-card>
            </div>
            
            <div class="col-3 mb-4">
              <p-card class="stat-card">
                <div class="stat-content">
                  <div class="stat-icon">
                    <i class="pi pi-download"></i>
                  </div>
                  <div class="stat-info">
                    <h3 class="stat-number">156</h3>
                    <p class="stat-label">Downloads</p>
                  </div>
                </div>
              </p-card>
            </div>
            
            <div class="col-3 mb-4">
              <p-card class="stat-card">
                <div class="stat-content">
                  <div class="stat-icon">
                    <i class="pi pi-users"></i>
                  </div>
                  <div class="stat-info">
                    <h3 class="stat-number">3</h3>
                    <p class="stat-label">Publishers</p>
                  </div>
                </div>
              </p-card>
            </div>
            
            <div class="col-3 mb-4">
              <p-card class="stat-card">
                <div class="stat-content">
                  <div class="stat-icon">
                    <i class="pi pi-star"></i>
                  </div>
                  <div class="stat-info">
                    <h3 class="stat-number">4.8</h3>
                    <p class="stat-label">Avg Rating</p>
                  </div>
                </div>
              </p-card>
            </div>
          </div>
        </div>

        <!-- Recent Activity -->
        <div class="row">
          <div class="col-8">
            <p-card header="Recent Resources" class="mb-4">
              <p-table [value]="recentResources" [paginator]="false">
                <ng-template pTemplate="header">
                  <tr>
                    <th>Name</th>
                    <th>Type</th>
                    <th>Status</th>
                    <th>Downloads</th>
                    <th>Actions</th>
                  </tr>
                </ng-template>
                <ng-template pTemplate="body" let-resource>
                  <tr>
                    <td>
                      <div class="resource-name">
                        <strong>{{ resource.name }}</strong>
                        <small class="text-muted d-block">{{ resource.description }}</small>
                      </div>
                    </td>
                    <td>
                      <p-chip [label]="resource.type" [style]="{'background-color': resource.typeColor}"></p-chip>
                    </td>
                    <td>
                      <p-chip [label]="resource.status" 
                              [style]="{'background-color': resource.status === 'Published' ? '#28a745' : '#ffc107'}"></p-chip>
                    </td>
                    <td>{{ resource.downloads }}</td>
                    <td>
                      <a [routerLink]="['/resources', resource.id]" pButton icon="pi pi-eye" 
                         size="small" [outlined]="true" class="me-2"></a>
                      <button pButton icon="pi pi-pencil" size="small" [outlined]="true"></button>
                    </td>
                  </tr>
                </ng-template>
              </p-table>
            </p-card>
          </div>
          
          <div class="col-4">
            <!-- Quick Actions -->
            <p-card header="Quick Actions" class="mb-4">
              <div class="quick-actions">
                <button pButton label="Upload Resource" icon="pi pi-upload" class="w-full mb-2"></button>
                <button pButton label="Create Publisher" icon="pi pi-plus" [outlined]="true" class="w-full mb-2"></button>
                <a routerLink="/content-standards" pButton label="View Standards" 
                   icon="pi pi-book" [outlined]="true" class="w-full"></a>
              </div>
            </p-card>
            
            <!-- Recent Downloads -->
            <p-card header="Recent Downloads">
              <div class="recent-downloads">
                <div class="download-item" *ngFor="let download of recentDownloads">
                  <div class="download-info">
                    <strong class="download-name">{{ download.name }}</strong>
                    <small class="text-muted d-block">{{ download.date }}</small>
                  </div>
                  <div class="download-size text-muted">
                    {{ download.size }}
                  </div>
                </div>
              </div>
            </p-card>
          </div>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .home-auth-page {
      background: #f8f9fa;
      min-height: 100vh;
    }
    
    .welcome-header h1 {
      font-size: 2rem;
      font-weight: 600;
    }
    
    .stat-card {
      height: 100%;
      transition: transform 0.2s;
    }
    
    .stat-card:hover {
      transform: translateY(-2px);
    }
    
    .stat-content {
      display: flex;
      align-items: center;
      gap: 1rem;
    }
    
    .stat-icon {
      width: 60px;
      height: 60px;
      border-radius: 50%;
      background: var(--p-primary-100);
      display: flex;
      align-items: center;
      justify-content: center;
    }
    
    .stat-icon i {
      font-size: 1.5rem;
      color: var(--p-primary-500);
    }
    
    .stat-number {
      font-size: 1.75rem;
      font-weight: 700;
      color: var(--p-primary-500);
      margin: 0;
    }
    
    .stat-label {
      color: #6c757d;
      margin: 0;
      font-size: 0.875rem;
    }
    
    .resource-name strong {
      display: block;
      margin-bottom: 0.25rem;
    }
    
    .quick-actions {
      display: flex;
      flex-direction: column;
    }
    
    .download-item {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 0.75rem 0;
      border-bottom: 1px solid #dee2e6;
    }
    
    .download-item:last-child {
      border-bottom: none;
    }
    
    .download-name {
      display: block;
      margin-bottom: 0.25rem;
    }
    
    .col-3 {
      flex: 0 0 25%;
      max-width: 25%;
    }
    
    .col-4 {
      flex: 0 0 33.333333%;
      max-width: 33.333333%;
    }
    
    .col-8 {
      flex: 0 0 66.666667%;
      max-width: 66.666667%;
    }
    
    /* Responsive */
    @media (max-width: 768px) {
      .col-3, .col-4, .col-8 {
        flex: 0 0 100%;
        max-width: 100%;
      }
      
      .header-actions {
        margin-top: 1rem;
      }
      
      .flex {
        flex-direction: column;
        align-items: flex-start !important;
      }
    }
  `]
})
export class HomeAuthPage {
  private translationService = inject(TranslationService);
  t = this.translationService.t;
  
  recentResources = [
    {
      id: 'quran-uthmani',
      name: 'Quran Uthmani Script',
      description: 'Complete Quran in Uthmani script with Tajweed',
      type: 'Text',
      typeColor: '#e3f2fd',
      status: 'Published',
      downloads: 1247
    },
    {
      id: 'tafseer-ibn-kathir',
      name: 'Tafseer Ibn Kathir',
      description: 'Classical commentary by Ibn Kathir',
      type: 'Commentary',
      typeColor: '#f3e5f5',
      status: 'Review',
      downloads: 856
    },
    {
      id: 'quran-audio-mishary',
      name: 'Quran Audio - Mishary',
      description: 'Complete recitation by Sheikh Mishary',
      type: 'Audio',
      typeColor: '#e8f5e8',
      status: 'Published',
      downloads: 2103
    }
  ];
  
  recentDownloads = [
    { name: 'Sahih Bukhari Collection', date: '2 hours ago', size: '45 MB' },
    { name: 'Quran Translation - English', date: '1 day ago', size: '12 MB' },
    { name: 'Hadith Qudsi Collection', date: '3 days ago', size: '8 MB' }
  ];
}


