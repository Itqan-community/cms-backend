import { Component, OnInit, inject, signal, effect } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule, ActivatedRoute } from '@angular/router';
import { ReactiveFormsModule, FormsModule } from '@angular/forms';
import { HttpClient, HttpParams } from '@angular/common/http';

// NG-ZORRO Imports
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
import { NzStatisticModule } from 'ng-zorro-antd/statistic';
import { NzBreadCrumbModule } from 'ng-zorro-antd/breadcrumb';

// Services and Models
import { I18nService } from '../../core/services/i18n.service';
import { environment } from '../../../environments/environment.develop';

interface Publisher {
  id: string;
  first_name: string;
  last_name: string;
  email: string;
  profile?: {
    bio_en?: string;
    bio_ar?: string;
    avatar?: string;
    organization?: string;
    organization_ar?: string;
    website?: string;
  };
  created_at: string;
  // Statistics
  stats?: {
    total_resources: number;
    published_resources: number;
    total_downloads: number;
    verified_resources: number;
  };
}

interface Resource {
  id: string;
  title_en: string;
  title_ar: string;
  description_en: string;
  description_ar: string;
  resource_type: 'text' | 'audio' | 'translation' | 'tafsir';
  language: string;
  checksum: string;
  publisher_id: string;
  publisher?: Publisher;
  metadata: Record<string, any>;
  published_at: string | null;
  thumbnail?: string;
  license_type: string;
  download_count?: number;
}

interface PublisherResourcesResponse {
  count: number;
  next?: string;
  previous?: string;
  results: Resource[];
}

/**
 * Publisher Profile Component
 * 
 * Displays publisher information, statistics, and their published resources
 * with advanced filtering capabilities. Supports full Arabic RTL layout.
 */
