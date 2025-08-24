import { Injectable, signal } from '@angular/core';

@Injectable({ providedIn: 'root' })
export class LanguageService {
  private lang = signal<'en' | 'ar'>('en');
  current = this.lang.asReadonly();
  isRtl = () => this.lang() === 'ar';
  set(code: 'en' | 'ar') { this.lang.set(code); }
}


