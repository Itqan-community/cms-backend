import { Component, OnInit, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, FormGroup, Validators, ReactiveFormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';
import { NzLayoutModule } from 'ng-zorro-antd/layout';
import { NzBreadCrumbModule } from 'ng-zorro-antd/breadcrumb';
import { NzButtonModule } from 'ng-zorro-antd/button';
import { NzCardModule } from 'ng-zorro-antd/card';
import { NzGridModule } from 'ng-zorro-antd/grid';
import { NzIconModule } from 'ng-zorro-antd/icon';
import { NzFormModule } from 'ng-zorro-antd/form';
import { NzInputModule } from 'ng-zorro-antd/input';
import { NzSelectModule } from 'ng-zorro-antd/select';
import { NzTextareaModule } from 'ng-zorro-antd/input';
import { NzSwitchModule } from 'ng-zorro-antd/switch';
import { NzTabsModule } from 'ng-zorro-antd/tabs';
import { NzTagModule } from 'ng-zorro-antd/tag';
import { NzStepsModule } from 'ng-zorro-antd/steps';
import { NzDividerModule } from 'ng-zorro-antd/divider';
import { NzSpaceModule } from 'ng-zorro-antd/space';
import { NzTypographyModule } from 'ng-zorro-antd/typography';
import { NzMessageModule, NzMessageService } from 'ng-zorro-antd/message';
import { NzModalModule, NzModalService } from 'ng-zorro-antd/modal';
import { NzSpinModule } from 'ng-zorro-antd/spin';
import { NzAlertModule } from 'ng-zorro-antd/alert';
import { NzUploadModule } from 'ng-zorro-antd/upload';
import { NzCheckboxModule } from 'ng-zorro-antd/checkbox';

import { environment } from '../../../../environments/environment';
import { I18nService } from '../../../core/services/i18n.service';

/**
 * ADMIN-003: Content Creation Component
 * 
 * Implements bilingual content creation forms with EN/AR locale switching
 * following the ADMIN-003 wireframe design with NG-ZORRO components
 */

interface Resource {
  id?: string;
  title_en: string;
  title_ar: string;
  description_en: string;
  description_ar: string;
  resource_type: string;
  language: string;
  version: string;
  checksum?: string;
  publisher?: string;
  metadata: any;
  published_at?: string;
}

interface License {
  id?: string;
  license_type: string;
  terms_en: string;
  terms_ar: string;
  geographic_restrictions: any;
  usage_restrictions: any;
  requires_approval: boolean;
  effective_from: string;
  expires_at?: string;
}

interface Distribution {
  id?: string;
  format_type: string;
  endpoint_url: string;
  version: string;
  access_config: any;
  metadata: any;
}

interface ContentForm {
  resource: Resource;
  licenses: License[];
  distributions: Distribution[];
}

@Component({
  selector: 'app-content-creation',
  standalone: true,
  imports: [
    CommonModule,
    ReactiveFormsModule,
    NzLayoutModule,
    NzBreadCrumbModule,
    NzButtonModule,
    NzCardModule,
    NzGridModule,
    NzIconModule,
    NzFormModule,
    NzInputModule,
    NzSelectModule,
    NzTextareaModule,
    NzSwitchModule,
    NzTabsModule,
    NzTagModule,
    NzStepsModule,
    NzDividerModule,
    NzSpaceModule,
    NzTypographyModule,
    NzMessageModule,
    NzModalModule,
    NzSpinModule,
    NzAlertModule,
    NzUploadModule,
    NzCheckboxModule
  ],
  template: `
    <nz-layout class="content-creation">
      <!-- Header -->
      <nz-header class="content-header">
        <nz-breadcrumb>
          <nz-breadcrumb-item>
            <span nz-icon nzType="home"></span>
            Admin
          </nz-breadcrumb-item>
          <nz-breadcrumb-item>
            <span nz-icon nzType="file-text"></span>
            Content Creation
          </nz-breadcrumb-item>
        </nz-breadcrumb>

        <div class="header-actions">
          <!-- Language Switcher -->
          <div class="language-switcher">
            <nz-button-group>
              <button 
                nz-button 
                [nzType]="currentLocale() === 'en' ? 'primary' : 'default'"
                (click)="switchLocale('en')">
                <span nz-icon nzType="global"></span>
                English
              </button>
              <button 
                nz-button 
                [nzType]="currentLocale() === 'ar' ? 'primary' : 'default'"
                (click)="switchLocale('ar')">
                <span nz-icon nzType="global"></span>
                العربية
              </button>
            </nz-button-group>
          </div>

          <nz-divider nzType="vertical"></nz-divider>

          <button nz-button nzType="default" (click)="saveDraft()" [nzLoading]="isSaving()">
            <span nz-icon nzType="save"></span>
            Save Draft
          </button>
          <button nz-button nzType="primary" (click)="submitForReview()" [nzLoading]="isSubmitting()">
            <span nz-icon nzType="check"></span>
            Submit for Review
          </button>
        </div>
      </nz-header>

      <nz-content class="content-main">
        <!-- Progress Steps -->
        <nz-card class="steps-card">
          <nz-steps [nzCurrent]="currentStep()" nzSize="small">
            <nz-step nzTitle="Basic Info" nzIcon="info-circle"></nz-step>
            <nz-step nzTitle="Content Details" nzIcon="file-text"></nz-step>
            <nz-step nzTitle="Licensing" nzIcon="safety-certificate"></nz-step>
            <nz-step nzTitle="Distribution" nzIcon="cloud-upload"></nz-step>
            <nz-step nzTitle="Review" nzIcon="eye"></nz-step>
          </nz-steps>
        </nz-card>

        <!-- Content Creation Form -->
        <form nz-form [formGroup]="contentForm" [nzLayout]="'vertical'">
          
          <!-- Step 1: Basic Information -->
          @if (currentStep() === 0) {
            <nz-card nzTitle="Basic Information" class="form-card">
              <div class="locale-tabs">
                <nz-tabs [(nzSelectedIndex)]="selectedTabIndex()" (nzSelectedIndexChange)="onTabChange($event)">
                  <!-- English Tab -->
                  <nz-tab-pane nzTab="English Content">
                    <div nz-row [nzGutter]="[24, 16]">
                      <div nz-col [nzSpan]="24">
                        <nz-form-item>
                          <nz-form-label nzRequired>Title (English)</nz-form-label>
                          <nz-form-control nzErrorTip="Please enter the English title">
                            <input nz-input formControlName="title_en" placeholder="Enter resource title in English">
                          </nz-form-control>
                        </nz-form-item>
                      </div>

                      <div nz-col [nzSpan]="24">
                        <nz-form-item>
                          <nz-form-label nzRequired>Description (English)</nz-form-label>
                          <nz-form-control nzErrorTip="Please enter the English description">
                            <textarea nz-input formControlName="description_en" rows="4" 
                              placeholder="Detailed description of the resource content in English"></textarea>
                          </nz-form-control>
                        </nz-form-item>
                      </div>
                    </div>
                  </nz-tab-pane>

                  <!-- Arabic Tab -->
                  <nz-tab-pane nzTab="المحتوى العربي">
                    <div nz-row [nzGutter]="[24, 16]" class="rtl-content">
                      <div nz-col [nzSpan]="24">
                        <nz-form-item>
                          <nz-form-label nzRequired>العنوان (العربية)</nz-form-label>
                          <nz-form-control nzErrorTip="يرجى إدخال العنوان بالعربية">
                            <input nz-input formControlName="title_ar" placeholder="أدخل عنوان المصدر بالعربية" 
                              dir="rtl">
                          </nz-form-control>
                        </nz-form-item>
                      </div>

                      <div nz-col [nzSpan]="24">
                        <nz-form-item>
                          <nz-form-label nzRequired>الوصف (العربية)</nz-form-label>
                          <nz-form-control nzErrorTip="يرجى إدخال الوصف بالعربية">
                            <textarea nz-input formControlName="description_ar" rows="4" 
                              placeholder="وصف مفصل لمحتوى المصدر بالعربية" dir="rtl"></textarea>
                          </nz-form-control>
                        </nz-form-item>
                      </div>
                    </div>
                  </nz-tab-pane>
                </nz-tabs>
              </div>

              <nz-divider></nz-divider>

              <!-- Common Fields -->
              <div nz-row [nzGutter]="[24, 16]">
                <div nz-col [nzSpan]="8">
                  <nz-form-item>
                    <nz-form-label nzRequired>Resource Type</nz-form-label>
                    <nz-form-control nzErrorTip="Please select resource type">
                      <nz-select formControlName="resource_type" nzPlaceHolder="Select type">
                        <nz-option nzValue="text" nzLabel="Quranic Text"></nz-option>
                        <nz-option nzValue="audio" nzLabel="Audio Recitation"></nz-option>
                        <nz-option nzValue="translation" nzLabel="Translation"></nz-option>
                        <nz-option nzValue="tafsir" nzLabel="Tafsir (Commentary)"></nz-option>
                      </nz-select>
                    </nz-form-control>
                  </nz-form-item>
                </div>

                <div nz-col [nzSpan]="8">
                  <nz-form-item>
                    <nz-form-label nzRequired>Primary Language</nz-form-label>
                    <nz-form-control nzErrorTip="Please select primary language">
                      <nz-select formControlName="language" nzPlaceHolder="Select language">
                        <nz-option nzValue="ar" nzLabel="Arabic (العربية)"></nz-option>
                        <nz-option nzValue="en" nzLabel="English"></nz-option>
                        <nz-option nzValue="ur" nzLabel="Urdu (اردو)"></nz-option>
                        <nz-option nzValue="tr" nzLabel="Turkish (Türkçe)"></nz-option>
                        <nz-option nzValue="id" nzLabel="Indonesian (Bahasa Indonesia)"></nz-option>
                        <nz-option nzValue="ms" nzLabel="Malay (Bahasa Melayu)"></nz-option>
                      </nz-select>
                    </nz-form-control>
                  </nz-form-item>
                </div>

                <div nz-col [nzSpan]="8">
                  <nz-form-item>
                    <nz-form-label nzRequired>Version</nz-form-label>
                    <nz-form-control nzErrorTip="Please enter version">
                      <input nz-input formControlName="version" placeholder="e.g., 1.0, 2.1">
                    </nz-form-control>
                  </nz-form-item>
                </div>
              </div>

              <div class="step-actions">
                <button nz-button nzType="primary" (click)="nextStep()">
                  Next: Content Details
                  <span nz-icon nzType="arrow-right"></span>
                </button>
              </div>
            </nz-card>
          }

          <!-- Step 2: Content Details -->
          @if (currentStep() === 1) {
            <nz-card nzTitle="Content Details & Metadata" class="form-card">
              <div nz-row [nzGutter]="[24, 16]">
                <div nz-col [nzSpan]="24">
                  <h4>Islamic Content Metadata</h4>
                  
                  <!-- Resource Type Specific Fields -->
                  @if (contentForm.get('resource_type')?.value === 'audio') {
                    <div nz-row [nzGutter]="[16, 16]">
                      <div nz-col [nzSpan]="8">
                        <nz-form-item>
                          <nz-form-label>Reciter Name</nz-form-label>
                          <nz-form-control>
                            <input nz-input [value]="getMetadataField('reciter')" 
                              (input)="setMetadataField('reciter', $event)" placeholder="Reciter name">
                          </nz-form-control>
                        </nz-form-item>
                      </div>
                      <div nz-col [nzSpan]="8">
                        <nz-form-item>
                          <nz-form-label>Audio Quality</nz-form-label>
                          <nz-form-control>
                            <nz-select [ngModel]="getMetadataField('quality')" 
                              (ngModelChange)="setMetadataField('quality', $event)" nzPlaceHolder="Select quality">
                              <nz-option nzValue="128kbps" nzLabel="128 kbps"></nz-option>
                              <nz-option nzValue="192kbps" nzLabel="192 kbps"></nz-option>
                              <nz-option nzValue="320kbps" nzLabel="320 kbps"></nz-option>
                              <nz-option nzValue="lossless" nzLabel="Lossless"></nz-option>
                            </nz-select>
                          </nz-form-control>
                        </nz-form-item>
                      </div>
                      <div nz-col [nzSpan]="8">
                        <nz-form-item>
                          <nz-form-label>Duration (minutes)</nz-form-label>
                          <nz-form-control>
                            <input nz-input type="number" [value]="getMetadataField('duration')" 
                              (input)="setMetadataField('duration', $event)" placeholder="Duration">
                          </nz-form-control>
                        </nz-form-item>
                      </div>
                    </div>
                  }

                  @if (contentForm.get('resource_type')?.value === 'text') {
                    <div nz-row [nzGutter]="[16, 16]">
                      <div nz-col [nzSpan]="8">
                        <nz-form-item>
                          <nz-form-label>Mushaf Type</nz-form-label>
                          <nz-form-control>
                            <nz-select [ngModel]="getMetadataField('mushaf_type')" 
                              (ngModelChange)="setMetadataField('mushaf_type', $event)" nzPlaceHolder="Select type">
                              <nz-option nzValue="uthmani" nzLabel="Uthmani Script"></nz-option>
                              <nz-option nzValue="simple" nzLabel="Simple Script"></nz-option>
                              <nz-option nzValue="indopak" nzLabel="Indo-Pak Script"></nz-option>
                            </nz-select>
                          </nz-form-control>
                        </nz-form-item>
                      </div>
                      <div nz-col [nzSpan]="8">
                        <nz-form-item>
                          <nz-form-label>Include Diacritics</nz-form-label>
                          <nz-form-control>
                            <nz-switch [ngModel]="getMetadataField('include_diacritics')" 
                              (ngModelChange)="setMetadataField('include_diacritics', $event)"></nz-switch>
                          </nz-form-control>
                        </nz-form-item>
                      </div>
                      <div nz-col [nzSpan]="8">
                        <nz-form-item>
                          <nz-form-label>Verse Count</nz-form-label>
                          <nz-form-control>
                            <input nz-input type="number" [value]="getMetadataField('verse_count')" 
                              (input)="setMetadataField('verse_count', $event)" placeholder="6236">
                          </nz-form-control>
                        </nz-form-item>
                      </div>
                    </div>
                  }

                  @if (contentForm.get('resource_type')?.value === 'translation') {
                    <div nz-row [nzGutter]="[16, 16]">
                      <div nz-col [nzSpan]="8">
                        <nz-form-item>
                          <nz-form-label>Translator Name</nz-form-label>
                          <nz-form-control>
                            <input nz-input [value]="getMetadataField('translator')" 
                              (input)="setMetadataField('translator', $event)" placeholder="Translator name">
                          </nz-form-control>
                        </nz-form-item>
                      </div>
                      <div nz-col [nzSpan]="8">
                        <nz-form-item>
                          <nz-form-label>Translation Style</nz-form-label>
                          <nz-form-control>
                            <nz-select [ngModel]="getMetadataField('style')" 
                              (ngModelChange)="setMetadataField('style', $event)" nzPlaceHolder="Select style">
                              <nz-option nzValue="literal" nzLabel="Literal"></nz-option>
                              <nz-option nzValue="interpretive" nzLabel="Interpretive"></nz-option>
                              <nz-option nzValue="poetic" nzLabel="Poetic"></nz-option>
                            </nz-select>
                          </nz-form-control>
                        </nz-form-item>
                      </div>
                      <div nz-col [nzSpan]="8">
                        <nz-form-item>
                          <nz-form-label>Publication Year</nz-form-label>
                          <nz-form-control>
                            <input nz-input type="number" [value]="getMetadataField('publication_year')" 
                              (input)="setMetadataField('publication_year', $event)" placeholder="2023">
                          </nz-form-control>
                        </nz-form-item>
                      </div>
                    </div>
                  }
                </div>
              </div>

              <div class="step-actions">
                <button nz-button nzType="default" (click)="previousStep()">
                  <span nz-icon nzType="arrow-left"></span>
                  Previous
                </button>
                <button nz-button nzType="primary" (click)="nextStep()">
                  Next: Licensing
                  <span nz-icon nzType="arrow-right"></span>
                </button>
              </div>
            </nz-card>
          }

          <!-- Step 3: Licensing -->
          @if (currentStep() === 2) {
            <nz-card nzTitle="License Configuration" class="form-card">
              <nz-alert 
                nzType="info" 
                nzMessage="Configure licensing terms for this Islamic content. These terms will govern how developers can use this resource."
                nzShowIcon
                class="license-info">
              </nz-alert>

              <div formArrayName="licenses">
                @for (license of getLicenseControls(); track $index; let i = $index) {
                  <nz-card [nzTitle]="'License ' + (i + 1)" class="license-card" [formGroupName]="i">
                    <div class="license-tabs">
                      <nz-tabs>
                        <!-- English License Terms -->
                        <nz-tab-pane nzTab="English Terms">
                          <nz-form-item>
                            <nz-form-label nzRequired>License Terms (English)</nz-form-label>
                            <nz-form-control nzErrorTip="Please enter license terms in English">
                              <textarea nz-input formControlName="terms_en" rows="6" 
                                placeholder="Enter detailed license terms and conditions in English"></textarea>
                            </nz-form-control>
                          </nz-form-item>
                        </nz-tab-pane>

                        <!-- Arabic License Terms -->
                        <nz-tab-pane nzTab="الشروط العربية">
                          <div class="rtl-content">
                            <nz-form-item>
                              <nz-form-label nzRequired>شروط الترخيص (العربية)</nz-form-label>
                              <nz-form-control nzErrorTip="يرجى إدخال شروط الترخيص بالعربية">
                                <textarea nz-input formControlName="terms_ar" rows="6" 
                                  placeholder="أدخل شروط وأحكام الترخيص المفصلة بالعربية" dir="rtl"></textarea>
                              </nz-form-control>
                            </nz-form-item>
                          </div>
                        </nz-tab-pane>
                      </nz-tabs>
                    </div>

                    <div nz-row [nzGutter]="[16, 16]">
                      <div nz-col [nzSpan]="8">
                        <nz-form-item>
                          <nz-form-label nzRequired>License Type</nz-form-label>
                          <nz-form-control>
                            <nz-select formControlName="license_type" nzPlaceHolder="Select type">
                              <nz-option nzValue="open" nzLabel="Open License"></nz-option>
                              <nz-option nzValue="restricted" nzLabel="Restricted License"></nz-option>
                              <nz-option nzValue="commercial" nzLabel="Commercial License"></nz-option>
                            </nz-select>
                          </nz-form-control>
                        </nz-form-item>
                      </div>

                      <div nz-col [nzSpan]="8">
                        <nz-form-item>
                          <nz-form-label>Requires Approval</nz-form-label>
                          <nz-form-control>
                            <nz-switch formControlName="requires_approval"></nz-switch>
                          </nz-form-control>
                        </nz-form-item>
                      </div>

                      <div nz-col [nzSpan]="8" *ngIf="i > 0">
                        <button nz-button nzType="text" nzDanger (click)="removeLicense(i)">
                          <span nz-icon nzType="delete"></span>
                          Remove License
                        </button>
                      </div>
                    </div>
                  </nz-card>
                }

                <button nz-button nzType="dashed" (click)="addLicense()" class="add-license-btn">
                  <span nz-icon nzType="plus"></span>
                  Add Additional License
                </button>
              </div>

              <div class="step-actions">
                <button nz-button nzType="default" (click)="previousStep()">
                  <span nz-icon nzType="arrow-left"></span>
                  Previous
                </button>
                <button nz-button nzType="primary" (click)="nextStep()">
                  Next: Distribution
                  <span nz-icon nzType="arrow-right"></span>
                </button>
              </div>
            </nz-card>
          }

          <!-- Step 4: Distribution -->
          @if (currentStep() === 3) {
            <nz-card nzTitle="Distribution Configuration" class="form-card">
              <nz-alert 
                nzType="info" 
                nzMessage="Configure how developers will access this content. You can provide multiple access methods."
                nzShowIcon
                class="distribution-info">
              </nz-alert>

              <div formArrayName="distributions">
                @for (distribution of getDistributionControls(); track $index; let i = $index) {
                  <nz-card [nzTitle]="'Distribution Method ' + (i + 1)" class="distribution-card" [formGroupName]="i">
                    <div nz-row [nzGutter]="[16, 16]">
                      <div nz-col [nzSpan]="8">
                        <nz-form-item>
                          <nz-form-label nzRequired>Format Type</nz-form-label>
                          <nz-form-control>
                            <nz-select formControlName="format_type" nzPlaceHolder="Select format">
                              <nz-option nzValue="REST_JSON" nzLabel="REST API (JSON)"></nz-option>
                              <nz-option nzValue="GraphQL" nzLabel="GraphQL API"></nz-option>
                              <nz-option nzValue="ZIP" nzLabel="ZIP Download"></nz-option>
                              <nz-option nzValue="API" nzLabel="Custom API"></nz-option>
                            </nz-select>
                          </nz-form-control>
                        </nz-form-item>
                      </div>

                      <div nz-col [nzSpan]="16">
                        <nz-form-item>
                          <nz-form-label nzRequired>Endpoint URL</nz-form-label>
                          <nz-form-control nzErrorTip="Please enter a valid URL">
                            <input nz-input formControlName="endpoint_url" 
                              placeholder="https://api.itqan.dev/v1/resources/..." type="url">
                          </nz-form-control>
                        </nz-form-item>
                      </div>

                      <div nz-col [nzSpan]="8">
                        <nz-form-item>
                          <nz-form-label>Version</nz-form-label>
                          <nz-form-control>
                            <input nz-input formControlName="version" placeholder="1.0">
                          </nz-form-control>
                        </nz-form-item>
                      </div>

                      <div nz-col [nzSpan]="16" *ngIf="i > 0">
                        <button nz-button nzType="text" nzDanger (click)="removeDistribution(i)">
                          <span nz-icon nzType="delete"></span>
                          Remove Distribution Method
                        </button>
                      </div>
                    </div>
                  </nz-card>
                }

                <button nz-button nzType="dashed" (click)="addDistribution()" class="add-distribution-btn">
                  <span nz-icon nzType="plus"></span>
                  Add Distribution Method
                </button>
              </div>

              <div class="step-actions">
                <button nz-button nzType="default" (click)="previousStep()">
                  <span nz-icon nzType="arrow-left"></span>
                  Previous
                </button>
                <button nz-button nzType="primary" (click)="nextStep()">
                  Next: Review
                  <span nz-icon nzType="arrow-right"></span>
                </button>
              </div>
            </nz-card>
          }

          <!-- Step 5: Review -->
          @if (currentStep() === 4) {
            <nz-card nzTitle="Review & Submit" class="form-card">
              <nz-alert 
                nzType="success" 
                nzMessage="Please review all the information below before submitting your content for review."
                nzShowIcon
                class="review-info">
              </nz-alert>

              <!-- Resource Summary -->
              <nz-card nzTitle="Resource Summary" nzSize="small" class="summary-card">
                <div nz-row [nzGutter]="[16, 16]">
                  <div nz-col [nzSpan]="12">
                    <strong>English Title:</strong> {{ contentForm.get('title_en')?.value }}
                  </div>
                  <div nz-col [nzSpan]="12">
                    <strong>Arabic Title:</strong> {{ contentForm.get('title_ar')?.value }}
                  </div>
                  <div nz-col [nzSpan]="12">
                    <strong>Resource Type:</strong> {{ contentForm.get('resource_type')?.value | titlecase }}
                  </div>
                  <div nz-col [nzSpan]="12">
                    <strong>Primary Language:</strong> {{ getLanguageDisplay(contentForm.get('language')?.value) }}
                  </div>
                </div>
              </nz-card>

              <!-- License Summary -->
              <nz-card nzTitle="Licenses" nzSize="small" class="summary-card">
                @for (license of getLicenseControls(); track $index; let i = $index) {
                  <div class="license-summary">
                    <strong>License {{ i + 1 }}:</strong> 
                    {{ license.get('license_type')?.value | titlecase }}
                    @if (license.get('requires_approval')?.value) {
                      <nz-tag nzColor="orange">Requires Approval</nz-tag>
                    }
                  </div>
                }
              </nz-card>

              <!-- Distribution Summary -->
              <nz-card nzTitle="Distribution Methods" nzSize="small" class="summary-card">
                @for (distribution of getDistributionControls(); track $index; let i = $index) {
                  <div class="distribution-summary">
                    <strong>Method {{ i + 1 }}:</strong> 
                    {{ distribution.get('format_type')?.value }}
                    <br>
                    <small>{{ distribution.get('endpoint_url')?.value }}</small>
                  </div>
                }
              </nz-card>

              <div class="step-actions">
                <button nz-button nzType="default" (click)="previousStep()">
                  <span nz-icon nzType="arrow-left"></span>
                  Previous
                </button>
                <button nz-button nzType="primary" (click)="submitContent()" [nzLoading]="isSubmitting()">
                  <span nz-icon nzType="check"></span>
                  Submit Content
                </button>
              </div>
            </nz-card>
          }
        </form>
      </nz-content>
    </nz-layout>
  `,
  styleUrls: ['./content-creation.component.scss']
})
export class ContentCreationComponent implements OnInit {
  private readonly fb = inject(FormBuilder);
  private readonly http = inject(HttpClient);
  private readonly message = inject(NzMessageService);
  private readonly modal = inject(NzModalService);
  private readonly router = inject(Router);
  public readonly i18n = inject(I18nService);

  // Form and state
  contentForm!: FormGroup;
  currentStep = signal(0);
  selectedTabIndex = signal(0);
  currentLocale = signal<'en' | 'ar'>('en');
  
  // Loading states
  isSaving = signal(false);
  isSubmitting = signal(false);

  ngOnInit(): void {
    this.initializeForm();
  }

  initializeForm(): void {
    this.contentForm = this.fb.group({
      // Resource fields
      title_en: ['', [Validators.required]],
      title_ar: ['', [Validators.required]],
      description_en: ['', [Validators.required]],
      description_ar: ['', [Validators.required]],
      resource_type: ['', [Validators.required]],
      language: ['', [Validators.required]],
      version: ['1.0', [Validators.required]],
      metadata: [{}],
      
      // Licenses array
      licenses: this.fb.array([this.createLicenseGroup()]),
      
      // Distributions array
      distributions: this.fb.array([this.createDistributionGroup()])
    });
  }

  createLicenseGroup(): FormGroup {
    return this.fb.group({
      license_type: ['open', [Validators.required]],
      terms_en: ['', [Validators.required]],
      terms_ar: ['', [Validators.required]],
      requires_approval: [true],
      geographic_restrictions: [{}],
      usage_restrictions: [{}],
      effective_from: [new Date().toISOString()],
      expires_at: [null]
    });
  }

  createDistributionGroup(): FormGroup {
    return this.fb.group({
      format_type: ['REST_JSON', [Validators.required]],
      endpoint_url: ['', [Validators.required, Validators.pattern(/^https?:\/\/.*$/)]],
      version: ['1.0', [Validators.required]],
      access_config: [{}],
      metadata: [{}]
    });
  }

  // Navigation methods
  nextStep(): void {
    if (this.validateCurrentStep()) {
      this.currentStep.update(step => Math.min(step + 1, 4));
    }
  }

  previousStep(): void {
    this.currentStep.update(step => Math.max(step - 1, 0));
  }

  validateCurrentStep(): boolean {
    const currentStepIndex = this.currentStep();
    
    switch (currentStepIndex) {
      case 0:
        return this.validateBasicInfo();
      case 1:
        return true; // Metadata is optional
      case 2:
        return this.validateLicenses();
      case 3:
        return this.validateDistributions();
      default:
        return true;
    }
  }

  validateBasicInfo(): boolean {
    const controls = ['title_en', 'title_ar', 'description_en', 'description_ar', 'resource_type', 'language', 'version'];
    let isValid = true;
    
    controls.forEach(controlName => {
      const control = this.contentForm.get(controlName);
      if (control) {
        control.markAsTouched();
        if (!control.valid) {
          isValid = false;
        }
      }
    });
    
    if (!isValid) {
      this.message.error('Please fill in all required fields in Basic Information');
    }
    
    return isValid;
  }

  validateLicenses(): boolean {
    const licenses = this.contentForm.get('licenses') as any;
    let isValid = true;
    
    licenses.controls.forEach((license: any) => {
      license.markAllAsTouched();
      if (!license.valid) {
        isValid = false;
      }
    });
    
    if (!isValid) {
      this.message.error('Please complete all license information');
    }
    
    return isValid;
  }

  validateDistributions(): boolean {
    const distributions = this.contentForm.get('distributions') as any;
    let isValid = true;
    
    distributions.controls.forEach((distribution: any) => {
      distribution.markAllAsTouched();
      if (!distribution.valid) {
        isValid = false;
      }
    });
    
    if (!isValid) {
      this.message.error('Please complete all distribution information');
    }
    
    return isValid;
  }

  // Locale switching
  switchLocale(locale: 'en' | 'ar'): void {
    this.currentLocale.set(locale);
    this.selectedTabIndex.set(locale === 'en' ? 0 : 1);
    
    // Update document direction for RTL support
    document.documentElement.dir = locale === 'ar' ? 'rtl' : 'ltr';
  }

  onTabChange(index: number): void {
    this.selectedTabIndex.set(index);
    this.currentLocale.set(index === 0 ? 'en' : 'ar');
  }

  // License management
  getLicenseControls(): any[] {
    return (this.contentForm.get('licenses') as any).controls;
  }

  addLicense(): void {
    const licensesArray = this.contentForm.get('licenses') as any;
    licensesArray.push(this.createLicenseGroup());
  }

  removeLicense(index: number): void {
    const licensesArray = this.contentForm.get('licenses') as any;
    licensesArray.removeAt(index);
  }

  // Distribution management
  getDistributionControls(): any[] {
    return (this.contentForm.get('distributions') as any).controls;
  }

  addDistribution(): void {
    const distributionsArray = this.contentForm.get('distributions') as any;
    distributionsArray.push(this.createDistributionGroup());
  }

  removeDistribution(index: number): void {
    const distributionsArray = this.contentForm.get('distributions') as any;
    distributionsArray.removeAt(index);
  }

  // Metadata helpers
  getMetadataField(field: string): any {
    const metadata = this.contentForm.get('metadata')?.value || {};
    return metadata[field];
  }

  setMetadataField(field: string, event: any): void {
    const metadata = this.contentForm.get('metadata')?.value || {};
    const value = event.target ? event.target.value : event;
    metadata[field] = value;
    this.contentForm.patchValue({ metadata });
  }

  // Helper methods
  getLanguageDisplay(code: string): string {
    const languageMap: { [key: string]: string } = {
      'ar': 'Arabic (العربية)',
      'en': 'English',
      'ur': 'Urdu (اردو)',
      'tr': 'Turkish (Türkçe)',
      'id': 'Indonesian',
      'ms': 'Malay'
    };
    return languageMap[code] || code;
  }

  // Form submission
  async saveDraft(): Promise<void> {
    this.isSaving.set(true);
    
    try {
      const formData = this.prepareFormData();
      formData.status = 'draft';
      
      await this.http.post(`${environment.apiUrl}/content/resources/`, formData).toPromise();
      this.message.success('Draft saved successfully');
    } catch (error) {
      console.error('Error saving draft:', error);
      this.message.error('Failed to save draft');
    } finally {
      this.isSaving.set(false);
    }
  }

  async submitForReview(): Promise<void> {
    if (!this.contentForm.valid) {
      this.message.error('Please complete all required fields');
      return;
    }

    this.isSubmitting.set(true);
    
    try {
      const formData = this.prepareFormData();
      formData.status = 'pending_review';
      
      await this.http.post(`${environment.apiUrl}/content/resources/`, formData).toPromise();
      this.message.success('Content submitted for review successfully');
      this.router.navigate(['/admin/content']);
    } catch (error) {
      console.error('Error submitting content:', error);
      this.message.error('Failed to submit content');
    } finally {
      this.isSubmitting.set(false);
    }
  }

  async submitContent(): Promise<void> {
    await this.submitForReview();
  }

  private prepareFormData(): any {
    const formValue = this.contentForm.value;
    
    return {
      // Resource data
      title_en: formValue.title_en,
      title_ar: formValue.title_ar,
      description_en: formValue.description_en,
      description_ar: formValue.description_ar,
      resource_type: formValue.resource_type,
      language: formValue.language,
      version: formValue.version,
      metadata: formValue.metadata,
      
      // Related data
      licenses: formValue.licenses,
      distributions: formValue.distributions
    };
  }
}
