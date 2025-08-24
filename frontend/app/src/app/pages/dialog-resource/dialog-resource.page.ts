import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { DialogModule } from 'primeng/dialog';
import { ButtonModule } from 'primeng/button';
import { ChipModule } from 'primeng/chip';
import { TagModule } from 'primeng/tag';
import { TabViewModule } from 'primeng/tabview';
import { DividerModule } from 'primeng/divider';
import { Router, RouterLink } from '@angular/router';
import { TranslationService } from '../../shared/translation.service';

@Component({
  standalone: true,
  selector: 'app-dialog-resource',
  imports: [CommonModule, DialogModule, ButtonModule, ChipModule, TagModule, TabViewModule, DividerModule, RouterLink],
  template: `
    <div class="dialog-demo-page">
      <div class="container py-6">
        <div class="demo-header mb-4">
          <h2>Resource Details Modal Demo</h2>
          <p class="text-muted">This demonstrates the resource details popup as shown in wireframe 4a</p>
          <button pButton label="Open Resource Dialog" (click)="openDialog()" class="mb-4"></button>
        </div>

        <!-- Resource Details Modal Dialog -->
        <p-dialog [(visible)]="visible" 
                  [modal]="true" 
                  header="Resource Details" 
                  [style]="{width: '90vw', maxWidth: '1000px'}" 
                  [draggable]="false" 
                  [resizable]="false"
                  [closable]="true"
                  styleClass="resource-dialog">
          
          <!-- Dialog Content -->
          <div class="dialog-content">
            <!-- Resource Header -->
            <div class="resource-header mb-4">
              <div class="resource-title-section">
                <h3 class="resource-title mb-2">{{ resource.title }}</h3>
                <p class="resource-description text-muted mb-3">{{ resource.description }}</p>
                
                <!-- Resource Tags -->
                <div class="resource-tags mb-3">
                  <p-chip [label]="resource.license" 
                          [style]="{'background-color': '#e3f2fd', 'color': '#1976d2'}" 
                          class="me-2"></p-chip>
                  <p-chip [label]="resource.language" 
                          [style]="{'background-color': '#f3e5f5', 'color': '#7b1fa2'}" 
                          class="me-2"></p-chip>
                  <p-chip [label]="resource.version" 
                          [style]="{'background-color': '#e8f5e8', 'color': '#388e3c'}" 
                          class="me-2"></p-chip>
                  <p-tag [value]="resource.type" 
                         [style]="{'background-color': '#fff3e0', 'color': '#f57c00'}"></p-tag>
                </div>

                <!-- Resource Stats -->
                <div class="resource-stats flex gap-4">
                  <div class="stat-item">
                    <i class="pi pi-download me-1"></i>
                    <span>{{ resource.downloads }} downloads</span>
                  </div>
                  <div class="stat-item">
                    <i class="pi pi-calendar me-1"></i>
                    <span>Updated {{ resource.lastUpdated }}</span>
                  </div>
                  <div class="stat-item">
                    <i class="pi pi-database me-1"></i>
                    <span>{{ resource.size }}</span>
                  </div>
                  <div class="stat-item">
                    <i class="pi pi-star me-1"></i>
                    <span>{{ resource.rating }}/5</span>
                  </div>
                </div>
              </div>
            </div>

            <p-divider></p-divider>

            <!-- Dialog Tabs -->
            <p-tabView>
              <!-- Quick Info Tab -->
              <p-tabPanel header="Quick Info">
                <div class="quick-info-content">
                  <div class="row">
                    <div class="col-6">
                      <h4 class="mb-3">Resource Information</h4>
                      <div class="info-list">
                        <div class="info-item">
                          <strong>Publisher:</strong>
                          <span>{{ resource.publisher }}</span>
                        </div>
                        <div class="info-item">
                          <strong>Category:</strong>
                          <span>{{ resource.category }}</span>
                        </div>
                        <div class="info-item">
                          <strong>Format:</strong>
                          <span>{{ resource.format }}</span>
                        </div>
                        <div class="info-item">
                          <strong>Encoding:</strong>
                          <span>{{ resource.encoding }}</span>
                        </div>
                        <div class="info-item">
                          <strong>Created:</strong>
                          <span>{{ resource.createdDate }}</span>
                        </div>
                      </div>
                    </div>
                    
                    <div class="col-6">
                      <h4 class="mb-3">Key Features</h4>
                      <ul class="features-list">
                        <li *ngFor="let feature of resource.keyFeatures">{{ feature }}</li>
                      </ul>
                      
                      <h4 class="mb-3 mt-4">Usage Example</h4>
                      <div class="code-example">
                        <pre><code>{{ resource.quickExample }}</code></pre>
                      </div>
                    </div>
                  </div>
                </div>
              </p-tabPanel>

              <!-- Files Tab -->
              <p-tabPanel header="Files ({{ resource.files.length }})">
                <div class="files-content">
                  <div class="files-list">
                    <div *ngFor="let file of resource.files" class="file-item">
                      <div class="file-info">
                        <div class="file-icon">
                          <i class="pi pi-file"></i>
                        </div>
                        <div class="file-details">
                          <h5 class="file-name">{{ file.name }}</h5>
                          <p class="file-meta text-muted">{{ file.size }} • {{ file.format }} • {{ file.lastModified }}</p>
                        </div>
                      </div>
                      <div class="file-actions">
                        <button pButton icon="pi pi-download" 
                                size="small" 
                                [outlined]="true" 
                                pTooltip="Download"
                                class="me-1"></button>
                        <button pButton icon="pi pi-eye" 
                                size="small" 
                                [outlined]="true" 
                                pTooltip="Preview"></button>
                      </div>
                    </div>
                  </div>
                </div>
              </p-tabPanel>

              <!-- License Tab -->
              <p-tabPanel header="License">
                <div class="license-content">
                  <div class="license-summary mb-4">
                    <h4 class="mb-2">{{ resource.licenseDetails.name }}</h4>
                    <p class="text-muted mb-3">{{ resource.licenseDetails.summary }}</p>
                  </div>

                  <div class="row">
                    <div class="col-4">
                      <div class="license-section">
                        <h5 class="text-success mb-2">✅ Permissions</h5>
                        <ul class="license-list">
                          <li *ngFor="let permission of resource.licenseDetails.permissions">{{ permission }}</li>
                        </ul>
                      </div>
                    </div>
                    
                    <div class="col-4">
                      <div class="license-section">
                        <h5 class="text-warning mb-2">⚠️ Conditions</h5>
                        <ul class="license-list">
                          <li *ngFor="let condition of resource.licenseDetails.conditions">{{ condition }}</li>
                        </ul>
                      </div>
                    </div>
                    
                    <div class="col-4">
                      <div class="license-section">
                        <h5 class="text-danger mb-2">❌ Limitations</h5>
                        <ul class="license-list">
                          <li *ngFor="let limitation of resource.licenseDetails.limitations">{{ limitation }}</li>
                        </ul>
                      </div>
                    </div>
                  </div>

                  <div class="license-actions mt-4">
                    <button pButton label="View Full License" 
                            [outlined]="true" 
                            class="me-2"></button>
                    <button pButton label="Download License Text" 
                            icon="pi pi-download" 
                            [outlined]="true"></button>
                  </div>
                </div>
              </p-tabPanel>
            </p-tabView>
          </div>

          <!-- Dialog Footer -->
          <ng-template pTemplate="footer">
            <div class="dialog-footer">
              <div class="footer-actions">
                <button pButton label="Download Resource" 
                        icon="pi pi-download" 
                        class="download-btn me-2"></button>
                <a routerLink="/resources/123" 
                   pButton label="View Full Details" 
                   [outlined]="true" 
                   class="me-2"
                   (click)="close()"></a>
                <button pButton label="Close" 
                        [outlined]="true" 
                        (click)="close()"></button>
              </div>
            </div>
          </ng-template>
        </p-dialog>
      </div>
    </div>
  `,
  styles: [`
    .dialog-demo-page {
      min-height: 100vh;
      background: #f8f9fa;
    }

    .demo-header {
      text-align: center;
      padding: 2rem;
      background: white;
      border-radius: 0.5rem;
      box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }

    /* Dialog Styles */
    :host ::ng-deep .resource-dialog .p-dialog-content {
      padding: 0;
    }

    :host ::ng-deep .resource-dialog .p-dialog-header {
      background: var(--p-primary-500);
      color: white;
      border-radius: 0.5rem 0.5rem 0 0;
    }

    :host ::ng-deep .resource-dialog .p-dialog-header .p-dialog-title {
      color: white;
      font-weight: 600;
    }

    :host ::ng-deep .resource-dialog .p-dialog-header .p-dialog-header-icon {
      color: white;
    }

    .dialog-content {
      padding: 1.5rem;
    }

    /* Resource Header */
    .resource-header {
      border-bottom: 1px solid #dee2e6;
      padding-bottom: 1rem;
    }

    .resource-title {
      font-size: 1.5rem;
      font-weight: 700;
      color: #333;
      margin: 0;
    }

    .resource-description {
      font-size: 1rem;
      line-height: 1.5;
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

    /* Quick Info */
    .info-list {
      display: flex;
      flex-direction: column;
      gap: 0.75rem;
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

    .features-list {
      padding-left: 1.25rem;
      margin: 0;
    }

    .features-list li {
      margin-bottom: 0.5rem;
      line-height: 1.4;
    }

    .code-example {
      background: #f8f9fa;
      border: 1px solid #dee2e6;
      border-radius: 0.25rem;
      padding: 0.75rem;
    }

    .code-example pre {
      margin: 0;
      font-family: 'Courier New', monospace;
      font-size: 0.75rem;
      color: #495057;
    }

    /* Files */
    .files-list {
      display: flex;
      flex-direction: column;
      gap: 1rem;
    }

    .file-item {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 1rem;
      background: #f8f9fa;
      border-radius: 0.5rem;
      border: 1px solid #dee2e6;
    }

    .file-info {
      display: flex;
      align-items: center;
      gap: 1rem;
    }

    .file-icon {
      width: 40px;
      height: 40px;
      background: var(--p-primary-500);
      color: white;
      border-radius: 0.25rem;
      display: flex;
      align-items: center;
      justify-content: center;
    }

    .file-name {
      margin: 0 0 0.25rem 0;
      font-size: 1rem;
      font-weight: 600;
    }

    .file-meta {
      margin: 0;
      font-size: 0.875rem;
    }

    .file-actions {
      display: flex;
      gap: 0.5rem;
    }

    /* License */
    .license-section h5 {
      font-weight: 600;
    }

    .license-list {
      padding-left: 1rem;
      margin: 0;
    }

    .license-list li {
      margin-bottom: 0.5rem;
      font-size: 0.875rem;
      line-height: 1.4;
    }

    .license-actions {
      text-align: center;
      padding-top: 1rem;
      border-top: 1px solid #dee2e6;
    }

    /* Dialog Footer */
    .dialog-footer {
      padding: 1rem 1.5rem;
      background: #f8f9fa;
      border-top: 1px solid #dee2e6;
    }

    .footer-actions {
      display: flex;
      justify-content: flex-end;
      align-items: center;
    }

    .download-btn {
      background: var(--p-primary-500);
      border-color: var(--p-primary-500);
    }

    /* Grid System */
    .col-4 {
      flex: 0 0 33.333333%;
      max-width: 33.333333%;
    }

    .col-6 {
      flex: 0 0 50%;
      max-width: 50%;
    }

    /* Responsive */
    @media (max-width: 768px) {
      .col-4, .col-6 {
        flex: 0 0 100%;
        max-width: 100%;
      }

      .resource-stats {
        flex-direction: column;
        align-items: flex-start;
        gap: 0.5rem;
      }

      .footer-actions {
        flex-direction: column;
        gap: 0.5rem;
      }

      .footer-actions button,
      .footer-actions a {
        width: 100%;
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
export class ResourceDetailsDialogPage {
  private router = inject(Router);
  private translationService = inject(TranslationService);
  t = this.translationService.t;
  
  visible = false;

  resource = {
    title: 'Quran Text - Uthmani Script (Hafs)',
    description: 'Complete Quranic text in Uthmani script following the Hafs recitation method with full diacritical marks and comprehensive metadata.',
    license: 'CC0 1.0',
    language: 'Arabic',
    version: 'v2.1.0',
    type: 'Text',
    downloads: '15,847',
    lastUpdated: '2 weeks ago',
    size: '2.4 MB',
    rating: '4.8',
    publisher: 'Itqan Foundation',
    category: 'Quranic Text',
    format: 'JSON, XML, CSV',
    encoding: 'UTF-8',
    createdDate: 'January 15, 2023',
    keyFeatures: [
      'Complete 114 Surahs with 6,236 Ayahs',
      'Full diacritical marks (Tashkeel)',
      'Verse-by-verse metadata',
      'Multiple output formats',
      'API-ready structure'
    ],
    quickExample: `// Get verse by reference
const verse = quran.getVerse(2, 255);
console.log(verse.arabic);
// "اللَّهُ لَا إِلَٰهَ إِلَّا هُوَ..."`,
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
      }
    ],
    licenseDetails: {
      name: 'Creative Commons Zero v1.0 Universal',
      summary: 'No rights reserved. You can copy, modify, distribute and perform the work, even for commercial purposes, all without asking permission.',
      permissions: [
        'Commercial use',
        'Modification',
        'Distribution',
        'Private use'
      ],
      conditions: [
        'No conditions required'
      ],
      limitations: [
        'No warranty',
        'No liability',
        'No trademark rights'
      ]
    }
  };

  openDialog() {
    this.visible = true;
  }

  close() { 
    this.visible = false; 
  }
}


