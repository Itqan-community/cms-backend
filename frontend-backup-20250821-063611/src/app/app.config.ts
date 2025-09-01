import { ApplicationConfig, importProvidersFrom } from '@angular/core';
import { provideRouter } from '@angular/router';
import { provideHttpClient } from '@angular/common/http';
import { BrowserAnimationsModule } from '@angular/platform-browser/animations';

// NG-ZORRO imports
import { NZ_I18N, en_US, ar_EG } from 'ng-zorro-antd/i18n';
import { NZ_CONFIG, NzConfig } from 'ng-zorro-antd/core/config';

import { routes } from './app.routes';

// Itqan NG-ZORRO Theme Configuration
const itqanTheme: NzConfig = {
  theme: {
    primaryColor: '#669B80',
    successColor: '#52c41a',
    warningColor: '#faad14',
    errorColor: '#ff4d4f',
    infoColor: '#1890ff',
  },
  form: {
    nzAutoTips: {
      en: {
        required: 'This field is required',
        email: 'Invalid email format'
      },
      ar: {
        required: 'هذا الحقل مطلوب',
        email: 'تنسيق البريد الإلكتروني غير صحيح'
      }
    }
  }
};

export const appConfig: ApplicationConfig = {
  providers: [
    provideRouter(routes),
    provideHttpClient(),
    importProvidersFrom(BrowserAnimationsModule),
    { provide: NZ_I18N, useValue: en_US }, // Default to English
    { provide: NZ_CONFIG, useValue: itqanTheme }
  ]
};