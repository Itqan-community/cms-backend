import { Component, OnInit, inject, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { FormBuilder, FormGroup, ReactiveFormsModule, FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { Observable, of } from 'rxjs';

// NG-ZORRO imports
import { NzLayoutModule } from 'ng-zorro-antd/layout';
import { NzCardModule } from 'ng-zorro-antd/card';
import { NzGridModule } from 'ng-zorro-antd/grid';
import { NzInputModule } from 'ng-zorro-antd/input';
import { NzButtonModule } from 'ng-zorro-antd/button';
import { NzIconModule } from 'ng-zorro-antd/icon';
import { NzSelectModule } from 'ng-zorro-antd/select';
import { NzCheckboxModule } from 'ng-zorro-antd/checkbox';
import { NzTagModule } from 'ng-zorro-antd/tag';
import { NzPaginationModule } from 'ng-zorro-antd/pagination';
import { NzSpinModule } from 'ng-zorro-antd/spin';
import { NzEmptyModule } from 'ng-zorro-antd/empty';
import { NzDividerModule } from 'ng-zorro-antd/divider';
import { NzSpaceModule } from 'ng-zorro-antd/space';
import { NzAvatarModule } from 'ng-zorro-antd/avatar';
import { NzTypographyModule } from 'ng-zorro-antd/typography';

import { I18nService } from '../../core/services/i18n.service';
import { AccessRequestModalComponent } from '../access/access-request-modal.component';
import { environment } from '../../../environments/environment';

interface Resource {
  id: string;
  title: string;
  title_en?: string;
  title_ar?: string;
  description: string;
  description_en?: string;
  description_ar?: string;
  resource_type: string;
  license_type: string;
  publisher_name: string;
  publisher_avatar?: string;
  thumbnail?: string;
  file_size?: string;
  download_count?: number;
  created_at: string;
  tags?: string[];
  checksum?: string;
}

interface AssetStoreFilters {
  search?: string;
  category?: string;
  license?: string;
  language?: string;
  publisher?: string;
  page?: number;
  page_size?: number;
}

interface AssetStoreResponse {
  results: Resource[];
  count: number;
  next?: string;
  previous?: string;
}

/**
 * Asset Store Landing Page Component (ADMIN-001)
 * 
 * Main home page showing resource discovery with search, filters, and cards.
 * Matches the Arabic wireframe design with proper RTL support.
 */
@Component({
  selector: 'app-asset-store',
  standalone: true,
  imports: [
    CommonModule,
    RouterModule,
    ReactiveFormsModule,
    FormsModule,
    NzLayoutModule,
    NzCardModule,
    NzGridModule,
    NzInputModule,
    NzButtonModule,
    NzIconModule,
    NzSelectModule,
    NzCheckboxModule,
    NzTagModule,
    NzPaginationModule,
    NzSpinModule,
    NzEmptyModule,
    NzDividerModule,
    NzSpaceModule,
    NzAvatarModule,
    NzTypographyModule,
    AccessRequestModalComponent
  ],
  template: `
    <div class="asset-store-page" [dir]="isArabic() ? 'rtl' : 'ltr'">
      <!-- Search Section (Full Width) -->
      <div class="search-section">
        <div class="search-container">
          <nz-input-group [nzSuffix]="searchSuffix" class="search-input">
            <input 
              nz-input 
              [placeholder]="t('asset_store.search_placeholder')"
              [(ngModel)]="searchQuery"
              (keyup.enter)="onSearch()"
              class="search-field">
          </nz-input-group>
          <ng-template #searchSuffix>
            <button nz-button nzType="text" nzSize="large" (click)="onSearch()">
              <span nz-icon nzType="search" nzTheme="outline"></span>
            </button>
          </ng-template>
        </div>
      </div>

      <!-- Main Content Layout -->
      <nz-layout class="main-layout">
        <!-- Sidebar with Filters (appears first for RTL visual positioning) -->
        <nz-sider 
          class="filters-sidebar" 
          [nzWidth]="280"
          [nzBreakpoint]="'lg'"
          [nzCollapsedWidth]="0"
          nzTheme="light">
          
          <div class="filters-container">
            <div class="filters-header">
              <h3 class="filters-title">{{ t('asset_store.filters') }}</h3>
            </div>
            
            <!-- Categories Filter -->
            <div class="filter-section">
              <h4>{{ t('asset_store.categories') }}</h4>
              <nz-checkbox-group 
                [(ngModel)]="selectedCategories" 
                (ngModelChange)="onCategoryChange()">
                <div class="checkbox-item" *ngFor="let category of availableCategories">
                  <label nz-checkbox [nzValue]="category.value" class="checkbox-label">
                    <span class="checkbox-text">{{ isArabic() ? category.label_ar : category.label_en }}</span>
                    <span class="count">({{ category.count }})</span>
                  </label>
                </div>
              </nz-checkbox-group>
            </div>

            <nz-divider class="filter-divider"></nz-divider>

            <!-- Creative Commons License Filter -->
            <div class="filter-section">
              <h4>{{ t('asset_store.creative_commons') }}</h4>
              <nz-checkbox-group 
                [(ngModel)]="selectedLicenses" 
                (ngModelChange)="onLicenseChange()">
                <div class="checkbox-item" *ngFor="let license of creativeCommonsOptions">
                  <label nz-checkbox [nzValue]="license.value" class="checkbox-label">
                    <span class="cc-content">
                      <span class="cc-icon">{{ license.icon }}</span>
                      <span class="checkbox-text">{{ isArabic() ? license.label_ar : license.label_en }}</span>
                    </span>
                    <span class="count">({{ license.count }})</span>
                  </label>
                </div>
              </nz-checkbox-group>
            </div>

            <nz-divider class="filter-divider"></nz-divider>

            <!-- Language Filter -->
            <div class="filter-section">
              <h4>{{ t('asset_store.language') }}</h4>
              <nz-select 
                [(ngModel)]="selectedLanguage"
                (ngModelChange)="onLanguageChange()"
                [nzPlaceHolder]="t('asset_store.all_languages')"
                nzAllowClear
                class="language-select">
                <nz-option 
                  *ngFor="let lang of languageOptions" 
                  [nzValue]="lang.value" 
                  [nzLabel]="isArabic() ? lang.label_ar : lang.label_en">
                </nz-option>
              </nz-select>
            </div>
          </div>
        </nz-sider>

        <!-- Content Area -->
        <nz-content class="content-area">

          <!-- Resources Grid -->
          <div class="resources-section">
            <!-- Loading State -->
            <div *ngIf="loading()" class="loading-grid">
              <nz-spin nzTip="{{ t('asset_store.loading') }}" nzSize="large">
                <div nz-row [nzGutter]="[16, 16]" class="resources-grid">
                  <div nz-col [nzXs]="24" [nzSm]="12" [nzMd]="8" [nzLg]="6" *ngFor="let i of [1,2,3,4,5,6,7,8]">
                    <nz-card class="resource-card loading-card">
                      <div class="loading-content">
                        <nz-avatar nzSize="large" nzIcon="file"></nz-avatar>
                        <div class="loading-text">
                          <div class="loading-line"></div>
                          <div class="loading-line short"></div>
                        </div>
                      </div>
                    </nz-card>
                  </div>
                </div>
              </nz-spin>
            </div>

            <!-- Resources Grid -->
            <div *ngIf="!loading() && resources().length > 0" class="resources-grid-container">
              <div nz-row [nzGutter]="[16, 16]" class="resources-grid">
                <div 
                  nz-col 
                  [nzXs]="24" 
                  [nzSm]="12" 
                  [nzMd]="8" 
                  [nzLg]="6"
                  *ngFor="let resource of resources(); trackBy: trackByResourceId">
                  
                  <nz-card 
                    class="resource-card"
                    [nzHoverable]="true"
                    [nzCover]="resourceCover"
                    [nzActions]="[requestAccessAction]"
                    (click)="openAccessRequestModal(resource)">
                    
                    <!-- Resource Cover/Thumbnail -->
                    <ng-template #resourceCover>
                      <div class="resource-thumbnail">
                        <img 
                          [src]="resource.thumbnail || '/assets/images/itqan-logo.svg'"
                          [alt]="getLocalizedTitle(resource)"
                          loading="lazy">
                        <div class="resource-overlay">
                          <nz-tag [nzColor]="getResourceTypeColor(resource.resource_type)">
                            <span nz-icon [nzType]="getResourceTypeIcon(resource.resource_type)"></span>
                            {{ getLocalizedResourceType(resource.resource_type) }}
                          </nz-tag>
                        </div>
                      </div>
                    </ng-template>

                    <!-- Resource Details -->
                    <nz-card-meta
                      [nzTitle]="resourceTitle"
                      [nzDescription]="resourceDescription">
                      
                      <ng-template #resourceTitle>
                        <div class="resource-title" [class.rtl]="isArabic()">
                          {{ getLocalizedTitle(resource) }}
                        </div>
                      </ng-template>
                      
                      <ng-template #resourceDescription>
                        <div class="resource-description" [class.rtl]="isArabic()">
                          {{ getLocalizedDescription(resource) }}
                        </div>
                      </ng-template>
                    </nz-card-meta>

                    <!-- Resource Footer -->
                    <div class="resource-footer">
                      <!-- License -->
                      <div class="license-info">
                        <span class="license-label">{{ t('asset_store.license') }}:</span>
                        <nz-tag [nzColor]="getLicenseColor(resource.license_type)">
                          {{ getLocalizedLicense(resource.license_type) }}
                        </nz-tag>
                      </div>
                      
                      <!-- Publisher -->
                      <div class="publisher-info">
                        <nz-avatar 
                          [nzSrc]="resource.publisher_avatar" 
                          [nzIcon]="'user'"
                          nzSize="small">
                        </nz-avatar>
                        <span class="publisher-name">{{ resource.publisher_name }}</span>
                      </div>
                    </div>

                    <!-- Request Access Action -->
                    <ng-template #requestAccessAction>
                      <span nz-icon nzType="key" nzTheme="outline"></span>
                      {{ t('asset_store.request_access') }}
                    </ng-template>
                  </nz-card>
                </div>
              </div>

              <!-- Pagination -->
              <div class="pagination-section">
                              <nz-pagination
                [nzPageIndex]="currentPage()"
                [nzTotal]="totalResources()"
                [nzPageSize]="pageSize"
                [nzShowSizeChanger]="true"
                [nzPageSizeOptions]="[12, 24, 48, 96]"
                [nzShowQuickJumper]="true"
                [nzShowTotal]="totalTemplate"
                (nzPageIndexChange)="onPageChange($event)"
                (nzPageSizeChange)="onPageSizeChange($event)">
                  
                  <ng-template #totalTemplate let-total let-range>
                    {{ t('asset_store.pagination_total', { total: total, start: range[0], end: range[1] }) }}
                  </ng-template>
                </nz-pagination>
              </div>
            </div>

            <!-- Empty State -->
            <div *ngIf="!loading() && resources().length === 0" class="empty-state">
              <nz-empty
                [nzNotFoundContent]="emptyTemplate">
                <ng-template #emptyTemplate>
                  <span>{{ t('asset_store.no_resources') }}</span>
                </ng-template>
              </nz-empty>
            </div>
          </div>
        </nz-content>
      </nz-layout>

      <!-- Access Request Modal -->
      <app-access-request-modal
        [(visible)]="showAccessModal"
        [resource]="selectedResource"
        (requestSubmitted)="onAccessRequestSubmitted($event)">
      </app-access-request-modal>
    </div>
  `,
  styles: [`
    .asset-store-page {
      min-height: calc(100vh - 64px);
      background-color: #f5f5f5;
      padding-top: 64px; /* Account for fixed header */
    }

    /* Search Section (Full Width) */
    .search-section {
      background: #fff;
      padding: 20px 0;
      margin-bottom: 0;
      box-shadow: 0 2px 4px rgba(0, 0, 0, 0.04);
    }

    .search-container {
      max-width: 600px;
      margin: 0 auto;
      padding: 0 24px;
    }

    .search-input {
      width: 100%;
    }

    .search-field {
      font-size: 16px;
      padding: 12px 16px;
      border-radius: 8px;
      background: #f8f9fa;
      border: 1px solid #e9ecef;
    }

    .search-field:focus {
      background: #fff;
      border-color: #669B80;
      box-shadow: 0 0 0 2px rgba(102, 155, 128, 0.2);
    }

    /* Main Layout */
    .main-layout {
      min-height: calc(100vh - 128px);
      background: transparent;
    }

    .content-area {
      padding: 24px;
      background: transparent;
    }

    /* RTL Layout: No flex-direction changes needed */
    /* Sidebar appears on RIGHT in RTL, content on LEFT - matches wireframe */

    /* Resources Grid */
    .resources-section {
      width: 100%;
    }

    .resources-grid-container {
      width: 100%;
    }

    .resources-grid {
      width: 100%;
    }

    .resource-card {
      height: 400px;
      border-radius: 12px;
      transition: all 0.3s ease;
      cursor: pointer;
      overflow: hidden;
    }

    .resource-card:hover {
      transform: translateY(-4px);
      box-shadow: 0 8px 25px rgba(0, 0, 0, 0.15);
    }

    .resource-thumbnail {
      position: relative;
      height: 200px;
      overflow: hidden;
    }

    .resource-thumbnail img {
      width: 100%;
      height: 100%;
      object-fit: cover;
      transition: transform 0.3s ease;
    }

    .resource-card:hover .resource-thumbnail img {
      transform: scale(1.05);
    }

    .resource-overlay {
      position: absolute;
      top: 12px;
      right: 12px;
    }

    .resource-title {
      font-size: 16px;
      font-weight: 600;
      color: #22433D;
      margin-bottom: 8px;
      display: -webkit-box;
      -webkit-line-clamp: 2;
      -webkit-box-orient: vertical;
      overflow: hidden;
    }

    .resource-title.rtl {
      font-family: 'Noto Sans Arabic', sans-serif;
      text-align: right;
    }

    .resource-description {
      color: #666;
      font-size: 14px;
      line-height: 1.5;
      display: -webkit-box;
      -webkit-line-clamp: 3;
      -webkit-box-orient: vertical;
      overflow: hidden;
    }

    .resource-description.rtl {
      font-family: 'Noto Sans Arabic', sans-serif;
      text-align: right;
    }

    .resource-footer {
      margin-top: 16px;
      display: flex;
      flex-direction: column;
      gap: 8px;
    }

    .license-info {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 12px;
    }

    .license-label {
      color: #666;
      font-weight: 500;
    }

    .publisher-info {
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .publisher-name {
      font-size: 14px;
      color: #22433D;
      font-weight: 500;
    }

    /* Filters Sidebar */
    .filters-sidebar {
      background: #fff !important;
      border: 1px solid #e8e8e8;
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
    }

    .filters-container {
      padding: 20px;
      height: 100%;
      background: #fff;
    }

    .filters-header {
      margin-bottom: 20px;
    }

    .filters-title {
      font-size: 18px;
      font-weight: 600;
      color: #22433D;
      margin: 0;
      padding-bottom: 12px;
      border-bottom: 2px solid #669B80;
    }

    [dir="rtl"] .filters-title {
      font-family: 'Noto Sans Arabic', sans-serif;
      text-align: right;
    }

    .filter-section {
      margin-bottom: 20px;
    }

    .filter-section h4 {
      font-size: 14px;
      font-weight: 600;
      color: #22433D;
      margin-bottom: 12px;
    }

    [dir="rtl"] .filter-section h4 {
      font-family: 'Noto Sans Arabic', sans-serif;
      text-align: right;
    }

    .checkbox-item {
      display: block;
      margin-bottom: 10px;
    }

    .checkbox-label {
      display: flex;
      align-items: center;
      justify-content: space-between;
      width: 100%;
      font-size: 13px;
      cursor: pointer;
      padding: 4px 0;
    }

    .checkbox-text {
      flex: 1;
      margin-left: 8px;
    }

    [dir="rtl"] .checkbox-text {
      margin-left: 0;
      margin-right: 8px;
      text-align: right;
      font-family: 'Noto Sans Arabic', sans-serif;
    }

    .cc-content {
      display: flex;
      align-items: center;
      flex: 1;
    }

    .cc-icon {
      margin-right: 6px;
      font-weight: bold;
      color: #669B80;
      font-size: 14px;
    }

    [dir="rtl"] .cc-icon {
      margin-right: 0;
      margin-left: 6px;
    }

    .count {
      color: #999;
      font-size: 12px;
      font-weight: 500;
    }

    .filter-divider {
      margin: 16px 0;
      border-color: #f0f0f0;
    }

    .language-select {
      width: 100%;
    }

    /* RTL Sidebar Adjustments */
    [dir="rtl"] .filters-sidebar {
      border-left: none;
      border-right: 1px solid #e8e8e8;
    }

    /* Pagination */
    .pagination-section {
      display: flex;
      justify-content: center;
      margin-top: 32px;
      padding: 20px;
    }

    /* Loading States */
    .loading-grid {
      min-height: 400px;
      display: flex;
      align-items: center;
      justify-content: center;
    }

    .loading-card {
      height: 400px;
    }

    .loading-content {
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 20px;
    }

    .loading-text {
      flex: 1;
    }

    .loading-line {
      height: 12px;
      background: #f0f0f0;
      border-radius: 6px;
      margin-bottom: 8px;
    }

    .loading-line.short {
      width: 60%;
    }

    /* Empty State */
    .empty-state {
      min-height: 300px;
      display: flex;
      align-items: center;
      justify-content: center;
    }

    /* Additional RTL Support */
    [dir="rtl"] .resource-overlay {
      right: auto;
      left: 12px;
    }

    [dir="rtl"] .publisher-info {
      flex-direction: row-reverse;
    }

    [dir="rtl"] .resource-title,
    [dir="rtl"] .resource-description {
      text-align: right;
      font-family: 'Noto Sans Arabic', sans-serif;
    }

    [dir="rtl"] .license-info {
      flex-direction: row-reverse;
    }

    [dir="rtl"] .pagination-section {
      direction: rtl;
    }

    [dir="rtl"] .search-container {
      direction: rtl;
    }

    [dir="rtl"] .search-field {
      text-align: right;
      font-family: 'Noto Sans Arabic', sans-serif;
    }

    /* Responsive Design */
    @media (max-width: 1200px) {
      .search-container {
        max-width: 500px;
      }
    }

    @media (max-width: 992px) {
      .main-layout {
        flex-direction: column;
      }
      
      .filters-sidebar {
        width: 100% !important;
        max-width: none;
      }
      
      .content-area {
        padding: 16px;
      }
    }

    @media (max-width: 768px) {
      .search-container {
        padding: 0 16px;
        max-width: none;
      }
      
      .resource-card {
        height: auto;
        min-height: 350px;
      }
      
      .search-field {
        font-size: 14px;
      }
      
      .filters-container {
        padding: 16px;
      }
      
      .filters-title {
        font-size: 16px;
      }
    }

    @media (max-width: 576px) {
      .search-section {
        padding: 16px 0;
      }
      
      .asset-store-page {
        padding-top: 64px;
      }
      
      .resource-card {
        min-height: 300px;
      }
    }
  `]
})
export class AssetStoreComponent implements OnInit {
  private http = inject(HttpClient);
  private i18nService = inject(I18nService);
  private fb = inject(FormBuilder);

  // Reactive state
  resources = signal<Resource[]>([]);
  totalResources = signal(0);
  loading = signal(false);
  currentPage = signal(1);
  pageSize = 12;
  searchQuery = '';

  // Filter state
  selectedCategories: string[] = [];
  selectedLicenses: string[] = [];
  selectedLanguage = '';

  // Modal states
  showAccessModal = false;
  selectedResource: Resource | null = null;

  // Computed properties
  isArabic = computed(() => this.i18nService.currentLanguage() === 'ar');

  // Filter options
  availableCategories = [
    { value: 'translation', label_en: 'Translation', label_ar: 'ترجمة', count: 142 },
    { value: 'transliteration', label_en: 'Transliteration', label_ar: 'نقل حرفي', count: 89 },
    { value: 'corpus', label_en: 'Corpus', label_ar: 'مجموعة نصوص', count: 67 },
    { value: 'audio', label_en: 'Audio', label_ar: 'صوتيات', count: 32 },
    { value: 'fonts', label_en: 'Fonts', label_ar: 'خطوط', count: 23 }
  ];

  creativeCommonsOptions = [
    { value: 'cc0', label_en: 'Public Domain', label_ar: 'ملك عام', icon: '🌍', count: 89 },
    { value: 'cc-by', label_en: 'CC BY', label_ar: 'مع النسبة', icon: '✅', count: 67 },
    { value: 'cc-by-sa', label_en: 'ShareAlike', label_ar: 'مشاركة بالمثل', icon: '🔄', count: 34 },
    { value: 'cc-by-nd', label_en: 'No Derivatives', label_ar: 'عدم الاشتقاق', icon: '🚫', count: 22 },
    { value: 'cc-by-nc', label_en: 'Non-Commercial', label_ar: 'غير تجاري', icon: '💰', count: 45 },
    { value: 'cc-by-nc-sa', label_en: 'Non-Commercial ShareAlike', label_ar: 'غير تجاري ومشاركة بالمثل', icon: '🔒', count: 12 },
    { value: 'cc-by-nc-nd', label_en: 'Non-Commercial No Derivatives', label_ar: 'غير تجاري وعدم الاشتقاق', icon: '🔐', count: 8 }
  ];

  languageOptions = [
    { value: 'ar', label_en: 'Arabic', label_ar: 'العربية' },
    { value: 'en', label_en: 'English', label_ar: 'الإنجليزية' },
    { value: 'ur', label_en: 'Urdu', label_ar: 'الأردية' },
    { value: 'fa', label_en: 'Persian', label_ar: 'الفارسية' },
    { value: 'tr', label_en: 'Turkish', label_ar: 'التركية' },
    { value: 'id', label_en: 'Indonesian', label_ar: 'الإندونيسية' }
  ];

  ngOnInit() {
    this.loadResources();
  }

  /**
   * Translation helper method
   */
  t(key: string, params?: any): string {
    return this.i18nService.translate(key, params);
  }

  /**
   * Load resources from API
   */
  loadResources() {
    this.loading.set(true);

    const filters: AssetStoreFilters = {
      search: this.searchQuery,
      page: this.currentPage(),
      page_size: this.pageSize
    };

    if (this.selectedCategories.length > 0) {
      filters.category = this.selectedCategories.join(',');
    }

    if (this.selectedLicenses.length > 0) {
      filters.license = this.selectedLicenses.join(',');
    }

    if (this.selectedLanguage) {
      filters.language = this.selectedLanguage;
    }

    // Mock API call - replace with real endpoint
    this.mockApiCall(filters).subscribe({
      next: (response) => {
        this.resources.set(response.results);
        this.totalResources.set(response.count);
        this.loading.set(false);
      },
      error: (error) => {
        console.error('Error loading resources:', error);
        this.loading.set(false);
      }
    });
  }

  /**
   * Mock API call - replace with real implementation
   */
  private mockApiCall(filters: AssetStoreFilters): Observable<AssetStoreResponse> {
    // Simulate API delay and return Observable
    return of({
      results: this.generateMockResources(),
      count: 353
    });
  }

  /**
   * Generate mock resources for demonstration
   */
  private generateMockResources(): Resource[] {
    return [
      {
        id: '1',
        title: 'Quranic Text Collection',
        title_ar: 'عنوان المصدر شرح مختصر الرخصة اسم الناشر',
        description: 'Complete Quranic text with authentic manuscripts and verified sources for Islamic research and development.',
        description_ar: 'نص قرآني كامل مع المخطوطات الأصلية والمصادر المتحققة للبحث والتطوير الإسلامي.',
        resource_type: 'translation',
        license_type: 'cc-by',
        publisher_name: 'Islamic Research Foundation',
        download_count: 1247,
        created_at: '2024-01-15',
        tags: ['quran', 'manuscript', 'text']
      },
      {
        id: '2',
        title: 'Islamic Audio Collection',
        title_ar: 'عنوان المصدر شرح مختصر الرخصة اسم الناشر',
        description: 'Professional collection of Islamic audio content including Quran recitations and scholarly lectures.',
        description_ar: 'مجموعة احترافية من المحتوى الصوتي الإسلامي تشمل تلاوات القرآن والمحاضرات العلمية.',
        resource_type: 'audio',
        license_type: 'cc0',
        publisher_name: 'Masjid Al-Haram',
        download_count: 892,
        created_at: '2024-02-01',
        tags: ['audio', 'recitation', 'lecture']
      },
      {
        id: '3',
        title: 'Arabic Typography Set',
        title_ar: 'عنوان المصدر شرح مختصر الرخصة اسم الناشر',
        description: 'High-quality Arabic typography and calligraphy fonts for Islamic content creation and publishing.',
        description_ar: 'خطوط عالية الجودة للطباعة العربية والخط للإنشاء والنشر الإسلامي.',
        resource_type: 'fonts',
        license_type: 'cc-by-nc',
        publisher_name: 'Typography Institute',
        download_count: 2156,
        created_at: '2024-01-28',
        tags: ['fonts', 'typography', 'arabic']
      },
      {
        id: '4',
        title: 'Hadith Corpus Database',
        title_ar: 'عنوان المصدر شرح مختصر الرخصة اسم الناشر',
        description: 'Comprehensive database of authenticated Hadith collections with proper chain of narration verification.',
        description_ar: 'قاعدة بيانات شاملة لمجموعات الأحاديث المصدقة مع التحقق من سلسلة الرواية.',
        resource_type: 'corpus',
        license_type: 'cc-by-sa',
        publisher_name: 'Hadith Research Center',
        download_count: 1456,
        created_at: '2024-02-10',
        tags: ['hadith', 'corpus', 'authentication']
      },
      {
        id: '5',
        title: 'Tafsir Commentary Collection',
        title_ar: 'عنوان المصدر شرح مختصر الرخصة اسم الناشر',
        description: 'Classical and contemporary Tafsir collections from renowned Islamic scholars and institutions.',
        description_ar: 'مجموعات التفسير الكلاسيكية والمعاصرة من علماء ومؤسسات إسلامية مرموقة.',
        resource_type: 'translation',
        license_type: 'cc-by-nd',
        publisher_name: 'Al-Azhar University',
        download_count: 987,
        created_at: '2024-01-20',
        tags: ['tafsir', 'commentary', 'scholarship']
      },
      {
        id: '6',
        title: 'Islamic Art Patterns',
        title_ar: 'عنوان المصدر شرح مختصر الرخصة اسم الناشر',
        description: 'Traditional Islamic geometric patterns and artistic designs for digital and print applications.',
        description_ar: 'الأنماط الهندسية الإسلامية التقليدية والتصاميم الفنية للتطبيقات الرقمية والطباعة.',
        resource_type: 'fonts',
        license_type: 'cc0',
        publisher_name: 'Islamic Arts Museum',
        download_count: 654,
        created_at: '2024-02-05',
        tags: ['art', 'patterns', 'geometry']
      }
    ];
  }

  /**
   * Search functionality
   */
  onSearch() {
    this.currentPage.set(1);
    this.loadResources();
  }

  /**
   * Filter change handlers
   */
  onCategoryChange() {
    this.currentPage.set(1);
    this.loadResources();
  }

  onLicenseChange() {
    this.currentPage.set(1);
    this.loadResources();
  }

  onLanguageChange() {
    this.currentPage.set(1);
    this.loadResources();
  }

  /**
   * Pagination handlers
   */
  onPageChange(page: number) {
    this.currentPage.set(page);
    this.loadResources();
  }

  onPageSizeChange(size: number) {
    this.pageSize = size;
    this.currentPage.set(1);
    this.loadResources();
  }

  /**
   * Modal and Navigation methods
   */
  openAccessRequestModal(resource: Resource): void {
    // Open access request modal for selected resource
    this.selectedResource = {
      ...resource,
      title_en: resource.title || `Resource ${resource.id.slice(0, 8)}`,
      title_ar: resource.title_ar || `