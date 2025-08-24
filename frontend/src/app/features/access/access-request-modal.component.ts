import { Component, Input, Output, EventEmitter, OnInit, inject, signal, effect } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule, FormsModule, FormBuilder, FormGroup, Validators } from '@angular/forms';
import { HttpClient } from '@angular/common/http';

// NG-ZORRO Imports
import { NzModalModule } from 'ng-zorro-antd/modal';
import { NzFormModule } from 'ng-zorro-antd/form';
import { NzInputModule } from 'ng-zorro-antd/input';
import { NzButtonModule } from 'ng-zorro-antd/button';
import { NzSelectModule } from 'ng-zorro-antd/select';
import { NzRadioModule } from 'ng-zorro-antd/radio';
import { NzCheckboxModule } from 'ng-zorro-antd/checkbox';
import { NzInputNumberModule } from 'ng-zorro-antd/input-number';
import { NzStepsModule } from 'ng-zorro-antd/steps';
import { NzCarouselModule } from 'ng-zorro-antd/carousel';
import { NzCardModule } from 'ng-zorro-antd/card';
import { NzDividerModule } from 'ng-zorro-antd/divider';
import { NzTypographyModule } from 'ng-zorro-antd/typography';
import { NzIconModule } from 'ng-zorro-antd/icon';
import { NzSpaceModule } from 'ng-zorro-antd/space';
import { NzTagModule } from 'ng-zorro-antd/tag';
import { NzProgressModule } from 'ng-zorro-antd/progress';
import { NzResultModule } from 'ng-zorro-antd/result';
import { NzSpinModule } from 'ng-zorro-antd/spin';

// Services
import { I18nService } from '../../core/services/i18n.service';
import { environment } from '../../../environments/environment.develop';

interface Resource {
  id: string;
  title_en?: string;
  title_ar?: string;
  description_en?: string;
  description_ar?: string;
  resource_type: string;
  license_type: string;
  checksum?: string;
  publisher_name: string;
  size?: string;
}

interface LicenseTerms {
  id: string;
  title_en: string;
  title_ar: string;
  content_en: string;
  content_ar: string;
  icon?: string;
  required: boolean;
}

interface AccessRequestData {
  resource_id: string;
  purpose: string;
  project_type: string;
  expected_usage: string;
  distribution_method: string;
  target_audience: string;
  organization?: string;
  justification: string;
  agree_to_terms: boolean;
}

/**
 * Access Request Modal Component
 * 
 * Comprehensive workflow for requesting access to Islamic content resources.
 * Includes purpose questionnaire, terms carousel, and approval tracking.
 */