@Component({
  selector: 'app-publisher-profile',
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
    NzStatisticModule,
    NzBreadCrumbModule
  ],
  template: `
    <div class="publisher-profile-page" [dir]="isArabic() ? 'rtl' : 'ltr'">
      <!-- Breadcrumb Navigation -->
      <div class="breadcrumb-section">
        <nz-breadcrumb>
          <nz-breadcrumb-item>
            <a routerLink="/">{{ t('publisher_profile.home') }}</a>
          </nz-breadcrumb-item>
          <nz-breadcrumb-item>
            <a routerLink="/publishers">{{ t('publisher_profile.publishers') }}</a>
          </nz-breadcrumb-item>
          <nz-breadcrumb-item *ngIf="publisher()">
            <span>{{ getPublisherName(publisher()!) }}</span>
          </nz-breadcrumb-item>
        </nz-breadcrumb>
      </div>

      <!-- Publisher Header Section -->
      <div class="publisher-header-section" *ngIf="!publisherLoading() && publisher()">
        <nz-card class="publisher-header-card" [nzBordered]="false">
          <div class="publisher-header-content">
            <div class="publisher-avatar-section">
              <nz-avatar 
                [nzSize]="120"
                [nzSrc]="publisher()?.profile?.avatar || '/assets/images/default-publisher-avatar.jpg'"
                [nzIcon]="'user'"
                class="publisher-avatar">
              </nz-avatar>
            </div>
            
            <div class="publisher-info-section">
              <h1 class="publisher-name" [class.rtl]="isArabic()">
                {{ getPublisherName(publisher()!) }}
              </h1>
              
              <div class="publisher-organization" *ngIf="getPublisherOrganization(publisher()!)" [class.rtl]="isArabic()">
                <span nz-icon nzType="bank" nzTheme="outline"></span>
                {{ getPublisherOrganization(publisher()!) }}
              </div>
              
              <div class="publisher-bio" *ngIf="getPublisherBio(publisher()!)" [class.rtl]="isArabic()">
                <p>{{ getPublisherBio(publisher()!) }}</p>
              </div>
              
              <div class="publisher-metadata">
                <nz-space nzSize="middle">
                  <span *nzSpaceItem class="metadata-item">
                    <span nz-icon nzType="mail" nzTheme="outline"></span>
                    {{ publisher()?.email }}
                  </span>
                  <span *nzSpaceItem class="metadata-item" [hidden]="!publisher()?.profile?.website">
                    <span nz-icon nzType="global" nzTheme="outline"></span>
                    <a [href]="publisher()?.profile?.website" target="_blank">
                      {{ t('publisher_profile.website') }}
                    </a>
                  </span>
                  <span *nzSpaceItem class="metadata-item">
                    <span nz-icon nzType="calendar" nzTheme="outline"></span>
                    {{ t('publisher_profile.joined') }} {{ formatDate(publisher()?.created_at!) }}
                  </span>
                </nz-space>
              </div>
            </div>

            <!-- Publisher Statistics -->
            <div class="publisher-stats-section">
              <div nz-row [nzGutter]="16" *ngIf="publisher()?.stats">
                <div nz-col [nzSpan]="6">
                  <nz-statistic 
                    [nzTitle]="t('publisher_profile.total_resources')"
                    [nzValue]="publisher()?.stats?.total_resources || 0"
                    [nzValueStyle]="{ color: '#669B80' }">
                  </nz-statistic>
                </div>
                <div nz-col [nzSpan]="6">
                  <nz-statistic 
                    [nzTitle]="t('publisher_profile.published_resources')"
                    [nzValue]="publisher()?.stats?.published_resources || 0"
                    [nzValueStyle]="{ color: '#52c41a' }">
                  </nz-statistic>
                </div>
                <div nz-col [nzSpan]="6">
                  <nz-statistic 
                    [nzTitle]="t('publisher_profile.total_downloads')"
                    [nzValue]="publisher()?.stats?.total_downloads || 0"
                    [nzValueStyle]="{ color: '#1890ff' }">
                  </nz-statistic>
                </div>
                <div nz-col [nzSpan]="6">
                  <nz-statistic 
                    [nzTitle]="t('publisher_profile.verified_resources')"
                    [nzValue]="publisher()?.stats?.verified_resources || 0"
                    [nzValueStyle]="{ color: '#fa8c16' }">
                  </nz-statistic>
                </div>
              </div>
            </div>
          </div>
        </nz-card>
      </div>

      <!-- Loading State for Publisher Info -->
      <div *ngIf="publisherLoading()" class="publisher-loading">
        <nz-spin nzTip="{{ t('publisher_profile.loading_publisher') }}" nzSize="large">
          <nz-card class="publisher-header-card loading-card">
            <div class="loading-content">
              <nz-avatar [nzSize]="120" nzIcon="user"></nz-avatar>
              <div class="loading-text">
                <div class="loading-line"></div>
                <div class="loading-line short"></div>
              </div>
            </div>
          </nz-card>
        </nz-spin>
      </div>

      <!-- Main Content Layout -->
      <nz-layout class="main-layout">
        <!-- Sidebar with Filters -->
        <nz-sider 
          class="filters-sidebar" 
          [nzWidth]="280"
          [nzBreakpoint]="'lg'"
          [nzCollapsedWidth]="0"
          nzTheme="light">
          
          <div class="filters-container">
            <div class="filters-header">
              <h3 class="filters-title">{{ t('publisher_profile.filters') }}</h3>
            </div>
            
            <!-- Resource Type Filter -->
            <div class="filter-section">
              <h4>{{ t('publisher_profile.resource_type') }}</h4>
              <nz-checkbox-group 
                [(ngModel)]="selectedResourceTypes" 
                (ngModelChange)="onResourceTypeChange()">
                <div class="checkbox-item" *ngFor="let type of resourceTypeOptions">
                  <label nz-checkbox [nzValue]="type.value" class="checkbox-label">
                    <span class="checkbox-text">{{ isArabic() ? type.label_ar : type.label_en }}</span>
                    <span class="count">({{ type.count }})</span>
                  </label>
                </div>
              </nz-checkbox-group>
            </div>

            <nz-divider class="filter-divider"></nz-divider>

            <!-- Creative Commons License Filter -->
            <div class="filter-section">
              <h4>{{ t('publisher_profile.creative_commons') }}</h4>
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
              <h4>{{ t('publisher_profile.language') }}</h4>
              <nz-select 
                [(ngModel)]="selectedLanguage"
                (ngModelChange)="onLanguageFilterChange()"
                [nzPlaceHolder]="t('publisher_profile.all_languages')"
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
            <!-- Section Header -->
            <div class="resources-header">
              <h2 class="resources-title" [class.rtl]="isArabic()">
                {{ t('publisher_profile.publisher_resources') }}
              </h2>
              <div class="resources-count">
                <nz-tag [nzColor]="'#669B80'">
                  {{ totalResources() }} {{ t('publisher_profile.resources_found') }}
                </nz-tag>
              </div>
            </div>

            <!-- Loading State -->
            <div *ngIf="resourcesLoading()" class="loading-grid">
                              <nz-spin [nzTip]="t('publisher_profile.loading_resources')" nzSize="large">
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
            <div *ngIf="!resourcesLoading() && resources().length > 0" class="resources-grid-container">
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
                    [nzActions]="[downloadAction]"
                    (click)="viewResource(resource)">
                    
                    <!-- Resource Cover/Thumbnail -->
                    <ng-template #resourceCover>
                      <div class="resource-thumbnail">
                        <img 
                          [src]="resource.thumbnail || '/assets/images/default-resource.jpg'"
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
                        <span class="license-label">{{ t('publisher_profile.license') }}:</span>
                        <nz-tag [nzColor]="getLicenseColor(resource.license_type)">
                          {{ getLocalizedLicense(resource.license_type) }}
                        </nz-tag>
                      </div>
                      
                      <!-- Metadata -->
                      <div class="resource-metadata">
                        <nz-space nzSize="small">
                          <span *nzSpaceItem class="metadata-badge">
                            <span nz-icon nzType="eye" nzTheme="outline"></span>
                            {{ resource.download_count || 0 }}
                          </span>
                          <span *nzSpaceItem class="metadata-badge">
                            <span nz-icon nzType="calendar" nzTheme="outline"></span>
                            {{ formatDate(resource.published_at!) }}
                          </span>
                        </nz-space>
                      </div>
                    </div>

                    <!-- Download Action -->
                    <ng-template #downloadAction>
                      <span nz-icon nzType="download" nzTheme="outline"></span>
                      {{ t('publisher_profile.download') }}
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
                    {{ t('publisher_profile.pagination_total', { total: total, start: range[0], end: range[1] }) }}
                  </ng-template>
                </nz-pagination>
              </div>
            </div>

            <!-- Empty State -->
            <div *ngIf="!resourcesLoading() && resources().length === 0" class="empty-state">
              <nz-empty
                [nzNotFoundContent]="emptyTemplate">
                <ng-template #emptyTemplate>
                  <span>{{ t('publisher_profile.no_resources') }}</span>
                </ng-template>
              </nz-empty>
            </div>
          </div>
        </nz-content>
      </nz-layout>
    </div>
  `,
  styles: [`
    .publisher-profile-page {
      min-height: calc(100vh - 64px);
      background-color: #f5f5f5;
      padding-top: 64px; /* Account for fixed header */
    }

    /* Breadcrumb Section */
    .breadcrumb-section {
      background: #fff;
      padding: 16px 24px;
      border-bottom: 1px solid #f0f0f0;
    }

    [dir="rtl"] .breadcrumb-section {
      text-align: right;
    }

    /* Publisher Header Section */
    .publisher-header-section {
      margin: 20px 24px;
    }

    .publisher-header-card {
      border-radius: 12px;
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
      background: linear-gradient(135deg, #669B80 0%, #22433D 100%);
      color: white;
    }

    .publisher-header-content {
      display: grid;
      grid-template-columns: auto 1fr auto;
      gap: 24px;
      align-items: center;
      padding: 32px;
    }

    [dir="rtl"] .publisher-header-content {
      grid-template-columns: auto 1fr auto;
      text-align: right;
    }

    .publisher-avatar-section {
      display: flex;
      justify-content: center;
    }

    .publisher-avatar {
      border: 4px solid rgba(255, 255, 255, 0.2);
      box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
    }

    .publisher-info-section {
      min-width: 0; /* Allow text truncation */
    }

    .publisher-name {
      font-size: 28px;
      font-weight: 700;
      color: white;
      margin-bottom: 8px;
      line-height: 1.3;
    }

    .publisher-name.rtl {
      font-family: 'Noto Sans Arabic', sans-serif;
      text-align: right;
    }

    .publisher-organization {
      font-size: 16px;
      color: rgba(255, 255, 255, 0.9);
      margin-bottom: 16px;
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .publisher-organization.rtl {
      flex-direction: row-reverse;
      font-family: 'Noto Sans Arabic', sans-serif;
      text-align: right;
    }

    .publisher-bio {
      color: rgba(255, 255, 255, 0.8);
      margin-bottom: 16px;
      line-height: 1.6;
    }

    .publisher-bio.rtl {
      font-family: 'Noto Sans Arabic', sans-serif;
      text-align: right;
    }

    .publisher-metadata .metadata-item {
      color: rgba(255, 255, 255, 0.8);
      font-size: 14px;
      display: flex;
      align-items: center;
      gap: 6px;
    }

    .publisher-metadata .metadata-item a {
      color: rgba(255, 255, 255, 0.9);
      text-decoration: underline;
    }

    [dir="rtl"] .publisher-metadata .metadata-item {
      flex-direction: row-reverse;
    }

    .publisher-stats-section {
      background: rgba(255, 255, 255, 0.1);
      border-radius: 8px;
      padding: 24px;
      min-width: 300px;
    }

    .publisher-stats-section ::ng-deep .ant-statistic-title {
      color: rgba(255, 255, 255, 0.8) !important;
      font-size: 12px;
    }

    .publisher-stats-section ::ng-deep .ant-statistic-content {
      color: white !important;
      font-weight: 600;
    }

    /* Main Layout */
    .main-layout {
      min-height: calc(100vh - 200px);
      background: transparent;
      margin: 0 24px;
    }

    .content-area {
      padding: 24px;
      background: transparent;
    }

    /* Resources Section */
    .resources-section {
      width: 100%;
    }

    .resources-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 24px;
      flex-wrap: wrap;
      gap: 16px;
    }

    .resources-title {
      font-size: 24px;
      font-weight: 600;
      color: #22433D;
      margin: 0;
    }

    .resources-title.rtl {
      font-family: 'Noto Sans Arabic', sans-serif;
      text-align: right;
    }

    .resources-count {
      flex-shrink: 0;
    }

    /* Resource Cards - Same as asset store */
    .resources-grid-container {
      width: 100%;
    }

    .resources-grid {
      width: 100%;
    }

    .resource-card {
      height: 420px;
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

    .resource-metadata {
      display: flex;
      justify-content: space-between;
      align-items: center;
    }

    .metadata-badge {
      display: flex;
      align-items: center;
      gap: 4px;
      color: #999;
      font-size: 12px;
    }

    /* Filters Sidebar - Same as asset store */
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

    /* Pagination */
    .pagination-section {
      display: flex;
      justify-content: center;
      margin-top: 32px;
      padding: 20px;
    }

    /* Loading States */
    .publisher-loading,
    .loading-grid {
      min-height: 300px;
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

    /* RTL Support */
    [dir="rtl"] .resource-overlay {
      right: auto;
      left: 12px;
    }

    [dir="rtl"] .license-info {
      flex-direction: row-reverse;
    }

    [dir="rtl"] .pagination-section {
      direction: rtl;
    }

    [dir="rtl"] .filters-sidebar {
      border-left: none;
      border-right: 1px solid #e8e8e8;
    }

    /* Responsive Design */
    @media (max-width: 1200px) {
      .publisher-header-content {
        grid-template-columns: 1fr;
        text-align: center;
        gap: 16px;
      }

      .publisher-stats-section {
        min-width: auto;
        width: 100%;
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

      .publisher-header-section {
        margin: 16px;
      }
    }

    @media (max-width: 768px) {
      .resource-card {
        height: auto;
        min-height: 350px;
      }
      
      .filters-container {
        padding: 16px;
      }
      
      .filters-title {
        font-size: 16px;
      }

      .publisher-header-content {
        padding: 20px;
      }

      .publisher-name {
        font-size: 22px;
      }
    }

    @media (max-width: 576px) {
      .publisher-profile-page {
        padding-top: 64px;
      }
      
      .resource-card {
        min-height: 300px;
      }

      .breadcrumb-section {
        padding: 12px 16px;
      }
    }
  `]
})
export class PublisherProfileComponent implements OnInit {
  private http = inject(HttpClient);
  private route = inject(ActivatedRoute);
  private i18nService = inject(I18nService);

