import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { DialogModule } from 'primeng/dialog';
import { ButtonModule } from 'primeng/button';
import { CheckboxModule } from 'primeng/checkbox';
import { ScrollPanelModule } from 'primeng/scrollpanel';
import { ChipModule } from 'primeng/chip';
import { DividerModule } from 'primeng/divider';
import { Router } from '@angular/router';
import { TranslationService } from '../../shared/translation.service';

@Component({
  standalone: true,
  selector: 'app-dialog-license-terms',
  imports: [CommonModule, FormsModule, DialogModule, ButtonModule, CheckboxModule, ScrollPanelModule, ChipModule, DividerModule],
  template: `
    <div class="dialog-demo-page">
      <div class="container py-6">
        <div class="demo-header mb-4">
          <h2>License Terms Modal Demo</h2>
          <p class="text-muted">This demonstrates the license terms popup as shown in wireframe 4b</p>
          <button pButton label="Open License Terms Dialog" (click)="openDialog()" class="mb-4"></button>
        </div>

        <!-- License Terms Modal Dialog -->
        <p-dialog [(visible)]="visible" 
                  [modal]="true" 
                  header="License Terms & Conditions" 
                  [style]="{width: '90vw', maxWidth: '800px'}" 
                  [draggable]="false" 
                  [resizable]="false"
                  [closable]="true"
                  styleClass="license-terms-dialog">
          
          <!-- Dialog Content -->
          <div class="dialog-content">
            <!-- License Header -->
            <div class="license-header mb-4">
              <div class="license-info">
                <div class="license-badge mb-3">
                  <p-chip [label]="license.type" 
                          [style]="{'background-color': license.color, 'color': 'white', 'font-size': '1rem'}" 
                          class="license-chip"></p-chip>
                </div>
                
                <h3 class="license-title mb-2">{{ license.fullName }}</h3>
                <p class="license-summary text-muted mb-3">{{ license.summary }}</p>
                
                <!-- Resource Context -->
                <div class="resource-context">
                  <small class="text-muted">
                    <i class="pi pi-info-circle me-1"></i>
                    You are about to download: <strong>{{ resource.name }}</strong>
                  </small>
                </div>
              </div>
            </div>

            <p-divider></p-divider>

            <!-- License Content -->
            <div class="license-content">
              <!-- Quick Summary -->
              <div class="license-summary-section mb-4">
                <h4 class="mb-3">License Summary</h4>
                <div class="summary-grid">
                  <div class="summary-section permissions">
                    <h5 class="text-success mb-2">
                      <i class="pi pi-check-circle me-1"></i>
                      You CAN
                    </h5>
                    <ul class="summary-list">
                      <li *ngFor="let permission of license.permissions">{{ permission }}</li>
                    </ul>
                  </div>
                  
                  <div class="summary-section conditions">
                    <h5 class="text-warning mb-2">
                      <i class="pi pi-exclamation-triangle me-1"></i>
                      You MUST
                    </h5>
                    <ul class="summary-list">
                      <li *ngFor="let condition of license.conditions">{{ condition }}</li>
                    </ul>
                  </div>
                  
                  <div class="summary-section limitations">
                    <h5 class="text-danger mb-2">
                      <i class="pi pi-times-circle me-1"></i>
                      You CANNOT
                    </h5>
                    <ul class="summary-list">
                      <li *ngFor="let limitation of license.limitations">{{ limitation }}</li>
                    </ul>
                  </div>
                </div>
              </div>

              <p-divider></p-divider>

              <!-- Full Legal Text -->
              <div class="legal-text-section">
                <h4 class="mb-3">Full Legal Text</h4>
                <div class="legal-disclaimer mb-3">
                  <p class="mb-0">
                    <strong>Important:</strong> The summary above is for informational purposes only. 
                    The full legal text below is the authoritative version of this license.
                  </p>
                </div>
                
                <p-scrollPanel [style]="{width: '100%', height: '300px'}" styleClass="legal-scroll">
                  <div class="legal-text">
                    <pre>{{ license.legalText }}</pre>
                  </div>
                </p-scrollPanel>
              </div>

              <!-- Agreement Section -->
              <div class="agreement-section mt-4">
                <div class="agreement-checkboxes">
                  <div class="checkbox-item">
                    <p-checkbox [(ngModel)]="agreements.readTerms" 
                                [binary]="true" 
                                inputId="readTerms"></p-checkbox>
                    <label for="readTerms" class="checkbox-label">
                      I have read and understood the license terms above
                    </label>
                  </div>
                  
                  <div class="checkbox-item">
                    <p-checkbox [(ngModel)]="agreements.acceptTerms" 
                                [binary]="true" 
                                inputId="acceptTerms"></p-checkbox>
                    <label for="acceptTerms" class="checkbox-label">
                      I agree to comply with all terms and conditions of this license
                    </label>
                  </div>
                  
                  <div class="checkbox-item">
                    <p-checkbox [(ngModel)]="agreements.acknowledgeRights" 
                                [binary]="true" 
                                inputId="acknowledgeRights"></p-checkbox>
                    <label for="acknowledgeRights" class="checkbox-label">
                      I acknowledge that this resource is provided under the {{ license.type }} license
                    </label>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- Dialog Footer -->
          <ng-template pTemplate="footer">
            <div class="dialog-footer">
              <div class="footer-actions">
                <button pButton label="Cancel" 
                        [outlined]="true" 
                        (click)="close()"
                        class="me-2"></button>
                <button pButton label="View License Details" 
                        [outlined]="true" 
                        (click)="viewLicenseDetails()"
                        class="me-2"></button>
                <button pButton label="Accept & Download" 
                        icon="pi pi-download" 
                        [disabled]="!canAccept()"
                        (click)="confirm()"
                        class="accept-btn"></button>
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
    :host ::ng-deep .license-terms-dialog .p-dialog-content {
      padding: 0;
    }

    :host ::ng-deep .license-terms-dialog .p-dialog-header {
      background: #dc3545;
      color: white;
      border-radius: 0.5rem 0.5rem 0 0;
    }

    :host ::ng-deep .license-terms-dialog .p-dialog-header .p-dialog-title {
      color: white;
      font-weight: 600;
    }

    :host ::ng-deep .license-terms-dialog .p-dialog-header .p-dialog-header-icon {
      color: white;
    }

    .dialog-content {
      padding: 1.5rem;
    }

    /* License Header */
    .license-header {
      text-align: center;
    }

    .license-chip {
      font-weight: 600;
      padding: 0.5rem 1rem;
    }

    .license-title {
      font-size: 1.5rem;
      font-weight: 700;
      color: #333;
      margin: 0;
    }

    .license-summary {
      font-size: 1rem;
      line-height: 1.5;
    }

    .resource-context {
      padding: 0.75rem;
      background: #e3f2fd;
      border-radius: 0.25rem;
      border-left: 3px solid #2196f3;
    }

    /* License Content */
    .license-summary-section h4 {
      color: #333;
      font-weight: 600;
    }

    .summary-grid {
      display: grid;
      grid-template-columns: 1fr 1fr 1fr;
      gap: 1.5rem;
    }

    .summary-section h5 {
      font-weight: 600;
      display: flex;
      align-items: center;
    }

    .summary-list {
      padding-left: 1rem;
      margin: 0;
    }

    .summary-list li {
      margin-bottom: 0.5rem;
      font-size: 0.875rem;
      line-height: 1.4;
    }

    /* Legal Text */
    .legal-text-section h4 {
      color: #333;
      font-weight: 600;
    }

    .legal-disclaimer {
      padding: 1rem;
      background: #fff3cd;
      border: 1px solid #ffeaa7;
      border-radius: 0.25rem;
      color: #856404;
    }

    :host ::ng-deep .legal-scroll .p-scrollpanel-wrapper {
      border: 1px solid #dee2e6;
      border-radius: 0.25rem;
    }

    .legal-text {
      padding: 1rem;
    }

    .legal-text pre {
      margin: 0;
      font-family: 'Courier New', monospace;
      font-size: 0.75rem;
      line-height: 1.5;
      color: #495057;
      white-space: pre-wrap;
    }

    /* Agreement Section */
    .agreement-section {
      background: #f8f9fa;
      border: 1px solid #dee2e6;
      border-radius: 0.5rem;
      padding: 1.5rem;
    }

    .agreement-checkboxes {
      display: flex;
      flex-direction: column;
      gap: 1rem;
    }

    .checkbox-item {
      display: flex;
      align-items: flex-start;
      gap: 0.75rem;
    }

    .checkbox-label {
      font-size: 0.875rem;
      line-height: 1.5;
      cursor: pointer;
      margin: 0;
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

    .accept-btn {
      background: var(--p-primary-500);
      border-color: var(--p-primary-500);
    }

    .accept-btn:disabled {
      background: #6c757d;
      border-color: #6c757d;
      cursor: not-allowed;
    }

    /* Responsive */
    @media (max-width: 768px) {
      .summary-grid {
        grid-template-columns: 1fr;
        gap: 1rem;
      }

      .footer-actions {
        flex-direction: column;
        gap: 0.5rem;
      }

      .footer-actions button {
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
export class LicenseTermsDialogPage {
  private router = inject(Router);
  private translationService = inject(TranslationService);
  t = this.translationService.t;
  
  visible = false;

  agreements = {
    readTerms: false,
    acceptTerms: false,
    acknowledgeRights: false
  };

  resource = {
    name: 'Quran Text - Uthmani Script (Hafs)'
  };

  license = {
    type: 'CC0 1.0',
    fullName: 'Creative Commons Zero v1.0 Universal',
    summary: 'This license allows you to use this work for any purpose without any restrictions. No attribution is required.',
    color: '#28a745',
    permissions: [
      'Use for any purpose',
      'Modify and adapt',
      'Distribute copies',
      'Use commercially',
      'Use privately'
    ],
    conditions: [
      'No conditions required',
      'Attribution appreciated but not required'
    ],
    limitations: [
      'No warranty provided',
      'No liability accepted',
      'Trademark rights not granted'
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
Work and the meaning and intended legal effect of CC0 on those rights.

1. Copyright and Related Rights. A Work made available under CC0 may be
protected by copyright and related or neighboring rights ("Copyright and
Related Rights"). Copyright and Related Rights include, but are not
limited to, the following:

  i. the right to reproduce, adapt, distribute, perform, display,
     communicate, and translate a Work;
 ii. moral rights retained by the original author(s) and/or performer(s);
iii. publicity and privacy rights pertaining to a person's image or
     likeness depicted in a Work;
 iv. rights protecting against unfair competition in regards to a Work,
     subject to the limitations in paragraph 4(a), below;
  v. rights protecting the extraction, dissemination, use and reuse of data
     in a Work;
 vi. database rights (such as those arising under Directive 96/9/EC of the
     European Parliament and of the Council of 11 March 1996 on the legal
     protection of databases, and under any national implementation
     thereof, including any amended or successor version of such
     directive); and
vii. other similar, equivalent or corresponding rights throughout the
     world based on applicable law or treaty, and any national
     implementations thereof.

2. Waiver. To the greatest extent permitted by, but not in contravention
of, applicable law, Affirmer hereby overtly, fully, permanently,
irrevocably and unconditionally waives, abandons, and surrenders all of
Affirmer's Copyright and Related Rights and associated claims and causes
of action, whether now known or unknown (including existing as well as
future claims and causes of action), in the Work (i) in all territories
worldwide, (ii) for the maximum duration provided by applicable law or
treaty (including future time extensions), (iii) in any current or future
medium and for any number of copies, and (iv) for any purpose whatsoever,
including without limitation commercial, advertising or promotional
purposes (the "Waiver"). Affirmer makes the Waiver for the benefit of each
member of the public at large and to the detriment of Affirmer's heirs and
successors, fully intending that such Waiver shall not be subject to
revocation, rescission, cancellation, termination, or any other legal or
equitable action to disrupt the quiet enjoyment of the Work by the public
as contemplated by Affirmer's express Statement of Purpose.`
  };

  openDialog() {
    this.visible = true;
    // Reset agreements when opening
    this.agreements = {
      readTerms: false,
      acceptTerms: false,
      acknowledgeRights: false
    };
  }

  close() { 
    this.visible = false; 
  }

  viewLicenseDetails() {
    this.router.navigate(['/licenses/cc0']);
    this.close();
  }

  canAccept(): boolean {
    return this.agreements.readTerms && 
           this.agreements.acceptTerms && 
           this.agreements.acknowledgeRights;
  }

  confirm() { 
    if (this.canAccept()) {
      this.router.navigate(['/demo/license-terms-confirm']); 
      this.close();
    }
  }
}


