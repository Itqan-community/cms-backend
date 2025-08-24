import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { CardModule } from 'primeng/card';
import { TableModule } from 'primeng/table';
import { ButtonModule } from 'primeng/button';
import { ChipModule } from 'primeng/chip';
import { TagModule } from 'primeng/tag';
import { AvatarModule } from 'primeng/avatar';
import { TabViewModule } from 'primeng/tabview';
import { RouterLink } from '@angular/router';
import { TranslationService } from '../../shared/translation.service';

@Component({
  standalone: true,
  selector: 'app-publisher-details',
  imports: [CommonModule, CardModule, TableModule, ButtonModule, ChipModule, TagModule, AvatarModule, TabViewModule, RouterLink],
  template: `
    <div class="publisher-details-page">
      <!-- Breadcrumb Navigation -->
      <div class="breadcrumb-section bg-surface py-3">
        <div class="container">
          <nav class="breadcrumb">
            <a routerLink="/home-auth" class="breadcrumb-item">Home</a>
            <span class="breadcrumb-separator">/</span>
            <span class="breadcrumb-current">Publishers</span>
            <span class="breadcrumb-separator">/</span>
            <span class="breadcrumb-current">{{ publisher.name }}</span>
          </nav>
        </div>
      </div>

      <div class="container py-6">
        <!-- Publisher Header -->
        <div class="publisher-header mb-6">
          <div class="row">
            <div class="col-8">
              <div class="publisher-info">
                <div class="publisher-avatar-section mb-4">
                  <p-avatar [label]="publisher.name.charAt(0)" 
                            size="xlarge" 
                            [style]="{'background-color': publisher.color, 'color': 'white'}"
                            class="me-4"></p-avatar>
                  <div class="publisher-basic-info">
                    <h1 class="publisher-name text-dark mb-2">{{ publisher.name }}</h1>
                    <p class="publisher-tagline text-muted mb-3">{{ publisher.tagline }}</p>
                    <div class="publisher-badges">
                      <p-chip label="Verified Publisher" 
                              icon="pi pi-verified" 
                              [style]="{'background-color': '#28a745', 'color': 'white'}" 
                              class="me-2"></p-chip>
                      <p-chip [label]="publisher.category" 
                              [style]="{'background-color': '#17a2b8', 'color': 'white'}" 
                              class="me-2"></p-chip>
                    </div>
                  </div>
                </div>
                
                <!-- Publisher Stats -->
                <div class="publisher-stats flex gap-6">
                  <div class="stat-item">
                    <div class="stat-number">{{ publisher.stats.resources }}</div>
                    <div class="stat-label">Resources</div>
                  </div>
                  <div class="stat-item">
                    <div class="stat-number">{{ publisher.stats.downloads }}</div>
                    <div class="stat-label">Total Downloads</div>
                  </div>
                  <div class="stat-item">
                    <div class="stat-number">{{ publisher.stats.followers }}</div>
                    <div class="stat-label">Followers</div>
                  </div>
                  <div class="stat-item">
                    <div class="stat-number">{{ publisher.stats.rating }}</div>
                    <div class="stat-label">Rating</div>
                  </div>
                </div>
              </div>
            </div>
            
            <div class="col-4">
              <div class="publisher-actions">
                <p-card class="action-card">
                  <div class="action-content">
                    <h3 class="mb-3">Publisher Actions</h3>
                    
                    <button pButton label="Follow Publisher" 
                            icon="pi pi-heart" 
                            class="w-full mb-3 follow-btn"></button>
                    
                    <button pButton label="Contact Publisher" 
                            icon="pi pi-envelope" 
                            [outlined]="true" 
                            class="w-full mb-3"></button>
                    
                    <button pButton label="Report Publisher" 
                            icon="pi pi-flag" 
                            severity="secondary" 
                            [outlined]="true" 
                            class="w-full mb-3"></button>
                    
                    <div class="publisher-links mt-4">
                      <h4 class="mb-2">External Links</h4>
                      <div class="links-list">
                        <a *ngFor="let link of publisher.externalLinks" 
                           [href]="link.url" 
                           target="_blank" 
                           class="external-link">
                          <i [class]="link.icon" class="me-2"></i>
                          {{ link.label }}
                        </a>
                      </div>
                    </div>
                  </div>
                </p-card>
              </div>
            </div>
          </div>
        </div>

        <!-- Publisher Content Tabs -->
        <div class="publisher-content">
          <p-tabView>
            <!-- Resources Tab -->
            <p-tabPanel header="Resources ({{ resources.length }})">
              <div class="resources-section">
                <!-- Filters and Search -->
                <div class="resources-header mb-4">
                  <div class="flex justify-between items-center">
                    <h3>Published Resources</h3>
                    <div class="resource-filters flex gap-2">
                      <p-chip label="All" [style]="{'background-color': '#007bff', 'color': 'white'}"></p-chip>
                      <p-chip label="Text" [style]="{'background-color': '#f8f9fa'}"></p-chip>
                      <p-chip label="Audio" [style]="{'background-color': '#f8f9fa'}"></p-chip>
                      <p-chip label="Commentary" [style]="{'background-color': '#f8f9fa'}"></p-chip>
                    </div>
                  </div>
                </div>

                <!-- Resources Table -->
                <p-table [value]="resources" 
                         [paginator]="true" 
                         [rows]="10" 
                         [showCurrentPageReport]="true"
                         currentPageReportTemplate="Showing {first} to {last} of {totalRecords} resources"
                         [rowsPerPageOptions]="[10, 25, 50]">
                  <ng-template pTemplate="header">
                    <tr>
                      <th pSortableColumn="name">
                        Resource Name <p-sortIcon field="name"></p-sortIcon>
                      </th>
                      <th pSortableColumn="type">
                        Type <p-sortIcon field="type"></p-sortIcon>
                      </th>
                      <th pSortableColumn="version">
                        Version <p-sortIcon field="version"></p-sortIcon>
                      </th>
                      <th pSortableColumn="language">
                        Language <p-sortIcon field="language"></p-sortIcon>
                      </th>
                      <th pSortableColumn="license">
                        License <p-sortIcon field="license"></p-sortIcon>
                      </th>
                      <th pSortableColumn="downloads">
                        Downloads <p-sortIcon field="downloads"></p-sortIcon>
                      </th>
                      <th pSortableColumn="updated">
                        Last Updated <p-sortIcon field="updated"></p-sortIcon>
                      </th>
                      <th>Actions</th>
                    </tr>
                  </ng-template>
                  <ng-template pTemplate="body" let-resource>
                    <tr>
                      <td>
                        <div class="resource-name-cell">
                          <strong>{{ resource.name }}</strong>
                          <small class="text-muted d-block">{{ resource.description }}</small>
                        </div>
                      </td>
                      <td>
                        <p-tag [value]="resource.type" 
                               [style]="{'background-color': resource.typeColor}"></p-tag>
                      </td>
                      <td>
                        <p-chip [label]="resource.version" 
                                size="small" 
                                [style]="{'background-color': '#e8f5e8'}"></p-chip>
                      </td>
                      <td>{{ resource.language }}</td>
                      <td>
                        <p-chip [label]="resource.license" 
                                size="small" 
                                [style]="{'background-color': '#e3f2fd'}"></p-chip>
                      </td>
                      <td>{{ resource.downloads | number }}</td>
                      <td>{{ resource.updated }}</td>
                      <td>
                        <div class="action-buttons">
                          <a [routerLink]="['/resources', resource.id]" 
                             pButton icon="pi pi-eye" 
                             size="small" 
                             [outlined]="true" 
                             pTooltip="View Details"
                             class="me-1"></a>
                          <button pButton icon="pi pi-download" 
                                  size="small" 
                                  [outlined]="true" 
                                  pTooltip="Download"
                                  class="me-1"></button>
                          <button pButton icon="pi pi-share-alt" 
                                  size="small" 
                                  [outlined]="true" 
                                  pTooltip="Share"></button>
                        </div>
                      </td>
                    </tr>
                  </ng-template>
                </p-table>
              </div>
            </p-tabPanel>

            <!-- About Tab -->
            <p-tabPanel header="About">
              <div class="about-section">
                <div class="row">
                  <div class="col-8">
                    <div class="about-content">
                      <h3 class="mb-3">About {{ publisher.name }}</h3>
                      <p class="mb-4">{{ publisher.about.description }}</p>
                      
                      <h4 class="mb-3">Mission</h4>
                      <p class="mb-4">{{ publisher.about.mission }}</p>
                      
                      <h4 class="mb-3">Specializations</h4>
                      <ul class="specializations-list mb-4">
                        <li *ngFor="let spec of publisher.about.specializations">{{ spec }}</li>
                      </ul>
                      
                      <h4 class="mb-3">Quality Standards</h4>
                      <div class="quality-standards">
                        <div *ngFor="let standard of publisher.about.qualityStandards" class="standard-item">
                          <i class="pi pi-check-circle text-success me-2"></i>
                          <span>{{ standard }}</span>
                        </div>
                      </div>
                    </div>
                  </div>
                  
                  <div class="col-4">
                    <div class="publisher-metadata">
                      <p-card header="Publisher Information">
                        <div class="metadata-list">
                          <div class="metadata-item">
                            <strong>Founded:</strong>
                            <span>{{ publisher.metadata.founded }}</span>
                          </div>
                          <div class="metadata-item">
                            <strong>Location:</strong>
                            <span>{{ publisher.metadata.location }}</span>
                          </div>
                          <div class="metadata-item">
                            <strong>Type:</strong>
                            <span>{{ publisher.metadata.type }}</span>
                          </div>
                          <div class="metadata-item">
                            <strong>Languages:</strong>
                            <span>{{ publisher.metadata.languages.join(', ') }}</span>
                          </div>
                          <div class="metadata-item">
                            <strong>Team Size:</strong>
                            <span>{{ publisher.metadata.teamSize }}</span>
                          </div>
                          <div class="metadata-item">
                            <strong>Verification:</strong>
                            <span class="text-success">
                              <i class="pi pi-verified me-1"></i>
                              Verified
                            </span>
                          </div>
                        </div>
                      </p-card>
                    </div>
                  </div>
                </div>
              </div>
            </p-tabPanel>

            <!-- Reviews Tab -->
            <p-tabPanel header="Reviews ({{ publisher.reviews.length }})">
              <div class="reviews-section">
                <div class="reviews-summary mb-4">
                  <div class="row">
                    <div class="col-4">
                      <div class="rating-overview text-center">
                        <div class="overall-rating">
                          <span class="rating-number">{{ publisher.stats.rating }}</span>
                          <div class="rating-stars">
                            <i *ngFor="let star of [1,2,3,4,5]" 
                               class="pi pi-star-fill text-warning"></i>
                          </div>
                          <p class="rating-count text-muted">Based on {{ publisher.reviews.length }} reviews</p>
                        </div>
                      </div>
                    </div>
                    <div class="col-8">
                      <div class="rating-breakdown">
                        <div *ngFor="let rating of ratingBreakdown" class="rating-bar">
                          <span class="rating-label">{{ rating.stars }} stars</span>
                          <div class="progress-bar">
                            <div class="progress-fill" [style.width.%]="rating.percentage"></div>
                          </div>
                          <span class="rating-count">{{ rating.count }}</span>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>

                <div class="reviews-list">
                  <div *ngFor="let review of publisher.reviews" class="review-item">
                    <div class="review-header">
                      <div class="reviewer-info">
                        <p-avatar [label]="review.reviewer.charAt(0)" class="me-2"></p-avatar>
                        <div>
                          <strong>{{ review.reviewer }}</strong>
                          <div class="review-stars">
                            <i *ngFor="let star of [1,2,3,4,5]" 
                               [class]="star <= review.rating ? 'pi pi-star-fill text-warning' : 'pi pi-star text-muted'"></i>
                          </div>
                        </div>
                      </div>
                      <span class="review-date text-muted">{{ review.date }}</span>
                    </div>
                    <p class="review-content">{{ review.content }}</p>
                  </div>
                </div>
              </div>
            </p-tabPanel>
          </p-tabView>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .publisher-details-page {
      min-height: 100vh;
      background: #f8f9fa;
    }

    /* Breadcrumb */
    .breadcrumb-section {
      border-bottom: 1px solid #dee2e6;
    }

    .breadcrumb {
      display: flex;
      align-items: center;
      font-size: 0.875rem;
    }

    .breadcrumb-item {
      color: var(--p-primary-500);
      text-decoration: none;
    }

    .breadcrumb-item:hover {
      text-decoration: underline;
    }

    .breadcrumb-separator {
      margin: 0 0.5rem;
      color: #6c757d;
    }

    .breadcrumb-current {
      color: #6c757d;
      font-weight: 500;
    }

    /* Publisher Header */
    .publisher-header {
      background: white;
      border-radius: 0.5rem;
      padding: 2rem;
      box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }

    .publisher-avatar-section {
      display: flex;
      align-items: center;
    }

    .publisher-name {
      font-size: 2rem;
      font-weight: 700;
    }

    .publisher-tagline {
      font-size: 1.125rem;
      line-height: 1.6;
    }

    .publisher-badges {
      display: flex;
      flex-wrap: wrap;
      gap: 0.5rem;
    }

    .publisher-stats {
      margin-top: 2rem;
    }

    .stat-item {
      text-align: center;
    }

    .stat-number {
      font-size: 1.5rem;
      font-weight: 700;
      color: var(--p-primary-500);
      display: block;
    }

    .stat-label {
      font-size: 0.875rem;
      color: #6c757d;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }

    /* Action Card */
    .action-card {
      position: sticky;
      top: 2rem;
    }

    .follow-btn {
      background: var(--p-primary-500);
      border-color: var(--p-primary-500);
    }

    .links-list {
      display: flex;
      flex-direction: column;
      gap: 0.5rem;
    }

    .external-link {
      display: flex;
      align-items: center;
      color: var(--p-primary-500);
      text-decoration: none;
      padding: 0.5rem;
      border-radius: 0.25rem;
      transition: background-color 0.2s;
    }

    .external-link:hover {
      background: rgba(102, 155, 128, 0.1);
    }

    /* Resources Section */
    .resources-header h3 {
      color: #333;
      margin: 0;
    }

    .resource-filters {
      cursor: pointer;
    }

    .resource-name-cell strong {
      display: block;
      margin-bottom: 0.25rem;
    }

    .action-buttons {
      display: flex;
      gap: 0.25rem;
    }

    /* About Section */
    .about-content h3,
    .about-content h4 {
      color: #333;
    }

    .specializations-list {
      padding-left: 1.5rem;
    }

    .specializations-list li {
      margin-bottom: 0.5rem;
    }

    .standard-item {
      display: flex;
      align-items: center;
      margin-bottom: 0.75rem;
    }

    .metadata-list {
      display: flex;
      flex-direction: column;
      gap: 1rem;
    }

    .metadata-item {
      display: flex;
      flex-direction: column;
      gap: 0.25rem;
    }

    .metadata-item strong {
      font-size: 0.875rem;
      color: #6c757d;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }

    /* Reviews Section */
    .rating-overview {
      padding: 1rem;
    }

    .rating-number {
      font-size: 3rem;
      font-weight: 700;
      color: var(--p-primary-500);
      display: block;
    }

    .rating-stars {
      margin: 0.5rem 0;
    }

    .rating-breakdown {
      padding: 1rem;
    }

    .rating-bar {
      display: flex;
      align-items: center;
      gap: 1rem;
      margin-bottom: 0.5rem;
    }

    .rating-label {
      min-width: 60px;
      font-size: 0.875rem;
    }

    .progress-bar {
      flex: 1;
      height: 8px;
      background: #e9ecef;
      border-radius: 4px;
      overflow: hidden;
    }

    .progress-fill {
      height: 100%;
      background: var(--p-primary-500);
    }

    .rating-count {
      min-width: 30px;
      font-size: 0.875rem;
      color: #6c757d;
    }

    .review-item {
      border-bottom: 1px solid #dee2e6;
      padding: 1.5rem 0;
    }

    .review-item:last-child {
      border-bottom: none;
    }

    .review-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 1rem;
    }

    .reviewer-info {
      display: flex;
      align-items: center;
    }

    .review-stars {
      margin-top: 0.25rem;
    }

    .review-content {
      line-height: 1.6;
      color: #333;
    }

    /* Grid System */
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
      .col-4, .col-8 {
        flex: 0 0 100%;
        max-width: 100%;
      }

      .publisher-header {
        padding: 1rem;
      }

      .publisher-avatar-section {
        flex-direction: column;
        text-align: center;
      }

      .publisher-stats {
        flex-direction: column;
        gap: 1rem;
      }

      .resources-header {
        flex-direction: column;
        gap: 1rem;
      }
    }

    /* RTL Adjustments */
    [dir="rtl"] .me-2 {
      margin-left: 0.5rem;
      margin-right: 0;
    }

    [dir="rtl"] .me-1 {
      margin-left: 0.25rem;
      margin-right: 0;
    }

    [dir="rtl"] .me-4 {
      margin-left: 1.5rem;
      margin-right: 0;
    }
  `]
})
export class PublisherDetailsPage {
  private translationService = inject(TranslationService);
  t = this.translationService.t;