  // Signals for reactive state
  private readonly _isArabic = signal<boolean>(false);
  private readonly _publisher = signal<Publisher | null>(null);
  private readonly _publisherLoading = signal<boolean>(true);
  private readonly _resources = signal<Resource[]>([]);
  private readonly _resourcesLoading = signal<boolean>(true);
  private readonly _currentPage = signal<number>(1);
  private readonly _totalResources = signal<number>(0);

  // Public reactive properties
  readonly isArabic = this._isArabic.asReadonly();
  readonly publisher = this._publisher.asReadonly();
  readonly publisherLoading = this._publisherLoading.asReadonly();
  readonly resources = this._resources.asReadonly();
  readonly resourcesLoading = this._resourcesLoading.asReadonly();
  readonly currentPage = this._currentPage.asReadonly();
  readonly totalResources = this._totalResources.asReadonly();

  // Filter states
  selectedResourceTypes: string[] = [];
  selectedLicenses: string[] = [];
  selectedLanguage: string | null = null;
  pageSize = 24;

  // Publisher ID from route
  publisherId: string | null = null;

  // Filter options
  resourceTypeOptions = [
    { value: 'text', label_en: 'Quranic Text', label_ar: 'النص القرآني', count: 0 },
    { value: 'audio', label_en: 'Audio Recitation', label_ar: 'التلاوة الصوتية', count: 0 },
    { value: 'translation', label_en: 'Translation', label_ar: 'الترجمة', count: 0 },
    { value: 'tafsir', label_en: 'Tafsir/Commentary', label_ar: 'التفسير', count: 0 }
  ];

