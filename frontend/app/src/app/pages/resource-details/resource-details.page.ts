import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { CardModule } from 'primeng/card';
import { ButtonModule } from 'primeng/button';
import { ChipModule } from 'primeng/chip';
import { TabViewModule } from 'primeng/tabview';
import { TableModule } from 'primeng/table';
import { TagModule } from 'primeng/tag';
import { RouterLink } from '@angular/router';
import { TranslationService } from '../../shared/translation.service';

@Component({
  standalone: true,
  selector: 'app-resource-details',
  imports: [CommonModule, CardModule, ButtonModule, ChipModule, TabViewModule, TableModule, TagModule, RouterLink],
  template: `
    <div class="resource-details-page">
      <!-- Breadcrumb Navigation -->
      <div class="breadcrumb-section bg-surface py-3">
        <div class="container">
          <nav class="breadcrumb">
            <a routerLink="/home-auth" class="breadcrumb-item">Home</a>
            <span class="breadcrumb-separator">/</span>
            <a routerLink="/publishers/itqan" class="breadcrumb-item">Publishers</a>
            <span class="breadcrumb-separator">/</span>
            <span class="breadcrumb-current">{{ resource.title }}</span>
          </nav>
        </div>
      </div>

      <div class="container py-6">
        <!-- Resource Header -->
        <div class="resource-header mb-6">
          <div class="row">
            <div class="col-8">
              <div class="resource-info">
                <h1 class="resource-title text-dark mb-3">{{ resource.title }}</h1>
                <p class="resource-description text-muted mb-4">{{ resource.description }}</p>
                
                <!-- Tags and Metadata -->
                <div class="resource-tags mb-4">
                  <p-chip [label]="resource.license" 
                          [style]="{'background-color': '#e3f2fd', 'color': '#1976d2'}" 
                          class="me-2"></p-chip>
                  <p-chip [label]="resource.language" 
                          [style]="{'background-color': '#f3e5f5', 'color': '#7b1fa2'}" 
                          class="me-2"></p-chip>
                  <p-chip [label]="resource.version" 
                          [style]="{'background-color': '#e8f5e8', 'color': '#388e3c'}" 
                          class="me-2"></p-chip>
                  <p-chip [label]="resource.format" 
                          [style]="{'background-color': '#fff3e0', 'color': '#f57c00'}" 
                          class="me-2"></p-chip>
                </div>

                <!-- Stats -->
                <div class="resource-stats flex gap-4">
                  <div class="stat-item">
                    <i class="pi pi-download me-2"></i>
                    <span>{{ resource.downloads }} downloads</span>
                  </div>
                  <div class="stat-item">
                    <i class="pi pi-calendar me-2"></i>
                    <span>Updated {{ resource.lastUpdated }}</span>
                  </div>
                  <div class="stat-item">
                    <i class="pi pi-database me-2"></i>
                    <span>{{ resource.size }}</span>
                  </div>
                </div>
              </div>
            </div>
            
            <div class="col-4">
              <div class="resource-actions">
                <p-card class="action-card">
                  <div class="action-buttons">
                    <button pButton label="Download Resource" 
                            icon="pi pi-download" 
                            class="w-full mb-3 download-btn"></button>
                    
                    <button pButton label="View API Documentation" 
                            icon="pi pi-book" 
                            [outlined]="true" 
                            class="w-full mb-3"></button>
                    
                    <a routerLink="/demo/license-terms-dialog" 
                       pButton label="License Details" 
                       icon="pi pi-info-circle" 
                       [outlined]="true" 
                       class="w-full mb-3"></a>
                    
                    <button pButton label="Report Issue" 
                            icon="pi pi-exclamation-triangle" 
                            severity="secondary" 
                            [outlined]="true" 
                            class="w-full"></button>
                  </div>
                </p-card>
              </div>
            </div>
          </div>
        </div>

        <!-- Resource Content Tabs -->
        <div class="resource-content">
          <p-tabView>
            <!-- Overview Tab -->
            <p-tabPanel header="Overview">
              <div class="row">
                <div class="col-8">
                  <div class="overview-content">
                    <h3 class="mb-3">About this Resource</h3>
                    <p class="mb-4">{{ resource.longDescription }}</p>
                    
                    <h4 class="mb-3">Key Features</h4>
                    <ul class="feature-list mb-4">
                      <li *ngFor="let feature of resource.features">{{ feature }}</li>
                    </ul>
                    
                    <h4 class="mb-3">Usage Examples</h4>
                    <div class="code-example">
                      <pre><code>{{ resource.usageExample }}</code></pre>
                    </div>
                  </div>
                </div>
                
                <div class="col-4">
                  <div class="resource-sidebar">
                    <p-card header="Resource Information">
                      <div class="info-list">
                        <div class="info-item">
                          <strong>Publisher:</strong>
                          <a routerLink="/publishers/itqan" class="text-primary">{{ resource.publisher }}</a>
                        </div>
                        <div class="info-item">
                          <strong>Category:</strong>
                          <span>{{ resource.category }}</span>
                        </div>
                        <div class="info-item">
                          <strong>Created:</strong>
                          <span>{{ resource.createdDate }}</span>
                        </div>
                        <div class="info-item">
                          <strong>File Format:</strong>
                          <span>{{ resource.fileFormat }}</span>
                        </div>
                        <div class="info-item">
                          <strong>Encoding:</strong>
                          <span>{{ resource.encoding }}</span>
                        </div>
                        <div class="info-item">
                          <strong>Checksum:</strong>
                          <span class="checksum">{{ resource.checksum }}</span>
                        </div>
                      </div>
                    </p-card>
                  </div>
                </div>
              </div>
            </p-tabPanel>

            <!-- Files Tab -->
            <p-tabPanel header="Files">
              <p-table [value]="resource.files" [paginator]="false">
                <ng-template pTemplate="header">
                  <tr>
                    <th>Filename</th>
                    <th>Size</th>
                    <th>Format</th>
                    <th>Last Modified</th>
                    <th>Actions</th>
                  </tr>
                </ng-template>
                <ng-template pTemplate="body" let-file>
                  <tr>
                    <td>
                      <div class="file-info">
                        <i class="pi pi-file me-2"></i>
                        <strong>{{ file.name }}</strong>
                      </div>
                    </td>
                    <td>{{ file.size }}</td>
                    <td>
                      <p-tag [value]="file.format" severity="info"></p-tag>
                    </td>
                    <td>{{ file.lastModified }}</td>
                    <td>
                      <button pButton icon="pi pi-download" 
                              size="small" 
                              [outlined]="true" 
                              class="me-2"></button>
                      <button pButton icon="pi pi-eye" 
                              size="small" 
                              [outlined]="true"></button>
                    </td>
                  </tr>
                </ng-template>
              </p-table>
            </p-tabPanel>

            <!-- Changelog Tab -->
            <p-tabPanel header="Changelog">
              <div class="changelog-content">
                <div *ngFor="let version of resource.changelog" class="version-entry mb-4">
                  <div class="version-header">
                    <h4 class="version-number">{{ version.version }}</h4>
                    <span class="version-date text-muted">{{ version.date }}</span>
                  </div>
                  <ul class="version-changes">
                    <li *ngFor="let change of version.changes">{{ change }}</li>
                  </ul>
                </div>
              </div>
            </p-tabPanel>

            <!-- Related Resources Tab -->
            <p-tabPanel header="Related Resources">
              <div class="related-resources">
                <div class="row">
                  <div *ngFor="let related of resource.relatedResources" class="col-4 mb-4">
                    <p-card class="related-card">
                      <div class="related-info">
                        <h5 class="mb-2">{{ related.title }}</h5>
                        <p class="text-muted mb-3">{{ related.description }}</p>
                        <div class="related-tags mb-3">
                          <p-chip [label]="related.type" size="small" class="me-1"></p-chip>
                        </div>
                        <a [routerLink]="['/resources', related.id]" 
                           pButton label="View Resource" 
                           size="small" 
                           [outlined]="true"></a>
                      </div>
                    </p-card>
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
    .resource-details-page {
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

    /* Resource Header */
    .resource-header {
      background: white;
      border-radius: 0.5rem;
      padding: 2rem;
      box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }

    .resource-title {
      font-size: 2rem;
      font-weight: 700;
    }

    .resource-description {
      font-size: 1.125rem;
      line-height: 1.6;
    }

    .resource-tags {
      display: flex;
      flex-wrap: wrap;
      gap: 0.5rem;
    }

    .resource-stats {
      color: #6c757d;
      font-size: 0.875rem;
    }

    .stat-item {
      display: flex;
      align-items: center;
    }

    /* Action Card */
    .action-card {
      position: sticky;
      top: 2rem;
    }

    .download-btn {
      background: var(--p-primary-500);
      border-color: var(--p-primary-500);
    }

    /* Content Tabs */
    .resource-content {
      background: white;
      border-radius: 0.5rem;
      box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }

    .overview-content h3,
    .overview-content h4 {
      color: #333;
    }

    .feature-list {
      padding-left: 1.5rem;
    }

    .feature-list li {
      margin-bottom: 0.5rem;
      line-height: 1.5;
    }

    .code-example {
      background: #f8f9fa;
      border: 1px solid #e9ecef;
      border-radius: 0.25rem;
      padding: 1rem;
      margin: 1rem 0;
    }

    .code-example pre {
      margin: 0;
      font-family: 'Courier New', monospace;
      font-size: 0.875rem;
      color: #495057;
    }

    /* Sidebar */
    .resource-sidebar {
      position: sticky;
      top: 2rem;
    }

    .info-list {
      display: flex;
      flex-direction: column;
      gap: 1rem;
    }

    .info-item {
      display: flex;
      flex-direction: column;
      gap: 0.25rem;
    }

    .info-item strong {
      font-size: 0.875rem;
      color: #6c757d;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }

    .checksum {
      font-family: monospace;
      font-size: 0.75rem;
      word-break: break-all;
    }

    /* Files Table */
    .file-info {
      display: flex;
      align-items: center;
    }

    /* Changelog */
    .version-entry {
      border-left: 3px solid var(--p-primary-500);
      padding-left: 1rem;
    }

    .version-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 0.5rem;
    }

    .version-number {
      margin: 0;
      color: var(--p-primary-500);
    }

    .version-changes {
      padding-left: 1.5rem;
    }

    .version-changes li {
      margin-bottom: 0.25rem;
    }

    /* Related Resources */
    .related-card {
      height: 100%;
      transition: transform 0.2s;
    }

    .related-card:hover {
      transform: translateY(-2px);
    }

    .related-info h5 {
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

      .resource-header {
        padding: 1rem;
      }

      .resource-title {
        font-size: 1.5rem;
      }

      .resource-stats {
        flex-direction: column;
        align-items: flex-start;
        gap: 0.5rem;
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
  `]
})
export class ResourceDetailsPage {
  private translationService = inject(TranslationService);
  t = this.translationService.t;

