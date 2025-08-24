import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { CardModule } from 'primeng/card';
import { ButtonModule } from 'primeng/button';
import { ChipModule } from 'primeng/chip';
import { DividerModule } from 'primeng/divider';
import { AccordionModule } from 'primeng/accordion';
import { RouterLink } from '@angular/router';
import { TranslationService } from '../../shared/translation.service';

@Component({
  standalone: true,
  selector: 'app-license-details',
  imports: [CommonModule, CardModule, ButtonModule, ChipModule, DividerModule, AccordionModule, RouterLink],
  template: `
    <div class="license-details-page">
      <!-- Breadcrumb Navigation -->
      <div class="breadcrumb-section bg-surface py-3">
        <div class="container">
          <nav class="breadcrumb">
            <a routerLink="/home-auth" class="breadcrumb-item">Home</a>
            <span class="breadcrumb-separator">/</span>
            <a routerLink="/resources/123" class="breadcrumb-item">{{ license.resourceName }}</a>
            <span class="breadcrumb-separator">/</span>
            <span class="breadcrumb-current">License Details</span>
          </nav>
        </div>
      </div>

      <div class="container py-6">
        <!-- License Header -->
        <div class="license-header mb-6">
          <div class="row">
            <div class="col-8">
              <div class="license-info">
                <div class="license-badge mb-3">
                  <p-chip [label]="license.type" 
                          [style]="{'background-color': license.color, 'color': 'white', 'font-size': '1.1rem'}" 
                          class="license-chip"></p-chip>
                </div>
                
                <h1 class="license-title text-dark mb-3">{{ license.fullName }}</h1>
                <p class="license-summary text-muted mb-4">{{ license.summary }}</p>
                
                <!-- Quick Stats -->
                <div class="license-stats flex gap-4 mb-4">
                  <div class="stat-item">
                    <i class="pi pi-check-circle me-2 text-success"></i>
                    <span>{{ license.permissions.length }} Permissions</span>
                  </div>
                  <div class="stat-item">
                    <i class="pi pi-exclamation-triangle me-2 text-warning"></i>
                    <span>{{ license.limitations.length }} Limitations</span>
                  </div>
                  <div class="stat-item">
                    <i class="pi pi-info-circle me-2 text-info"></i>
                    <span>{{ license.conditions.length }} Conditions</span>
                  </div>
                </div>
              </div>
            </div>
            
            <div class="col-4">
              <div class="license-actions">
                <p-card class="action-card">
                  <div class="action-content">
                    <h3 class="mb-3">License Actions</h3>
                    
                    <button pButton label="Download Full License" 
                            icon="pi pi-download" 
                            class="w-full mb-3 download-btn"></button>
                    
                    <button pButton label="View Legal Text" 
                            icon="pi pi-file-text" 
                            [outlined]="true" 
                            class="w-full mb-3"></button>
                    
                    <a routerLink="/resources/123" 
                       pButton label="Back to Resource" 
                       icon="pi pi-arrow-left" 
                       [outlined]="true" 
                       class="w-full mb-3"></a>
                    
                    <p-divider></p-divider>
                    
                    <div class="license-compatibility mt-3">
                      <h4 class="mb-2">Compatible Licenses</h4>
                      <div class="compatible-licenses">
                        <p-chip *ngFor="let compatible of license.compatibleLicenses" 
                                [label]="compatible" 
                                size="small" 
                                class="me-1 mb-1"
                                [style]="{'background-color': '#e3f2fd'}"></p-chip>
                      </div>
                    </div>
                  </div>
                </p-card>
              </div>
            </div>
          </div>
        </div>

        <!-- License Content -->
        <div class="license-content">
          <div class="row">
            <!-- Main Content -->
            <div class="col-8">
              <!-- License Overview -->
              <p-card header="License Overview" class="mb-4">
                <div class="overview-content">
                  <p class="mb-4">{{ license.description }}</p>
                  
                  <h4 class="mb-3">Key Highlights</h4>
                  <ul class="highlight-list mb-4">
                    <li *ngFor="let highlight of license.highlights">{{ highlight }}</li>
                  </ul>
                  
                  <div class="license-comparison">
                    <h4 class="mb-3">How this compares to other licenses</h4>
                    <div class="comparison-grid">
                      <div class="comparison-item" *ngFor="let comparison of license.comparisons">
                        <div class="comparison-license">{{ comparison.license }}</div>
                        <div class="comparison-difference">{{ comparison.difference }}</div>
                      </div>
                    </div>
                  </div>
                </div>
              </p-card>

              <!-- Permissions, Limitations, Conditions -->
              <p-accordion [multiple]="true" [activeIndex]="[0, 1, 2]">
                <!-- Permissions -->
                <p-accordionTab header="✅ What you CAN do">
                  <div class="license-section permissions">
                    <div class="permission-list">
                      <div *ngFor="let permission of license.permissions" class="permission-item">
                        <div class="permission-icon">
                          <i class="pi pi-check text-success"></i>
                        </div>
                        <div class="permission-content">
                          <h5 class="permission-title">{{ permission.title }}</h5>
                          <p class="permission-description">{{ permission.description }}</p>
                        </div>
                      </div>
                    </div>
                  </div>
                </p-accordionTab>

                <!-- Limitations -->
                <p-accordionTab header="❌ What you CANNOT do">
                  <div class="license-section limitations">
                    <div class="limitation-list">
                      <div *ngFor="let limitation of license.limitations" class="limitation-item">
                        <div class="limitation-icon">
                          <i class="pi pi-times text-danger"></i>
                        </div>
                        <div class="limitation-content">
                          <h5 class="limitation-title">{{ limitation.title }}</h5>
                          <p class="limitation-description">{{ limitation.description }}</p>
                        </div>
                      </div>
                    </div>
                  </div>
                </p-accordionTab>

                <!-- Conditions -->
                <p-accordionTab header="⚠️ What you MUST do">
                  <div class="license-section conditions">
                    <div class="condition-list">
                      <div *ngFor="let condition of license.conditions" class="condition-item">
                        <div class="condition-icon">
                          <i class="pi pi-exclamation-triangle text-warning"></i>
                        </div>
                        <div class="condition-content">
                          <h5 class="condition-title">{{ condition.title }}</h5>
                          <p class="condition-description">{{ condition.description }}</p>
                        </div>
                      </div>
                    </div>
                  </div>
                </p-accordionTab>
              </p-accordion>

              <!-- Legal Text -->
              <p-card header="Full Legal Text" class="mt-4">
                <div class="legal-text">
                  <div class="legal-disclaimer mb-3">
                    <p><strong>Disclaimer:</strong> This is a human-readable summary of the license. 
                    The full legal text below is the authoritative version.</p>
                  </div>
                  <div class="legal-content">
                    <pre class="legal-text-content">{{ license.legalText }}</pre>
                  </div>
                </div>
              </p-card>
            </div>

            <!-- Sidebar -->
            <div class="col-4">
              <!-- License Metadata -->
              <p-card header="License Information" class="mb-4">
                <div class="license-metadata">
                  <div class="metadata-item">
                    <strong>License Type:</strong>
                    <span>{{ license.type }}</span>
                  </div>
                  <div class="metadata-item">
                    <strong>Version:</strong>
                    <span>{{ license.version }}</span>
                  </div>
                  <div class="metadata-item">
                    <strong>Publisher:</strong>
                    <span>{{ license.publisher }}</span>
                  </div>
                  <div class="metadata-item">
                    <strong>Published:</strong>
                    <span>{{ license.publishedDate }}</span>
                  </div>
                  <div class="metadata-item">
                    <strong>Language:</strong>
                    <span>{{ license.language }}</span>
                  </div>
                  <div class="metadata-item">
                    <strong>Jurisdiction:</strong>
                    <span>{{ license.jurisdiction }}</span>
                  </div>
                </div>
              </p-card>

              <!-- Resources using this license -->
              <p-card header="Resources with this License" class="mb-4">
                <div class="related-resources">
                  <div *ngFor="let resource of license.relatedResources" class="related-resource-item">
                    <div class="resource-info">
                      <h6 class="resource-title">{{ resource.name }}</h6>
                      <p class="resource-type text-muted">{{ resource.type }}</p>
                    </div>
                    <a [routerLink]="['/resources', resource.id]" 
                       pButton icon="pi pi-external-link" 
                       size="small" 
                       [outlined]="true"></a>
                  </div>
                </div>
              </p-card>

              <!-- Help & Support -->
              <p-card header="Need Help?">
                <div class="help-content">
                  <p class="mb-3">Have questions about this license?</p>
                  <button pButton label="Contact Legal Team" 
                          icon="pi pi-envelope" 
                          size="small" 
                          [outlined]="true" 
                          class="w-full mb-2"></button>
                  <button pButton label="View FAQ" 
                          icon="pi pi-question-circle" 
                          size="small" 
                          [outlined]="true" 
                          class="w-full"></button>
                </div>
              </p-card>
            </div>
          </div>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .license-details-page {
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

    /* License Header */
    .license-header {
      background: white;
      border-radius: 0.5rem;
      padding: 2rem;
      box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }

    .license-chip {
      font-weight: 600;
      padding: 0.5rem 1rem;
    }

    .license-title {
      font-size: 2rem;
      font-weight: 700;
    }

    .license-summary {
      font-size: 1.125rem;
      line-height: 1.6;
    }

    .license-stats {
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

    .compatible-licenses {
      display: flex;
      flex-wrap: wrap;
      gap: 0.25rem;
    }

    /* License Content */
    .license-content {
      margin-top: 2rem;
    }

    .overview-content h4 {
      color: #333;
      font-weight: 600;
    }

    .highlight-list {
      padding-left: 1.5rem;
    }

    .highlight-list li {
      margin-bottom: 0.5rem;
      line-height: 1.5;
    }

    /* Comparison Grid */
    .comparison-grid {
      display: grid;
      gap: 1rem;
    }

    .comparison-item {
      display: flex;
      justify-content: space-between;
      padding: 1rem;
      background: #f8f9fa;
      border-radius: 0.25rem;
      border-left: 3px solid var(--p-primary-500);
    }

    .comparison-license {
      font-weight: 600;
    }

    .comparison-difference {
      color: #6c757d;
      font-size: 0.875rem;
    }

    /* License Sections */
    .license-section {
      padding: 1rem 0;
    }

    .permission-item,
    .limitation-item,
    .condition-item {
      display: flex;
      gap: 1rem;
      margin-bottom: 1.5rem;
      padding: 1rem;
      background: #f8f9fa;
      border-radius: 0.5rem;
    }

    .permission-icon,
    .limitation-icon,
    .condition-icon {
      flex-shrink: 0;
      width: 24px;
      height: 24px;
      display: flex;
      align-items: center;
      justify-content: center;
    }

    .permission-title,
    .limitation-title,
    .condition-title {
      margin: 0 0 0.5rem 0;
      font-size: 1rem;
      font-weight: 600;
      color: #333;
    }

    .permission-description,
    .limitation-description,
    .condition-description {
      margin: 0;
      color: #6c757d;
      line-height: 1.5;
    }

    /* Legal Text */
    .legal-disclaimer {
      padding: 1rem;
      background: #fff3cd;
      border: 1px solid #ffeaa7;
      border-radius: 0.25rem;
      color: #856404;
    }

    .legal-text-content {
      background: #f8f9fa;
      border: 1px solid #dee2e6;
      border-radius: 0.25rem;
      padding: 1.5rem;
      font-family: 'Courier New', monospace;
      font-size: 0.875rem;
      line-height: 1.6;
      white-space: pre-wrap;
      max-height: 400px;
      overflow-y: auto;
    }

    /* Sidebar */
    .license-metadata {
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

    .related-resource-item {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 0.75rem 0;
      border-bottom: 1px solid #dee2e6;
    }

    .related-resource-item:last-child {
      border-bottom: none;
    }

    .resource-title {
      margin: 0 0 0.25rem 0;
      font-size: 0.875rem;
      font-weight: 600;
    }

    .resource-type {
      margin: 0;
      font-size: 0.75rem;
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

      .license-header {
        padding: 1rem;
      }

      .license-title {
        font-size: 1.5rem;
      }

      .license-stats {
        flex-direction: column;
        align-items: flex-start;
        gap: 0.5rem;
      }

      .comparison-item {
        flex-direction: column;
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
export class LicenseDetailsPage {
  private translationService = inject(TranslationService);
  t = this.translationService.t;

  license = {
    type: 'CC0 1.0',
    fullName: 'Creative Commons Zero v1.0 Universal',
    summary: 'The Creative Commons CC0 Public Domain Dedication waives copyright interest in a work you\'ve created and dedicates it to the world-wide public domain.',
    description: 'CC0 enables scientists, educators, artists and other creators and owners of copyright- or database-protected content to waive those interests in their works and thereby place them as completely as possible in the public domain, so that others may freely build upon, enhance and reuse the works for any purposes without restriction under copyright or database law.',
    color: '#28a745',
    version: '1.0',
    publisher: 'Creative Commons',
    publishedDate: 'January 1, 2009',
    language: 'English',
    jurisdiction: 'International',
    resourceName: 'Quran Text - Uthmani Script',
    
    highlights: [
      'No rights reserved - complete public domain dedication',
      'Works for any purpose, including commercial use',
      'No attribution required (though appreciated)',
      'Compatible with all other licenses',
      'Recognized internationally'
    ],
    
    permissions: [
      {
        title: 'Commercial Use',
        description: 'You can use this work for commercial purposes without any restrictions or fees.'
      },
      {
        title: 'Modification',
        description: 'You can modify, transform, and build upon the material in any way.'
      },
      {
        title: 'Distribution',
        description: 'You can copy and redistribute the material in any medium or format.'
      },
      {
        title: 'Private Use',
        description: 'You can use this work for personal and private purposes.'
      }
    ],
    
    limitations: [
      {
        title: 'No Warranty',
        description: 'The work is provided "as is" without any warranties or guarantees of any kind.'
      },
      {
        title: 'No Liability',
        description: 'The creator cannot be held liable for any damages arising from the use of this work.'
      },
      {
        title: 'No Trademark Rights',
        description: 'This license does not grant rights to use trademarks or trade names.'
      }
    ],
    
    conditions: [
      {
        title: 'No Conditions',
        description: 'There are no conditions required for using this work. Attribution is not required but is appreciated.'
      }
    ],
    
    compatibleLicenses: [
      'MIT', 'Apache 2.0', 'GPL v3', 'BSD', 'Public Domain'
    ],
    
    comparisons: [
      {
        license: 'MIT License',
        difference: 'MIT requires attribution, CC0 does not'
      },
      {
        license: 'GPL v3',
        difference: 'GPL requires derivative works to use same license, CC0 has no such requirement'
      },
      {
        license: 'Apache 2.0',
        difference: 'Apache requires attribution and license notice, CC0 requires nothing'
      }
    ],
    
    relatedResources: [
      {
        id: 'quran-uthmani-hafs',
        name: 'Quran Text - Uthmani Script',
        type: 'Text Resource'
      },
      {
        id: 'hadith-bukhari',
        name: 'Sahih Bukhari Collection',
        type: 'Hadith Collection'
      },
      {
        id: 'islamic-calendar',
        name: 'Islamic Calendar Data',
        type: 'Data Resource'
      }
    ],
    
    legalText: `Creative Commons Legal Code

CC0 1.0 Universal

    CREATIVE COMMONS CORPORATION IS NOT A LAW FIRM AND DOES NOT PROVIDE
    LEGAL SERVICES. DISTRIBUTION OF THIS DOCUMENT DOES NOT CREATE AN
    ATTORNEY-CLIENT RELATIONSHIP. CREATIVE COMMONS PROVIDES THIS
    INFORMATION ON AN "AS-IS" BASIS. CREATIVE COMMONS MAKES NO WARRANTIES
    REGARDING THE USE OF THIS DOCUMENT OR THE INFORMATION OR WORKS
    PROVIDED HEREUNDER, AND DISCLAIMS LIABILITY FOR DAMAGES RESULTING FROM
    THE USE OF THIS DOCUMENT OR THE INFORMATION OR WORKS PROVIDED
    HEREUNDER.

Statement of Purpose

The laws of most jurisdictions throughout the world automatically confer
exclusive Copyright and Related Rights (defined below) upon the creator
and subsequent owner(s) (each and all, an "owner") of an original work of
authorship and/or a database (each, a "Work").

Certain owners wish to permanently relinquish those rights to a Work for
the purpose of contributing to a commons of creative, cultural and
scientific works ("Commons") that the public can reliably and without fear
of later claims of infringement build upon, modify, incorporate in other
works, reuse and redistribute as freely as possible in any form whatsoever
and for any purposes, including without limitation commercial purposes.
These owners may contribute to the Commons to promote the ideal of a free
culture and the further production of creative, cultural and scientific
works, or to gain reputation or greater distribution for their Work in
part through the use and efforts of others.

For these and/or other purposes and motivations, and without any
expectation of additional consideration or compensation, the person
associating CC0 with a Work (the "Affirmer"), to the extent that he or she
is an owner of Copyright and Related Rights in the Work, voluntarily
elects to apply CC0 to the Work and publicly distribute the Work under its
terms, with knowledge of his or her Copyright and Related Rights in the
Work and the meaning and intended legal effect of CC0 on those rights.`
  };
}