  publisher = {
    name: 'Itqan Foundation',
    tagline: 'Preserving and sharing authentic Islamic knowledge through technology',
    category: 'Non-Profit Organization',
    color: '#669B80',
    stats: {
      resources: 24,
      downloads: '156K',
      followers: '2.3K',
      rating: '4.8'
    },
    externalLinks: [
      { label: 'Official Website', url: 'https://itqan.dev', icon: 'pi pi-globe' },
      { label: 'GitHub Repository', url: 'https://github.com/itqan', icon: 'pi pi-github' },
      { label: 'Contact Email', url: 'mailto:info@itqan.dev', icon: 'pi pi-envelope' },
      { label: 'Documentation', url: 'https://docs.itqan.dev', icon: 'pi pi-book' }
    ],
    about: {
      description: 'The Itqan Foundation is a non-profit organization dedicated to preserving, digitizing, and sharing authentic Islamic knowledge through modern technology. We work with scholars, institutions, and developers worldwide to create high-quality, verified Islamic content resources.',
      mission: 'To make authentic Islamic knowledge accessible to everyone through technology, while maintaining the highest standards of accuracy and authenticity in all our digital resources.',
      specializations: [
        'Quranic text digitization and verification',
        'Hadith collection compilation and authentication',
        'Islamic calendar and prayer time calculations',
        'Tafsir and commentary digitization',
        'Arabic language processing and NLP',
        'Islamic educational content development'
      ],
      qualityStandards: [
        'All content verified by qualified Islamic scholars',
        'Multiple source cross-referencing for accuracy',
        'Peer review process for all published resources',
        'Regular updates and corrections based on feedback',
        'Open-source methodology for transparency'
      ]
    },
    metadata: {
      founded: 'January 2020',
      location: 'International (Remote)',
      type: 'Non-Profit Foundation',
      languages: ['Arabic', 'English', 'Urdu', 'Indonesian'],
      teamSize: '15+ Contributors'
    },
    reviews: [
      {
        reviewer: 'Dr. Ahmad Hassan',
        rating: 5,
        date: '2 weeks ago',
        content: 'Exceptional quality resources with meticulous attention to authenticity. The Quran text collection is particularly impressive with its accurate diacritical marks and comprehensive metadata.'
      },
      {
        reviewer: 'Sarah Ahmed',
        rating: 5,
        date: '1 month ago',
        content: 'As a developer working on Islamic apps, Itqan Foundation\'s resources have been invaluable. The API documentation is clear, and the data quality is outstanding.'
      },
      {
        reviewer: 'Mohamed Ali',
        rating: 4,
        date: '2 months ago',
        content: 'Great collection of authentic Islamic resources. The hadith collections are well-organized and properly attributed. Would love to see more tafsir resources in the future.'
      }
    ]
  };