  resource = {
    id: 'quran-uthmani-hafs',
    title: 'Quran Text - Uthmani Script (Hafs)',
    description: 'Complete Quranic text in Uthmani script following the Hafs recitation method with full diacritical marks.',
    longDescription: 'This comprehensive resource contains the complete text of the Holy Quran in the traditional Uthmani script, meticulously prepared following the Hafs recitation method. The text includes full diacritical marks (Tashkeel) and has been verified against multiple authentic sources. This resource is ideal for developers building Quranic applications, researchers studying Islamic texts, and educational platforms.',
    license: 'CC0 1.0',
    language: 'Arabic',
    version: 'v2.1.0',
    format: 'JSON/XML',
    downloads: 15847,
    lastUpdated: '2 weeks ago',
    size: '2.4 MB',
    publisher: 'Itqan Foundation',
    category: 'Quranic Text',
    createdDate: 'January 15, 2023',
    fileFormat: 'UTF-8 JSON, XML',
    encoding: 'Unicode (UTF-8)',
    checksum: 'sha256:a1b2c3d4e5f6...',
    features: [
      'Complete 114 chapters (Surahs) with 6,236 verses (Ayahs)',
      'Full diacritical marks (Harakat) for proper pronunciation',
      'Verse-by-verse structure with metadata',
      'Chapter information including names and revelation details',
      'Multiple output formats (JSON, XML, CSV)',
      'Verified against Mushaf Al-Madinah An-Nabawiyah',
      'API-ready structure for easy integration',
      'Comprehensive documentation and examples'
    ],
    usageExample: `// Example API call
fetch('/api/quran/2/255')
  .then(response => response.json())
  .then(data => {
    console.log(data.arabic_text);
    console.log(data.transliteration);
  });

// Example response
{
  "surah": 2,
  "ayah": 255,
  "arabic_text": "اللَّهُ لَا إِلَٰهَ إِلَّا هُوَ الْحَيُّ الْقَيُّومُ...",
  "transliteration": "Allahu la ilaha illa huwa al-hayyu al-qayyum..."
}`,
    files: [
      {
        name: 'quran-uthmani-complete.json',
        size: '1.8 MB',
        format: 'JSON',
        lastModified: '2024-01-15'
      },
      {
        name: 'quran-uthmani-complete.xml',
        size: '2.1 MB',
        format: 'XML',
        lastModified: '2024-01-15'
      },
      {
        name: 'quran-chapters-metadata.json',
        size: '45 KB',
        format: 'JSON',
        lastModified: '2024-01-15'
      },
      {
        name: 'documentation.pdf',
        size: '890 KB',
        format: 'PDF',
        lastModified: '2024-01-10'
      }
    ],
    changelog: [
      {
        version: 'v2.1.0',
        date: 'January 15, 2024',
        changes: [
          'Added comprehensive metadata for each chapter',
          'Improved Unicode normalization',
          'Fixed minor diacritical mark inconsistencies',
          'Added API documentation examples'
        ]
      },
      {
        version: 'v2.0.0',
        date: 'December 1, 2023',
        changes: [
          'Complete restructure of JSON format',
          'Added XML output format',
          'Improved verse numbering system',
          'Enhanced documentation'
        ]
      },
      {
        version: 'v1.5.2',
        date: 'October 15, 2023',
        changes: [
          'Fixed encoding issues in specific verses',
          'Updated license to CC0 1.0',
          'Added checksum verification'
        ]
      }
    ],
    relatedResources: [
      {
        id: 'quran-translations-english',
        title: 'Quran Translations - English',
        description: 'Multiple English translations of the Quran including Sahih International, Pickthall, and Yusuf Ali.',
        type: 'Translation'
      },
      {
        id: 'quran-audio-mishary',
        title: 'Quran Audio - Mishary Rashid',
        description: 'High-quality audio recitation by Sheikh Mishary Rashid Al-Afasy in MP3 format.',
        type: 'Audio'
      },
      {
        id: 'tafseer-ibn-kathir',
        title: 'Tafseer Ibn Kathir',
        description: 'Classical commentary on the Quran by the renowned scholar Ibn Kathir.',
        type: 'Commentary'
      }
    ]
  };
}