  creativeCommonsOptions = [
    { value: 'CC0', icon: 'CC0', label_en: 'Public Domain', label_ar: 'الملكية العامة', count: 0 },
    { value: 'CC-BY', icon: '©️', label_en: 'Attribution', label_ar: 'مع الإسناد', count: 0 },
    { value: 'CC-BY-SA', icon: '🔄', label_en: 'Attribution ShareAlike', label_ar: 'مع الإسناد والمشاركة', count: 0 },
    { value: 'CC-BY-NC', icon: '💰', label_en: 'Attribution Non-Commercial', label_ar: 'مع الإسناد غير التجاري', count: 0 },
    { value: 'CC-BY-ND', icon: '🔒', label_en: 'Attribution No-Derivatives', label_ar: 'مع الإسناد بلا تعديل', count: 0 },
    { value: 'CC-BY-NC-SA', icon: '🔄💰', label_en: 'Attribution Non-Commercial ShareAlike', label_ar: 'إسناد-غيرتجاري-مشاركة', count: 0 },
    { value: 'CC-BY-NC-ND', icon: '💰🔒', label_en: 'Attribution Non-Commercial No-Derivatives', label_ar: 'إسناد-غيرتجاري-لاتعديل', count: 0 }
  ];

  languageOptions = [
    { value: 'ar', label_en: 'Arabic', label_ar: 'العربية' },
    { value: 'en', label_en: 'English', label_ar: 'الإنجليزية' },
    { value: 'ur', label_en: 'Urdu', label_ar: 'الأردية' },
    { value: 'fa', label_en: 'Persian', label_ar: 'الفارسية' },
    { value: 'tr', label_en: 'Turkish', label_ar: 'التركية' },
    { value: 'id', label_en: 'Indonesian', label_ar: 'الإندونيسية' }
  ];

