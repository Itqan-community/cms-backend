import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { DialogModule } from 'primeng/dialog';
import { ButtonModule } from 'primeng/button';
import { ChipModule } from 'primeng/chip';
import { ProgressBarModule } from 'primeng/progressbar';
import { DividerModule } from 'primeng/divider';
import { Router } from '@angular/router';
import { TranslationService } from '../../shared/translation.service';

@Component({
  standalone: true,
  selector: 'app-dialog-license-confirm',
  imports: [CommonModule, DialogModule, ButtonModule, ChipModule, ProgressBarModule, DividerModule],
  template: `
    <div class="dialog-demo-page">
      <div class="container py-6">
        <div class="demo-header mb-4">
          <h2>License Confirmation Modal Demo</h2>
          <p class="text-muted">This demonstrates the license confirmation popup as shown in wireframe 4c</p>
          <button pButton label="Open License Confirmation Dialog" (click)="openDialog()" class="mb-4"></button>
        </div>

        <!-- License Confirmation Modal Dialog -->
        <p-dialog [(visible)]="visible" 
                  [modal]="true" 
                  header="Download Confirmation" 
                  [style]="{width: '90vw', maxWidth: '600px'}" 
                  [draggable]="false" 
                  [resizable]="false"
                  [closable]="true"
                  styleClass="license-confirm-dialog">
          
          <!-- Dialog Content -->
          <div class="dialog-content">
            <!-- Success Header -->
            <div class="success-header text-center mb-4">
              <div class="success-icon mb-3">
                <i class="pi pi-check-circle"></i>
              </div>
              <h3 class="success-title mb-2">License Agreement Accepted</h3>
              <p class="success-message text-muted">
                You have successfully accepted the license terms for this resource
              </p>
            </div>

            <p-divider></p-divider>

            <!-- Download Information -->
            <div class="download-info mb-4">
              <h4 class="mb-3">Download Details</h4>
              
              <!-- Resource Info -->
              <div class="resource-summary">
                <div class="resource-item">
                  <div class="resource-details">
                    <h5 class="resource-name mb-1">{{ download.resourceName }}</h5>
                    <p class="resource-meta text-muted mb-2">{{ download.description }}</p>
                    <div class="resource-tags">
                      <p-chip [label]="download.license" 
                              [style]="{'background-color': '#e3f2fd', 'color': '#1976d2'}" 
                              size="small" 
                              class="me-2"></p-chip>
                      <p-chip [label]="download.version" 
                              [style]="{'background-color': '#e8f5e8', 'color': '#388e3c'}" 
                              size="small" 
                              class="me-2"></p-chip>
                      <p-chip [label]="download.size" 
                              [style]="{'background-color': '#fff3e0', 'color': '#f57c00'}" 
                              size="small"></p-chip>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <p-divider></p-divider>

            <!-- Download Progress -->
            <div class="download-progress mb-4" *ngIf="downloadStarted">
              <h4 class="mb-3">Download Progress</h4>
              
              <div class="progress-info mb-2">
                <div class="flex justify-between">
                  <span>{{ download.currentFile }}</span>
                  <span>{{ downloadProgress }}%</span>
                </div>
              </div>
              
              <p-progressBar [value]="downloadProgress" 
                             [style]="{'height': '8px'}"
                             class="mb-3"></p-progressBar>
              
              <div class="download-stats">
                <div class="stat-grid">
                  <div class="stat-item">
                    <small class="stat-label">Speed</small>
                    <span class="stat-value">{{ download.speed }}</span>
                  </div>
                  <div class="stat-item">
                    <small class="stat-label">Time Remaining</small>
                    <span class="stat-value">{{ download.timeRemaining }}</span>
                  </div>
                  <div class="stat-item">
                    <small class="stat-label">Downloaded</small>
                    <span class="stat-value">{{ download.downloaded }}</span>
                  </div>
                </div>
              </div>
            </div>

            <!-- Download Complete -->
            <div class="download-complete mb-4" *ngIf="downloadComplete">
              <div class="complete-message text-center">
                <div class="complete-icon mb-2">
                  <i class="pi pi-download text-success"></i>
                </div>
                <h4 class="text-success mb-2">Download Complete!</h4>
                <p class="text-muted mb-3">
                  Your files have been successfully downloaded to your device
                </p>
                <div class="downloaded-files">
                  <h5 class="mb-2">Downloaded Files:</h5>
                  <ul class="files-list">
                    <li *ngFor="let file of download.files" class="file-item">
                      <i class="pi pi-file me-2"></i>
                      <span>{{ file.name }}</span>
                      <small class="text-muted">({{ file.size }})</small>
                    </li>
                  </ul>
                </div>
              </div>
            </div>

            <!-- License Reminder -->
            <div class="license-reminder">
              <div class="reminder-content">
                <h5 class="mb-2">
                  <i class="pi pi-info-circle me-2"></i>
                  License Reminder
                </h5>
                <p class="mb-2">
                  By downloading this resource, you agree to use it according to the 
                  <strong>{{ download.license }}</strong> license terms.
                </p>
                <div class="reminder-actions">
                  <button pButton label="View License Details" 
                          [outlined]="true" 
                          size="small"
                          (click)="viewLicense()"></button>
                </div>
              </div>
            </div>
          </div>

          <!-- Dialog Footer -->
          <ng-template pTemplate="footer">
            <div class="dialog-footer">
              <div class="footer-actions">
                <button pButton label="Back to Terms" 
                        [outlined]="true" 
                        (click)="back()"
                        class="me-2"
                        *ngIf="!downloadStarted"></button>
                <button pButton label="Start Download" 
                        icon="pi pi-download" 
                        (click)="startDownload()"
                        class="download-btn"
                        *ngIf="!downloadStarted && !downloadComplete"></button>
                <button pButton label="Cancel Download" 
                        severity="secondary"
                        [outlined]="true" 
                        (click)="cancelDownload()"
                        class="me-2"
                        *ngIf="downloadStarted && !downloadComplete"></button>
                <button pButton label="Open Download Folder" 
                        icon="pi pi-folder-open" 
                        (click)="openFolder()"
                        class="me-2"
                        *ngIf="downloadComplete"></button>
                <button pButton label="Close" 
                        [outlined]="true" 
                        (click)="close()"
                        *ngIf="downloadComplete || !downloadStarted"></button>
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
    :host ::ng-deep .license-confirm-dialog .p-dialog-content {
      padding: 0;
    }

    :host ::ng-deep .license-confirm-dialog .p-dialog-header {
      background: var(--p-primary-500);
      color: white;
      border-radius: 0.5rem 0.5rem 0 0;
    }

    :host ::ng-deep .license-confirm-dialog .p-dialog-header .p-dialog-title {
      color: white;
      font-weight: 600;
    }

    :host ::ng-deep .license-confirm-dialog .p-dialog-header .p-dialog-header-icon {
      color: white;
    }

    .dialog-content {
      padding: 1.5rem;
    }

    /* Success Header */
    .success-header {
      padding: 1rem 0;
    }

    .success-icon {
      font-size: 3rem;
      color: #28a745;
    }

    .success-title {
      font-size: 1.5rem;
      font-weight: 600;
      color: #333;
      margin: 0;
    }

    .success-message {
      font-size: 1rem;
      line-height: 1.5;
    }

    /* Download Info */
    .download-info h4 {
      color: #333;
      font-weight: 600;
    }

    .resource-summary {
      background: #f8f9fa;
      border: 1px solid #dee2e6;
      border-radius: 0.5rem;
      padding: 1rem;
    }

    .resource-name {
      font-size: 1.125rem;
      font-weight: 600;
      color: #333;
      margin: 0;
    }

    .resource-meta {
      font-size: 0.875rem;
      line-height: 1.4;
    }

    .resource-tags {
      display: flex;
      flex-wrap: wrap;
      gap: 0.5rem;
    }

    /* Download Progress */
    .download-progress h4 {
      color: #333;
      font-weight: 600;
    }

    .progress-info {
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-size: 0.875rem;
    }

    .stat-grid {
      display: grid;
      grid-template-columns: 1fr 1fr 1fr;
      gap: 1rem;
      text-align: center;
    }

    .stat-item {
      display: flex;
      flex-direction: column;
      gap: 0.25rem;
    }

    .stat-label {
      color: #6c757d;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      font-size: 0.75rem;
    }

    .stat-value {
      font-weight: 600;
      color: #333;
    }

    /* Download Complete */
    .download-complete {
      text-align: center;
    }

    .complete-icon {
      font-size: 2.5rem;
    }

    .downloaded-files {
      text-align: left;
      max-width: 400px;
      margin: 0 auto;
    }

    .files-list {
      list-style: none;
      padding: 0;
      margin: 0;
    }

    .file-item {
      display: flex;
      align-items: center;
      padding: 0.5rem;
      background: #f8f9fa;
      border-radius: 0.25rem;
      margin-bottom: 0.5rem;
    }

    .file-item:last-child {
      margin-bottom: 0;
    }

    /* License Reminder */
    .license-reminder {
      background: #fff3cd;
      border: 1px solid #ffeaa7;
      border-radius: 0.5rem;
      padding: 1rem;
    }

    .reminder-content h5 {
      color: #856404;
      font-weight: 600;
      display: flex;
      align-items: center;
      margin: 0;
    }

    .reminder-content p {
      color: #856404;
      font-size: 0.875rem;
      line-height: 1.5;
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

    /* Responsive */
    @media (max-width: 768px) {
      .stat-grid {
        grid-template-columns: 1fr;
        gap: 0.5rem;
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
  `]
})
export class LicenseTermsConfirmDialogPage {
  private router = inject(Router);
  private translationService = inject(TranslationService);
  t = this.translationService.t;
  
