import { ApplicationConfig, provideZoneChangeDetection, importProvidersFrom } from '@angular/core';
import { provideRouter } from '@angular/router';
import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { BrowserAnimationsModule } from '@angular/platform-browser/animations';

import { registerLocaleData } from '@angular/common';
import localeEn from '@angular/common/locales/en';
import localeAr from '@angular/common/locales/ar';

// NG-ZORRO imports
import { provideNzI18n, en_US, ar_EG } from 'ng-zorro-antd/i18n';
import { provideNzIcons } from 'ng-zorro-antd/icon';
import { IconDefinition } from '@ant-design/icons-angular';
import * as AllIcons from '@ant-design/icons-angular/icons';

import { routes } from './app.routes';

// Register locales
registerLocaleData(localeEn);
registerLocaleData(localeAr);

// Get all icons for NG-ZORRO
const antDesignIcons: IconDefinition[] = Object.keys(AllIcons).map(key => (AllIcons as any)[key]);

export const appConfig: ApplicationConfig = {
  providers: [
    // Angular core providers
    provideZoneChangeDetection({ eventCoalescing: true }),
    provideRouter(routes),
    provideHttpClient(withInterceptors([])), // HTTP interceptors will be added later
    
    // Animations for NG-ZORRO
    importProvidersFrom(BrowserAnimationsModule),
    
    // NG-ZORRO providers
    provideNzI18n(en_US), // Default to English, will be changed dynamically
    provideNzIcons(antDesignIcons),
  ]
};