@Component({
  selector: 'app-access-request-modal',
  standalone: true,
  imports: [
    CommonModule,
    ReactiveFormsModule,
    FormsModule,
    NzModalModule,
    NzFormModule,
    NzInputModule,
    NzButtonModule,
    NzSelectModule,
    NzRadioModule,
    NzCheckboxModule,
    NzInputNumberModule,
    NzStepsModule,
    NzCarouselModule,
    NzCardModule,
    NzDividerModule,
    NzTypographyModule,
    NzIconModule,
    NzSpaceModule,
    NzTagModule,
    NzProgressModule,
    NzResultModule,
    NzSpinModule
  ],
  template: `
    <nz-modal
      [nzVisible]="visible"
      [nzTitle]="modalTitle"
      [nzWidth]="800"
      (nzOnCancel)="onCancel()"
      [nzFooter]="modalFooter"
      class="access-request-modal"
    >
      <ng-container *nzModalContent>
        <div class="modal-content" [dir]="isArabic() ? 'rtl' : 'ltr'">
        
          <!-- Steps Progress -->
          <nz-steps 
            [nzCurrent]="currentStep()" 
            nzDirection="horizontal"
            class="request-steps">
            <nz-step 
              [nzTitle]="t('access_request.step_1_title')"
              [nzDescription]="t('access_request.step_1_desc')"
              [nzIcon]="'form'">
            </nz-step>
            <nz-step 
              [nzTitle]="t('access_request.step_2_title')"
              [nzDescription]="t('access_request.step_2_desc')"
              [nzIcon]="'file-text'">
            </nz-step>
            <nz-step 
              [nzTitle]="t('access_request.step_3_title')"
              [nzDescription]="t('access_request.step_3_desc')"
              [nzIcon]="'check-circle'">
            </nz-step>
          </nz-steps>
  
          <nz-divider></nz-divider>
  
          <!-- Resource Information Header -->
          <div class="resource-info" *ngIf="resource">
            <div class="resource-header">
              <div class="resource-details">
                <h3 class="resource-title" [class.rtl]="isArabic()">
                  {{ isArabic() ? (resource.title_ar || resource.title_en) : (resource.title_en || resource.title_ar) }}
                </h3>
                <p class="resource-description" [class.rtl]="isArabic()">
                  {{ isArabic() ? (resource.description_ar || resource.description_en) : (resource.description_en || resource.description_ar) }}
                </p>
                <div class="resource-metadata">
                  <nz-space [nzSize]="'small'">
                    <nz-tag *nzSpaceItem [nzColor]="'geekblue'">
                      {{ resource.resource_type | titlecase }}
                    </nz-tag>
                    <nz-tag *nzSpaceItem [nzColor]="'green'">
                      {{ resource.license_type }}
                    </nz-tag>
                    <span *nzSpaceItem class="publisher-name">
                      {{ t('access_request.by') }} {{ resource.publisher_name }}
                    </span>
                  </nz-space>
                </div>
              </div>
            </div>
          </div>
  
          <nz-divider></nz-divider>

          <!-- Step Content Areas -->
          <div class="step-content">
            
            <!-- Step 1: Purpose Questionnaire -->
            <div *ngIf="currentStep() === 0" class="step-content">
              <div class="step-header">
                <h3 [class.rtl]="isArabic()">{{ t('access_request.purpose_title') }}</h3>
                <p class="step-subtitle" [class.rtl]="isArabic()">{{ t('access_request.purpose_subtitle') }}</p>
              </div>
    
              <form nz-form [formGroup]="purposeForm" [nzLayout]="'vertical'">
                <!-- Project Type -->
                <nz-form-item>
                  <nz-form-label [nzRequired]="true">{{ t('access_request.project_type') }}</nz-form-label>
                  <nz-form-control nzErrorTip="{{ t('access_request.project_type_required') }}">
                    <nz-select formControlName="project_type" [nzPlaceHolder]="t('access_request.select_project_type')">
                      <nz-option 
                        *ngFor="let option of projectTypeOptions" 
                        [nzValue]="option.value" 
                        [nzLabel]="isArabic() ? option.label_ar : option.label_en">
                      </nz-option>
                    </nz-select>
                  </nz-form-control>
                </nz-form-item>
    
                <!-- Expected Usage -->
                <nz-form-item>
                  <nz-form-label [nzRequired]="true">{{ t('access_request.expected_usage') }}</nz-form-label>
                  <nz-form-control nzErrorTip="{{ t('access_request.expected_usage_required') }}">
                    <nz-radio-group formControlName="expected_usage">
                      <div class="radio-options">
                        <label *ngFor="let option of usageOptions" nz-radio [nzValue]="option.value">
                          <span [class.rtl]="isArabic()">{{ isArabic() ? option.label_ar : option.label_en }}</span>
                        </label>
                      </div>
                    </nz-radio-group>
                  </nz-form-control>
                </nz-form-item>
    
                <!-- Distribution Method -->
                <nz-form-item>
                  <nz-form-label [nzRequired]="true">{{ t('access_request.distribution_method') }}</nz-form-label>
                  <nz-form-control nzErrorTip="{{ t('access_request.distribution_method_required') }}">
                    <nz-select formControlName="distribution_method" [nzPlaceHolder]="t('access_request.select_distribution')">
                      <nz-option 
                        *ngFor="let option of distributionOptions" 
                        [nzValue]="option.value" 
                        [nzLabel]="isArabic() ? option.label_ar : option.label_en">
                      </nz-option>
                    </nz-select>
                  </nz-form-control>
                </nz-form-item>
    
                <!-- Target Audience -->
                <nz-form-item>
                  <nz-form-label [nzRequired]="true">{{ t('access_request.target_audience') }}</nz-form-label>
                  <nz-form-control nzErrorTip="{{ t('access_request.target_audience_required') }}">
                    <nz-checkbox-group formControlName="target_audience">
                      <div class="checkbox-options">
                        <label *ngFor="let option of audienceOptions" nz-checkbox [nzValue]="option.value">
                          <span [class.rtl]="isArabic()">{{ isArabic() ? option.label_ar : option.label_en }}</span>
                        </label>
                      </div>
                    </nz-checkbox-group>
                  </nz-form-control>
                </nz-form-item>
    
                <!-- Organization (Optional) -->
                <nz-form-item>
                  <nz-form-label>{{ t('access_request.organization') }} ({{ t('common.optional') }})</nz-form-label>
                  <nz-form-control>
                    <input 
                      nz-input 
                      formControlName="organization" 
                      [placeholder]="t('access_request.organization_placeholder')"
                      [class.rtl]="isArabic()">
                  </nz-form-control>
                </nz-form-item>
    
                <!-- Justification -->
                <nz-form-item>
                  <nz-form-label [nzRequired]="true">{{ t('access_request.justification') }}</nz-form-label>
                  <nz-form-control nzErrorTip="{{ t('access_request.justification_required') }}">
                    <textarea 
                      nz-input 
                      formControlName="justification"
                      rows="4"
                      [placeholder]="t('access_request.justification_placeholder')"
                      [class.rtl]="isArabic()">
                    </textarea>
                  </nz-form-control>
                </nz-form-item>
              </form>
            </div>
    
            <!-- Step 2: Terms and Conditions Carousel -->
            <div *ngIf="currentStep() === 1" class="step-content">
              <div class="step-header">
                <h3 [class.rtl]="isArabic()">{{ t('access_request.terms_title') }}</h3>
                <p class="step-subtitle" [class.rtl]="isArabic()">{{ t('access_request.terms_subtitle') }}</p>
              </div>
    
              <div class="terms-carousel-container">
                <nz-carousel 
                  [nzDotRender]="dotTemplate" 
                  [nzEffect]="'fade'"
                  #termsCarousel>
                  
                  <div nz-carousel-content *ngFor="let term of licenseTerms; let i = index">
                    <nz-card 
                      class="terms-card"
                      [nzTitle]="termsCardTitle"
                      [nzBordered]="true">
                      
                      <ng-template #termsCardTitle>
                        <div class="terms-card-header">
                          <span class="terms-icon" *ngIf="term.icon">{{ term.icon }}</span>
                          <span [class.rtl]="isArabic()">{{ isArabic() ? term.title_ar : term.title_en }}</span>
                          <nz-tag *ngIf="term.required" [nzColor]="'volcano'" class="required-tag">
                            {{ t('access_request.required') }}
                          </nz-tag>
                        </div>
                      </ng-template>
                      
                      <div class="terms-content" [class.rtl]="isArabic()">
                        <div [innerHTML]="isArabic() ? term.content_ar : term.content_en"></div>
                      </div>
                    </nz-card>
                  </div>
                  
                  <ng-template #dotTemplate let-i="index">
                    <div class="carousel-dot" [class.active]="i === currentTermsSlide()">
                      <span class="dot-number">{{ i + 1 }}</span>
                    </div>
                  </ng-template>
                </nz-carousel>
    
                <!-- Carousel Navigation -->
                <div class="carousel-navigation">
                  <button 
                    nz-button 
                    nzType="default"
                    [disabled]="currentTermsSlide() === 0"
                    (click)="previousTerms()">
                    <span nz-icon [nzType]="isArabic() ? 'right' : 'left'"></span>
                    {{ t('access_request.previous') }}
                  </button>
                  
                  <div class="carousel-progress">
                    <nz-progress 
                      [nzPercent]="getTermsProgress()" 
                      [nzStrokeColor]="'#669B80'"
                      [nzFormat]="progressFormat"
                      nzSize="small">
                    </nz-progress>
                  </div>
                  
                  <button 
                    nz-button 
                    nzType="default"
                    [disabled]="currentTermsSlide() >= licenseTerms.length - 1"
                    (click)="nextTerms()">
                    {{ t('access_request.next') }}
                    <span nz-icon [nzType]="isArabic() ? 'left' : 'right'"></span>
                  </button>
                </div>
    
                <!-- Agreement Checkbox -->
                <div class="agreement-section" *ngIf="allTermsViewed()">
                  <nz-divider></nz-divider>
                  <div class="agreement-checkbox">
                    <label nz-checkbox [(ngModel)]="agreeToTerms" [class.rtl]="isArabic()">
                      {{ t('access_request.agree_terms') }}
                    </label>
                  </div>
                </div>
              </div>
            </div>
    
            <!-- Step 3: Submission Result -->
            <div *ngIf="currentStep() === 2" class="step-content">
              <div class="submission-result">
                <!-- Loading State -->
                <div *ngIf="submitting()" class="submission-loading">
                  <nz-spin nzTip="{{ t('access_request.submitting') }}" nzSize="large">
                    <div class="loading-content">
                      <nz-progress 
                        [nzPercent]="submissionProgress()"
                        [nzStrokeColor]="'#669B80'"
                        nzSize="small">
                      </nz-progress>
                      <p class="loading-message">{{ t('access_request.processing') }}</p>
                    </div>
                  </nz-spin>
                </div>
    
                <!-- Success State -->
                <div *ngIf="!submitting() && submissionSuccess()" class="submission-success">
                  <nz-result
                    nzStatus="success"
                    [nzTitle]="t('access_request.success_title')"
                    [nzSubTitle]="t('access_request.success_subtitle')"
                    class="result-success">
                    
                    <div nz-result-extra>
                      <div class="success-actions">
                        <button nz-button nzType="primary" (click)="viewMyRequests()">
                          {{ t('access_request.view_requests') }}
                        </button>
                        <button nz-button nzType="default" (click)="browseMore()">
                          {{ t('access_request.browse_more') }}
                        </button>
                      </div>
                    </div>
                  </nz-result>
                </div>
    
                <!-- Error State -->
                <div *ngIf="!submitting() && !submissionSuccess() && submissionError()" class="submission-error">
                  <nz-result
                    nzStatus="error"
                    [nzTitle]="t('access_request.error_title')"
                    [nzSubTitle]="submissionError() || 'An error occurred'"
                    class="result-error">
                    
                    <div nz-result-extra>
                      <div class="error-actions">
                        <button nz-button nzType="primary" (click)="retrySubmission()">
                          {{ t('access_request.retry') }}
                        </button>
                        <button nz-button nzType="default" (click)="onCancel()">
                          {{ t('common.cancel') }}
                        </button>
                      </div>
                    </div>
                  </nz-result>
                </div>
              </div>
            </div>
          </div>
        </div>
      </ng-container>

      <ng-template #modalFooter>
        <div [dir]="isArabic() ? 'rtl' : 'ltr'" class="modal-footer" *ngIf="currentStep() < 2">
          <nz-space>
            <button 
              *nzSpaceItem 
              nz-button 
              nzType="default"
              (click)="onCancel()"
              [disabled]="submitting()">
              {{ t('common.cancel') }}
            </button>
            
            <ng-container *ngIf="currentStep() > 0">
              <button 
                *nzSpaceItem 
                nz-button 
                nzType="default"
                (click)="previousStep()"
                [disabled]="submitting()">
                {{ t('access_request.back') }}
              </button>
            </ng-container>
            
            <button 
              *nzSpaceItem 
              nz-button 
              nzType="primary"
              (click)="nextStep()"
              [disabled]="!canProceed() || submitting()"
              [nzLoading]="submitting()">
              {{ getNextButtonLabel() }}
            </button>
          </nz-space>
        </div>
      </ng-template>
    </nz-modal>
  `,
  styles: [`
    .access-request-modal {
      .modal-content {
        font-family: 'Noto Sans', sans-serif;
      }

      [dir="rtl"] .modal-content {
        font-family: 'Noto Sans Arabic', sans-serif;
        text-align: right;
      }

      /* Steps Progress */
      .request-steps {
        margin-bottom: 24px;
      }

      /* Resource Information */
      .resource-info {
        background: #f9f9f9;
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 0;
      }

      .resource-header {
        display: flex;
        align-items: flex-start;
        gap: 16px;
      }

      .resource-details {
        flex: 1;
      }

      .resource-title {
        font-size: 18px;
        font-weight: 600;
        color: #22433D;
        margin: 0 0 8px 0;
      }

      .resource-title.rtl {
        font-family: 'Noto Sans Arabic', sans-serif;
        text-align: right;
      }

      .resource-description {
        color: #666;
        margin: 0 0 12px 0;
        line-height: 1.5;
      }

      .resource-description.rtl {
        font-family: 'Noto Sans Arabic', sans-serif;
        text-align: right;
      }

      .resource-metadata {
        display: flex;
        align-items: center;
        gap: 8px;
      }

      .publisher-name {
        color: #999;
        font-size: 12px;
      }

      /* Step Content */
      .step-content {
        min-height: 400px;
        padding: 16px 0;
      }

      .step-header {
        margin-bottom: 24px;
      }

      .step-header h3 {
        font-size: 20px;
        font-weight: 600;
        color: #22433D;
        margin: 0 0 8px 0;
      }

      .step-header h3.rtl {
        font-family: 'Noto Sans Arabic', sans-serif;
        text-align: right;
      }

      .step-header p {
        color: #666;
        margin: 0;
      }

      .step-header p.rtl {
        font-family: 'Noto Sans Arabic', sans-serif;
        text-align: right;
      }

      /* Form Elements */
      .radio-options {
        display: flex;
        flex-direction: column;
        gap: 8px;
      }

      .radio-options label {
        padding: 8px 0;
      }

      .radio-options .rtl {
        font-family: 'Noto Sans Arabic', sans-serif;
        text-align: right;
      }

      .checkbox-options {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 8px;
        margin-top: 8px;
      }

      .checkbox-options label {
        padding: 8px 0;
      }

      .checkbox-options .rtl {
        font-family: 'Noto Sans Arabic', sans-serif;
        text-align: right;
      }

      .rtl input,
      .rtl textarea {
        text-align: right;
        font-family: 'Noto Sans Arabic', sans-serif;
      }

      /* Terms Carousel */
      .terms-carousel-container {
        width: 100%;
      }

      .terms-card {
        height: 400px;
        margin: 0 4px;
        overflow-y: auto;
      }

      .terms-card-header {
        display: flex;
        align-items: center;
        gap: 8px;
        flex-wrap: wrap;
      }

      .terms-card-header.rtl {
        flex-direction: row-reverse;
        text-align: right;
      }

      .terms-icon {
        font-size: 16px;
        color: #669B80;
      }

      .required-tag {
        margin-left: auto;
      }

      [dir="rtl"] .required-tag {
        margin-left: 0;
        margin-right: auto;
      }

      .terms-content {
        line-height: 1.6;
        color: #333;
      }

      .terms-content.rtl {
        font-family: 'Noto Sans Arabic', sans-serif;
        text-align: right;
      }

      .terms-content ul {
        padding-left: 20px;
        margin: 12px 0;
      }

      [dir="rtl"] .terms-content ul {
        padding-left: 0;
        padding-right: 20px;
      }

      .terms-content li {
        margin-bottom: 8px;
      }

      /* Carousel Navigation */
      .carousel-navigation {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-top: 16px;
        gap: 16px;
      }

      .carousel-progress {
        flex: 1;
        max-width: 300px;
      }

      .carousel-dot {
        width: 32px;
        height: 32px;
        border-radius: 50%;
        background: #f0f0f0;
        display: flex;
        align-items: center;
        justify-content: center;
        margin: 0 4px;
        transition: all 0.3s;
      }

      .carousel-dot.active {
        background: #669B80;
        color: white;
      }

      .dot-number {
        font-size: 12px;
        font-weight: 500;
      }

      /* Agreement Section */
      .agreement-section {
        margin-top: 16px;
      }

      .agreement-checkbox {
        padding: 16px;
        background: #f6ffed;
        border: 1px solid #b7eb8f;
        border-radius: 8px;
      }

      .agreement-checkbox label {
        font-weight: 500;
        color: #22433D;
      }

      .agreement-checkbox .rtl {
        font-family: 'Noto Sans Arabic', sans-serif;
        text-align: right;
      }

      /* Submission States */
      .submission-result {
        display: flex;
        align-items: center;
        justify-content: center;
        min-height: 400px;
      }

      .submission-loading {
        text-align: center;
      }

      .loading-content {
        max-width: 300px;
        margin: 0 auto;
      }

      .loading-message {
        margin-top: 16px;
        color: #666;
      }

      .success-actions,
      .error-actions {
        display: flex;
        gap: 12px;
        justify-content: center;
        flex-wrap: wrap;
      }

      .result-success ::ng-deep .ant-result-title {
        color: #52c41a;
      }

      .result-error ::ng-deep .ant-result-title {
        color: #ff4d4f;
      }

      /* Modal Footer */
      .modal-footer {
        display: flex;
        justify-content: flex-end;
        margin-top: 24px;
        padding-top: 16px;
        border-top: 1px solid #f0f0f0;
      }

      [dir="rtl"] .modal-footer {
        justify-content: flex-start;
      }

      /* Responsive Design */
      @media (max-width: 768px) {
        .resource-header {
          flex-direction: column;
        }

        .carousel-navigation {
          flex-direction: column;
          gap: 12px;
        }

        .carousel-progress {
          width: 100%;
          max-width: none;
        }

        .checkbox-options {
          grid-template-columns: 1fr;
        }

        .success-actions,
        .error-actions {
          flex-direction: column;
          width: 100%;
        }

        .success-actions button,
        .error-actions button {
          width: 100%;
        }
      }
    }
  `]
})
export class AccessRequestModalComponent implements OnInit {
  @Input() visible = false;
  @Input() resource: Resource | null = null;
  @Output() visibleChange = new EventEmitter<boolean>();
  @Output() requestSubmitted = new EventEmitter<string>(); // Access request ID