  visible = false;
  downloadStarted = false;
  downloadComplete = false;
  downloadProgress = 0;

  download = {
    resourceName: 'Quran Text - Uthmani Script (Hafs)',
    description: 'Complete Quranic text with diacritical marks and metadata',
    license: 'CC0 1.0',
    version: 'v2.1.0',
    size: '2.4 MB',
    currentFile: 'quran-uthmani-complete.json',
    speed: '1.2 MB/s',
    timeRemaining: '2 seconds',
    downloaded: '1.8 MB / 2.4 MB',
    files: [
      { name: 'quran-uthmani-complete.json', size: '1.8 MB' },
      { name: 'quran-uthmani-complete.xml', size: '2.1 MB' },
      { name: 'quran-chapters-metadata.json', size: '45 KB' },
      { name: 'documentation.pdf', size: '890 KB' }
    ]
  };

  private downloadInterval: any;

  openDialog() {
    this.visible = true;
    this.resetDownload();
  }

  resetDownload() {
    this.downloadStarted = false;
    this.downloadComplete = false;
    this.downloadProgress = 0;
    if (this.downloadInterval) {
      clearInterval(this.downloadInterval);
    }
  }

  startDownload() {
    this.downloadStarted = true;
    this.downloadProgress = 0;
    
    // Simulate download progress
    this.downloadInterval = setInterval(() => {
      this.downloadProgress += Math.random() * 15;
      
      if (this.downloadProgress >= 100) {
        this.downloadProgress = 100;
        this.downloadComplete = true;
        this.downloadStarted = false;
        clearInterval(this.downloadInterval);
      }
      
      // Update download stats based on progress
      const remaining = Math.max(0, 100 - this.downloadProgress);
      this.download.timeRemaining = remaining > 0 ? Math.ceil(remaining / 20) + ' seconds' : '0 seconds';
      this.download.downloaded = (2.4 * this.downloadProgress / 100).toFixed(1) + ' MB / 2.4 MB';
    }, 200);
  }

  cancelDownload() {
    if (this.downloadInterval) {
      clearInterval(this.downloadInterval);
    }
    this.resetDownload();
  }

  openFolder() {
    // Simulate opening download folder
    alert('Opening download folder...');
  }

  viewLicense() {
    this.router.navigate(['/licenses/cc0']);
    this.close();
  }

  back() { 
    this.router.navigate(['/demo/license-terms-dialog']); 
    this.close();
  }

  close() { 
    this.resetDownload();
    this.visible = false; 
  }

  ngOnDestroy() {
    if (this.downloadInterval) {
      clearInterval(this.downloadInterval);
    }
  }
}


