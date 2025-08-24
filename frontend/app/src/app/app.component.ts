import { Component, effect, inject } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { LanguageService } from './shared/language.service';
import { ButtonModule } from 'primeng/button';

@Component({
  selector: 'app-root',
  imports: [RouterOutlet, ButtonModule],
  template: `
    <header class="bg-surface px-4 py-6">
      <div class="container flex justify-between items-center">
        <h1 class="text-dark">Itqan CMS</h1>
        <div class="flex items-center gap-2">
          <button pButton label="LTR" (click)="lang.set('en')" [outlined]="lang.current()!=='en'"></button>
          <button pButton label="RTL" (click)="lang.set('ar')" [outlined]="lang.current()!=='ar'"></button>
        </div>
      </div>
    </header>
    <router-outlet></router-outlet>
  `,
  styleUrl: './app.component.scss'
})
export class AppComponent {
  lang = inject(LanguageService);
  constructor() {
    effect(() => {
      const rtl = this.lang.isRtl();
      document.documentElement.setAttribute('dir', rtl ? 'rtl' : 'ltr');
      document.documentElement.lang = this.lang.current();
    });
  }
}