  private http = inject(HttpClient);
  private fb = inject(FormBuilder);
  private i18nService = inject(I18nService);

  // Reactive state
  protected readonly _isArabic = signal<boolean>(false);
  protected readonly _currentStep = signal<number>(0);
  protected readonly _currentTermsSlide = signal<number>(0);
  protected readonly _submitting = signal<boolean>(false);
  protected readonly _submissionProgress = signal<number>(0);
  protected readonly _submissionSuccess = signal<boolean>(false);
  protected readonly _submissionError = signal<string | null>(null);

  // Public reactive properties
  readonly isArabic = this._isArabic.asReadonly();
  readonly currentStep = this._currentStep.asReadonly();
  readonly currentTermsSlide = this._currentTermsSlide.asReadonly();
  readonly submitting = this._submitting.asReadonly();
  readonly submissionProgress = this._submissionProgress.asReadonly();
  readonly submissionSuccess = this._submissionSuccess.asReadonly();
  readonly submissionError = this._submissionError.asReadonly();

  // Form state
  agreeToTerms = false;
  viewedTermsSlides = new Set<number>();

  // Form
  purposeForm: FormGroup;

  // Options data
  projectTypeOptions = [
    { value: 'mobile_app', label_en: 'Mobile Application', label_ar: 'تطبيق الهاتف المحمول' },
    { value: 'web_app', label_en: 'Web Application', label_ar: 'تطبيق الويب' },
    { value: 'desktop_app', label_en: 'Desktop Software', label_ar: 'برنامج سطح المكتب' },
    { value: 'research', label_en: 'Academic Research', label_ar: 'البحث الأكاديمي' },
    { value: 'educational', label_en: 'Educational Content', label_ar: 'المحتوى التعليمي' },
    { value: 'publication', label_en: 'Publication/Book', label_ar: 'النشر/الكتاب' },
    { value: 'media', label_en: 'Media/Broadcasting', label_ar: 'الإعلام/البث' },
    { value: 'other', label_en: 'Other', label_ar: 'أخرى' }
  ];