  constructor() {
    // Language detection effect
    effect(() => {
      this._isArabic.set(this.i18nService.currentLanguage() === 'ar');
    });
  }

  ngOnInit() {
    // Get publisher ID from route params
    this.route.paramMap.subscribe(params => {
      const id = params.get('publisherId');
      if (id) {
        this.publisherId = id;
        this.loadPublisher();
        this.loadResources();
      }
    });
  }

  /**
   * Load publisher information
   */
  private async loadPublisher(): Promise<void> {
    if (!this.publisherId) return;

    this._publisherLoading.set(true);
    
    try {
      const response = await this.http.get<Publisher>(`${environment.apiUrl}/accounts/users/${this.publisherId}/`).toPromise();
      
      if (response) {
        // Simulate statistics (in real implementation, these would come from backend)
        response.stats = {
          total_resources: 24,
          published_resources: 18,
          total_downloads: 1250,
          verified_resources: 16
        };
        
        this._publisher.set(response);
      }
    } catch (error) {
      console.error('Error loading publisher:', error);
      // Handle error appropriately
    } finally {
      this._publisherLoading.set(false);
    }
  }

  /**
   * Load publisher resources with filtering
   */
  private async loadResources(): Promise<void> {
    if (!this.publisherId) return;

    this._resourcesLoading.set(true);
    
    try {
      let params = new HttpParams()
        .set('publisher', this.publisherId)
        .set('page', this._currentPage().toString())
        .set('page_size', this.pageSize.toString())
        .set('is_published', 'true')
        .set('is_active', 'true');

      // Add filters
      if (this.selectedResourceTypes.length > 0) {
        this.selectedResourceTypes.forEach(type => {
          params = params.append('resource_type', type);
        });
      }
      
      if (this.selectedLicenses.length > 0) {
        this.selectedLicenses.forEach(license => {
          params = params.append('license_type', license);
        });
      }
      
      if (this.selectedLanguage) {
        params = params.set('language', this.selectedLanguage);
      }

      const response = await this.http.get<PublisherResourcesResponse>(`${environment.apiUrl}/content/resources/`, { params }).toPromise();
      
      if (response) {
        // Add bilingual properties and simulate some data
        const enhancedResources = response.results.map(resource => ({
          ...resource,
          title_en: resource.metadata?.['title_en'] || `Resource ${resource.id.slice(0, 8)}`,
          title_ar: resource.metadata?.['title_ar'] || `المورد ${resource.id.slice(0, 8)}`,
          description_en: resource.metadata?.['description_en'] || 'Islamic content resource with scholarly authentication.',
          description_ar: resource.metadata?.['description_ar'] || 'مورد محتوى إسلامي مع المصادقة العلمية.',
          download_count: Math.floor(Math.random() * 500) + 10,
          license_type: this.creativeCommonsOptions[Math.floor(Math.random() * this.creativeCommonsOptions.length)].value
        }));

        this._resources.set(enhancedResources);
        this._totalResources.set(response.count);
      }
    } catch (error) {
      console.error('Error loading resources:', error);
      // Simulate data for demonstration
      this.simulateResourceData();
    } finally {
      this._resourcesLoading.set(false);
    }
  }

