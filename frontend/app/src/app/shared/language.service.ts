import { Injectable, signal, inject } from '@angular/core';
import { TranslationService } from './translation.service';

@Injectable({ providedIn: 'root' })
export class LanguageService {
  private lang = signal<'en' | 'ar'>('en');
  private translationService = inject(TranslationService);
  
  current = this.lang.asReadonly();
  isRtl = () => this.lang() === 'ar';
  
  set(code: 'en' | 'ar') { 
    this.lang.set(code);
    this.translationService.setLanguage(code);
  }
}