  usageOptions = [
    { value: 'low', label_en: 'Low usage (< 1,000 requests/month)', label_ar: 'استخدام منخفض (< 1,000 طلب/شهر)' },
    { value: 'medium', label_en: 'Medium usage (1,000 - 10,000 requests/month)', label_ar: 'استخدام متوسط (1,000 - 10,000 طلب/شهر)' },
    { value: 'high', label_en: 'High usage (> 10,000 requests/month)', label_ar: 'استخدام عالي (> 10,000 طلب/شهر)' }
  ];

  distributionOptions = [
    { value: 'api', label_en: 'API Integration', label_ar: 'تكامل API' },
    { value: 'download', label_en: 'Direct Download', label_ar: 'التحميل المباشر' },
    { value: 'embedded', label_en: 'Embedded Content', label_ar: 'المحتوى المدمج' },
    { value: 'print', label_en: 'Print/Physical Media', label_ar: 'الطباعة/الوسائط المادية' }
  ];

  audienceOptions = [
    { value: 'muslims', label_en: 'Muslim Community', label_ar: 'المجتمع المسلم' },
    { value: 'students', label_en: 'Students/Researchers', label_ar: 'الطلاب/الباحثون' },
    { value: 'general', label_en: 'General Public', label_ar: 'الجمهور العام' },
    { value: 'scholars', label_en: 'Islamic Scholars', label_ar: 'علماء الإسلام' },
    { value: 'developers', label_en: 'Developers/Tech Community', label_ar: 'المطورون/مجتمع التكنولوجيا' }
  ];