  /**
   * Simulate resource data for demonstration
   */
  private simulateResourceData(): void {
    const mockResources: Resource[] = Array.from({ length: 24 }, (_, index) => ({
      id: `resource-${index + 1}`,
      title_en: `Quranic Resource ${index + 1}`,
      title_ar: `المورد القرآني ${index + 1}`,
      description_en: 'Authentic Islamic content with scholarly verification and proper licensing.',
      description_ar: 'محتوى إسلامي أصيل مع التحقق العلمي والترخيص المناسب.',
      resource_type: this.resourceTypeOptions[Math.floor(Math.random() * this.resourceTypeOptions.length)].value as any,
      language: this.languageOptions[Math.floor(Math.random() * this.languageOptions.length)].value,
      checksum: `sha256-${Math.random().toString(36).substring(2)}`,
      publisher_id: this.publisherId!,
      metadata: {},
      published_at: new Date(Date.now() - Math.random() * 365 * 24 * 60 * 60 * 1000).toISOString(),
      license_type: this.creativeCommonsOptions[Math.floor(Math.random() * this.creativeCommonsOptions.length)].value,
      download_count: Math.floor(Math.random() * 500) + 10
    }));

    this._resources.set(mockResources);
    this._totalResources.set(24);
  }

  // Event handlers
  onResourceTypeChange(): void {
    this._currentPage.set(1);
    this.loadResources();
  }