  resources = [
    {
      id: 'quran-uthmani-hafs',
      name: 'Quran Text - Uthmani Script (Hafs)',
      description: 'Complete Quranic text in Uthmani script with Tajweed marks',
      type: 'Text',
      typeColor: '#e3f2fd',
      version: 'v2.1.0',
      language: 'Arabic',
      license: 'CC0 1.0',
      downloads: 15847,
      updated: '2 weeks ago'
    },
    {
      id: 'hadith-bukhari',
      name: 'Sahih Bukhari Collection',
      description: 'Complete collection of authentic Hadith by Imam Bukhari',
      type: 'Hadith',
      typeColor: '#f3e5f5',
      version: 'v1.3.2',
      language: 'Arabic/English',
      license: 'CC BY 4.0',
      downloads: 8934,
      updated: '1 month ago'
    },
    {
      id: 'quran-audio-mishary',
      name: 'Quran Audio - Mishary Rashid',
      description: 'High-quality recitation by Sheikh Mishary Rashid Al-Afasy',
      type: 'Audio',
      typeColor: '#e8f5e8',
      version: 'v1.0.0',
      language: 'Arabic',
      license: 'CC BY-NC 4.0',
      downloads: 23156,
      updated: '3 weeks ago'
    },
    {
      id: 'tafseer-ibn-kathir',
      name: 'Tafseer Ibn Kathir',
      description: 'Classical Quranic commentary by Ibn Kathir',
      type: 'Commentary',
      typeColor: '#fff3e0',
      version: 'v0.9.1',
      language: 'Arabic',
      license: 'CC BY-SA 4.0',
      downloads: 5672,
      updated: '1 week ago'
    },
    {
      id: 'islamic-calendar',
      name: 'Islamic Calendar Data',
      description: 'Hijri calendar conversion and Islamic dates',
      type: 'Data',
      typeColor: '#fce4ec',
      version: 'v2.0.3',
      language: 'Multi-language',
      license: 'MIT',
      downloads: 12389,
      updated: '4 days ago'
    },
    {
      id: 'prayer-times-global',
      name: 'Global Prayer Times',
      description: 'Accurate prayer times calculation for worldwide locations',
      type: 'Data',
      typeColor: '#fce4ec',
      version: 'v1.8.7',
      language: 'Multi-language',
      license: 'Apache 2.0',
      downloads: 18923,
      updated: '1 week ago'
    }
  ];

  ratingBreakdown = [
    { stars: 5, count: 18, percentage: 75 },
    { stars: 4, count: 4, percentage: 17 },
    { stars: 3, count: 2, percentage: 8 },
    { stars: 2, count: 0, percentage: 0 },
    { stars: 1, count: 0, percentage: 0 }
  ];
}