  // License terms data
  licenseTerms: LicenseTerms[] = [
    {
      id: 'attribution',
      title_en: 'Attribution Requirements',
      title_ar: 'متطلبات الإسناد',
      content_en: `
        <p>When using this Islamic content, you must provide proper attribution:</p>
        <ul>
          <li>Include the original source citation</li>
          <li>Mention the publisher and scholarly review process</li>
          <li>Provide a link back to Itqan CMS when possible</li>
          <li>Maintain all copyright notices and checksums</li>
        </ul>
        <p><strong>Example Attribution:</strong><br>
        "Quranic content verified by [Publisher Name] via Itqan CMS (https://itqan-cms.com)"</p>
      `,
      content_ar: `
        <p>عند استخدام هذا المحتوى الإسلامي، يجب تقديم الإسناد المناسب:</p>
        <ul>
          <li>تضمين اقتباس المصدر الأصلي</li>
          <li>ذكر الناشر وعملية المراجعة العلمية</li>
          <li>توفير رابط إلى نظام إتقان عند الإمكان</li>
          <li>المحافظة على جميع إشعارات حقوق الطبع ومجاميع التحقق</li>
        </ul>
        <p><strong>مثال على الإسناد:</strong><br>
        "محتوى قرآني تم التحقق منه بواسطة [اسم الناشر] عبر نظام إتقان (https://itqan-cms.com)"</p>
      `,
      icon: '©️',
      required: true
    },
    {
      id: 'integrity',
      title_en: 'Content Integrity',
      title_ar: 'سلامة المحتوى',
      content_en: `
        <p>Islamic content integrity is paramount. You agree to:</p>
        <ul>
          <li>Never modify or alter Quranic text in any way</li>
          <li>Verify content checksums before distribution</li>
          <li>Report any discrepancies immediately</li>
          <li>Use only verified, scholarly-reviewed content</li>
        </ul>
        <p><strong>Checksum Verification:</strong> SHA-256 checksums must be validated to ensure content authenticity.</p>
      `,
      content_ar: `
        <p>سلامة المحتوى الإسلامي أمر بالغ الأهمية. أنت توافق على:</p>
        <ul>
          <li>عدم تعديل أو تغيير النص القرآني بأي شكل من الأشكال</li>
          <li>التحقق من مجاميع التحقق قبل التوزيع</li>
          <li>الإبلاغ عن أي اختلافات على الفور</li>
          <li>استخدام المحتوى المتحقق منه والمراجع علمياً فقط</li>
        </ul>
        <p><strong>التحقق من مجموع التحقق:</strong> يجب التحقق من مجاميع SHA-256 لضمان أصالة المحتوى.</p>
      `,
      icon: '🔒',
      required: true
    },
    {
      id: 'usage',
      title_en: 'Usage Guidelines',
      title_ar: 'إرشادات الاستخدام',
      content_en: `
        <p>Responsible usage of Islamic content requires:</p>
        <ul>
          <li>Respectful presentation in appropriate contexts</li>
          <li>No use in prohibited (haram) activities or contexts</li>
          <li>Compliance with Islamic copyright principles</li>
          <li>Regular updates to ensure content accuracy</li>
        </ul>
        <p><strong>Prohibited Uses:</strong> Content cannot be used in gambling, alcohol, adult content, or any non-Islamic contexts.</p>
      `,
      content_ar: `
        <p>الاستخدام المسؤول للمحتوى الإسلامي يتطلب:</p>
        <ul>
          <li>العرض المحترم في السياقات المناسبة</li>
          <li>عدم الاستخدام في الأنشطة أو السياقات المحرمة</li>
          <li>الامتثال لمبادئ حقوق الطبع الإسلامية</li>
          <li>التحديثات المنتظمة لضمان دقة المحتوى</li>
        </ul>
        <p><strong>الاستخدامات المحظورة:</strong> لا يمكن استخدام المحتوى في القمار أو الكحول أو المحتوى للبالغين أو أي سياقات غير إسلامية.</p>
      `,
      icon: '📋',
      required: true
    },
    {
      id: 'distribution',
      title_en: 'Distribution Rights',
      title_ar: 'حقوق التوزيع',
      content_en: `
        <p>Distribution of Islamic content is subject to:</p>
        <ul>
          <li>Maintaining original attribution and licensing</li>
          <li>Not sublicensing without explicit permission</li>
          <li>Reporting distribution statistics when requested</li>
          <li>Ensuring downstream users follow same guidelines</li>
        </ul>
        <p><strong>Commercial Use:</strong> Commercial distribution may require additional licensing agreements.</p>
      `,
      content_ar: `
        <p>توزيع المحتوى الإسلامي يخضع لـ:</p>
        <ul>
          <li>المحافظة على الإسناد والترخيص الأصلي</li>
          <li>عدم منح تراخيص فرعية دون إذن صريح</li>
          <li>الإبلاغ عن إحصائيات التوزيع عند الطلب</li>
          <li>ضمان اتباع المستخدمين النهائيين لنفس الإرشادات</li>
        </ul>
        <p><strong>الاستخدام التجاري:</strong> قد يتطلب التوزيع التجاري اتفاقيات ترخيص إضافية.</p>
      `,
      icon: '🔄',
      required: false
    }
  ];