  onLicenseChange(): void {
    this._currentPage.set(1);
    this.loadResources();
  }

  onLanguageFilterChange(): void {
    this._currentPage.set(1);
    this.loadResources();
  }

  onPageChange(page: number): void {
    this._currentPage.set(page);
    this.loadResources();
  }

  onPageSizeChange(size: number): void {
    this.pageSize = size;
    this._currentPage.set(1);
    this.loadResources();
  }

  // Helper methods
  getPublisherName(publisher: Publisher): string {
    return `${publisher.first_name} ${publisher.last_name}`.trim() || publisher.email;
  }

  getPublisherOrganization(publisher: Publisher): string {
    if (!publisher.profile) return '';
    return this.isArabic() ? (publisher.profile.organization_ar || publisher.profile.organization || '') : (publisher.profile.organization || '');
  }

  getPublisherBio(publisher: Publisher): string {
    if (!publisher.profile) return '';
    return this.isArabic() ? (publisher.profile.bio_ar || publisher.profile.bio_en || '') : (publisher.profile.bio_en || '');
  }

  getLocalizedTitle(resource: Resource): string {
    return this.isArabic() ? resource.title_ar : resource.title_en;
  }

  getLocalizedDescription(resource: Resource): string {
    return this.isArabic() ? resource.description_ar : resource.description_en;
  }

  getLocalizedResourceType(type: string): string {
    const typeOption = this.resourceTypeOptions.find(opt => opt.value === type);
    return typeOption ? (this.isArabic() ? typeOption.label_ar : typeOption.label_en) : type;
  }

  getLocalizedLicense(license: string): string {
    const licenseOption = this.creativeCommonsOptions.find(opt => opt.value === license);
    return licenseOption ? (this.isArabic() ? licenseOption.label_ar : licenseOption.label_en) : license;
  }

  getResourceTypeColor(type: string): string {
    const colors: Record<string, string> = {
      'text': '#669B80',
      'audio': '#1890ff',
      'translation': '#fa8c16',
      'tafsir': '#722ed1'
    };
    return colors[type] || '#8c8c8c';
  }

  getResourceTypeIcon(type: string): string {
    const icons: Record<string, string> = {
      'text': 'file-text',
      'audio': 'sound',
      'translation': 'global',
      'tafsir': 'book'
    };
    return icons[type] || 'file';
  }

  getLicenseColor(license: string): string {
    const colors: Record<string, string> = {
      'CC0': '#52c41a',
      'CC-BY': '#1890ff',
      'CC-BY-SA': '#722ed1',
      'CC-BY-NC': '#fa8c16',
      'CC-BY-ND': '#f5222d',
      'CC-BY-NC-SA': '#eb2f96',
      'CC-BY-NC-ND': '#a0d911'
    };
    return colors[license] || '#8c8c8c';
  }

  formatDate(dateString: string): string {
    const date = new Date(dateString);
    return date.toLocaleDateString(this.isArabic() ? 'ar-SA' : 'en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric'
    });
  }

  viewResource(resource: Resource): void {
    // Navigate to resource detail page or open modal
    console.log('Viewing resource:', resource);
  }

  trackByResourceId(index: number, resource: Resource): string {
    return resource.id;
  }

  /**
   * Translation helper method
   */
  t(key: string, params?: any): string {
    return this.i18nService.translate(key, params);
  }
}
