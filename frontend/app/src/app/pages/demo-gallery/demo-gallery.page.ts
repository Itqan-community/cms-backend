import { Component, inject } from '@angular/core';
import { RouterLink } from '@angular/router';
import { CardModule } from 'primeng/card';
import { ButtonModule } from 'primeng/button';
import { TranslationService } from '../../shared/translation.service';

@Component({
  standalone: true,
  selector: 'app-demo-gallery',
  imports: [RouterLink, CardModule, ButtonModule],
  template: `
    <div class="demo-gallery-page">
      <div class="container py-6">
        <div class="text-center mb-6">
          <h1 class="text-dark mb-3">{{ t('demo.title') }}</h1>
          <p class="text-muted">Navigate using the menu above or click the links below to explore all wireframe implementations</p>
        </div>
        
        <div class="row">
          <!-- Content Pages -->
          <div class="col-6 mb-4">
            <p-card header="Content Pages" class="h-full">
              <div class="flex flex-col gap-2">
                <a routerLink="/content-standards" pButton [label]="t('demo.contentStandards')" [outlined]="true"></a>
                <a [routerLink]="['/resources', '123']" pButton [label]="t('demo.resourceDetails')" [outlined]="true"></a>
                <a [routerLink]="['/licenses', 'cc0']" pButton [label]="t('demo.licenseDetails')" [outlined]="true"></a>
                <a [routerLink]="['/publishers', 'itqan']" pButton [label]="t('demo.publisherDetails')" [outlined]="true"></a>
              </div>
            </p-card>
          </div>
          
          <!-- Authentication Pages -->
          <div class="col-6 mb-4">
            <p-card header="Authentication Pages" class="h-full">
              <div class="flex flex-col gap-2">
                <a routerLink="/auth/login" pButton [label]="t('demo.login')" [outlined]="true"></a>
                <a routerLink="/auth/register-oauth" pButton [label]="t('demo.registerOAuth')" [outlined]="true"></a>
                <a routerLink="/auth/register-email" pButton [label]="t('demo.registerEmail')" [outlined]="true"></a>
                <a routerLink="/auth/profile-capture" pButton [label]="t('demo.profileCapture')" [outlined]="true"></a>
              </div>
            </p-card>
          </div>
          
          <!-- Home Pages -->
          <div class="col-6 mb-4">
            <p-card header="Home Pages" class="h-full">
              <div class="flex flex-col gap-2">
                <a routerLink="/home-unauth" pButton [label]="t('demo.homeUnauth')" [outlined]="true"></a>
                <a routerLink="/home-auth" pButton [label]="t('demo.homeAuth')" [outlined]="true"></a>
              </div>
            </p-card>
          </div>
          
          <!-- Dialog Demos -->
          <div class="col-6 mb-4">
            <p-card header="Dialog Demos" class="h-full">
              <div class="flex flex-col gap-2">
                <a routerLink="/demo/resource-dialog" pButton [label]="t('demo.resourceDialog')" [outlined]="true"></a>
                <a routerLink="/demo/license-terms-dialog" pButton [label]="t('demo.licenseTermsDialog')" [outlined]="true"></a>
                <a routerLink="/demo/license-terms-confirm" pButton [label]="t('demo.licenseTermsConfirm')" [outlined]="true"></a>
              </div>
            </p-card>
          </div>
        </div>
        
        <!-- Wireframe Info -->
        <div class="wireframe-info mt-6">
          <p-card>
            <div class="text-center">
              <h3 class="mb-3">Wireframe Implementation Status</h3>
              <p class="text-muted mb-4">All pages are built according to the provided wireframes with dummy data as shown in the designs.</p>
              <div class="flex justify-center gap-4">
                <div class="status-item">
                  <i class="pi pi-check-circle text-success me-2"></i>
                  <span>13 Pages Implemented</span>
                </div>
                <div class="status-item">
                  <i class="pi pi-globe text-primary me-2"></i>
                  <span>RTL/LTR Support</span>
                </div>
                <div class="status-item">
                  <i class="pi pi-mobile text-info me-2"></i>
                  <span>Responsive Design</span>
                </div>
              </div>
            </div>
          </p-card>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .demo-gallery-page {
      background: #f8f9fa;
      min-height: 100vh;
    }
    
    .h-full {
      height: 100%;
    }
    
    .status-item {
      display: flex;
      align-items: center;
      padding: 0.5rem 1rem;
      background: white;
      border-radius: 0.25rem;
      box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }
    
    .text-success { color: #28a745 !important; }
    .text-primary { color: var(--p-primary-500) !important; }
    .text-info { color: #17a2b8 !important; }
    
    /* RTL Adjustments */
    [dir="rtl"] .me-2 {
      margin-left: 0.5rem;
      margin-right: 0;
    }
  `]
})
export class DemoGalleryPage {
  private translationService = inject(TranslationService);
  t = this.translationService.t;
}