  constructor() {
    // Initialize form
    this.purposeForm = this.fb.group({
      project_type: ['', Validators.required],
      expected_usage: ['', Validators.required],
      distribution_method: ['', Validators.required],
      target_audience: [[], Validators.required],
      organization: [''],
      justification: ['', [Validators.required, Validators.minLength(50)]]
    });

    // Language detection effect
    effect(() => {
      this._isArabic.set(this.i18nService.currentLanguage() === 'ar');
    });
  }

  ngOnInit() {
    this.initializeViewedTerms();
  }

  get modalTitle(): string {
    if (this.currentStep() === 0) {
      return this.t('access_request.request_access');
    } else if (this.currentStep() === 1) {
      return this.t('access_request.review_terms');
    } else {
      return this.t('access_request.submission_status');
    }
  }

  // Step navigation
  nextStep(): void {
    if (this.currentStep() === 0 && this.purposeForm.valid) {
      this._currentStep.set(1);
    } else if (this.currentStep() === 1 && this.agreeToTerms && this.allTermsViewed()) {
      this.submitRequest();
    }
  }

  previousStep(): void {
    if (this.currentStep() > 0) {
      this._currentStep.set(this.currentStep() - 1);
    }
  }

  canProceed(): boolean {
    if (this.currentStep() === 0) {
      return this.purposeForm.valid;
    } else if (this.currentStep() === 1) {
      return this.agreeToTerms && this.allTermsViewed();
    }
    return false;
  }

  getNextButtonLabel(): string {
    if (this.currentStep() === 0) {
      return this.t('access_request.review_terms_btn');
    } else if (this.currentStep() === 1) {
      return this.t('access_request.submit_request');
    }
    return this.t('common.next');
  }

  // Terms carousel navigation
  nextTerms(): void {
    const nextSlide = this.currentTermsSlide() + 1;
    if (nextSlide < this.licenseTerms.length) {
      this._currentTermsSlide.set(nextSlide);
      this.viewedTermsSlides.add(nextSlide);
    }
  }

  previousTerms(): void {
    const prevSlide = this.currentTermsSlide() - 1;
    if (prevSlide >= 0) {
      this._currentTermsSlide.set(prevSlide);
    }
  }

  getTermsProgress(): number {
    return Math.round(((this.currentTermsSlide() + 1) / this.licenseTerms.length) * 100);
  }

  progressFormat = (percent: number): string => {
    return `${this.currentTermsSlide() + 1}/${this.licenseTerms.length}`;
  };

  allTermsViewed(): boolean {
    return this.viewedTermsSlides.size >= this.licenseTerms.length;
  }

  private initializeViewedTerms(): void {
    this.viewedTermsSlides.add(0); // First slide is viewed by default
  }

  // Request submission
  private async submitRequest(): Promise<void> {
    if (!this.resource || !this.purposeForm.valid || !this.agreeToTerms) {
      return;
    }

    this._currentStep.set(2);
    this._submitting.set(true);
    this._submissionProgress.set(0);
    this._submissionError.set(null);

    try {
      // Simulate progress updates
      const progressInterval = setInterval(() => {
        const currentProgress = this.submissionProgress();
        if (currentProgress < 90) {
          this._submissionProgress.set(currentProgress + 10);
        }
      }, 200);

      const requestData: AccessRequestData = {
        resource_id: this.resource.id,
        purpose: this.purposeForm.value.justification,
        project_type: this.purposeForm.value.project_type,
        expected_usage: this.purposeForm.value.expected_usage,
        distribution_method: this.purposeForm.value.distribution_method,
        target_audience: this.purposeForm.value.target_audience.join(','),
        organization: this.purposeForm.value.organization || undefined,
        justification: this.purposeForm.value.justification,
        agree_to_terms: this.agreeToTerms
      };

      const response = await this.http.post<{ id: string }>(`${environment.apiUrl}/licensing/access-requests/`, requestData).toPromise();

      clearInterval(progressInterval);
      this._submissionProgress.set(100);

      if (response?.id) {
        this._submissionSuccess.set(true);
        this.requestSubmitted.emit(response.id);
      } else {
        throw new Error('Invalid response from server');
      }

    } catch (error) {
      console.error('Access request submission error:', error);
      this._submissionError.set(this.t('access_request.submission_error'));
    } finally {
      this._submitting.set(false);
    }
  }

  retrySubmission(): void {
    this._submissionError.set(null);
    this.submitRequest();
  }

  // Modal actions
  onCancel(): void {
    this.visible = false;
    this.visibleChange.emit(false);
    this.resetModal();
  }

  private resetModal(): void {
    this._currentStep.set(0);
    this._currentTermsSlide.set(0);
    this._submitting.set(false);
    this._submissionProgress.set(0);
    this._submissionSuccess.set(false);
    this._submissionError.set(null);
    this.agreeToTerms = false;
    this.viewedTermsSlides.clear();
    this.initializeViewedTerms();
    this.purposeForm.reset();
  }

  // Result actions
  viewMyRequests(): void {
    // Navigate to user's access requests
    this.onCancel();
  }

  browseMore(): void {
    // Navigate back to resource browsing
    this.onCancel();
  }

  /**
   * Translation helper method
   */
  t(key: string, params?: any): string {
    return this.i18nService.translate(key, params);
  }
}
