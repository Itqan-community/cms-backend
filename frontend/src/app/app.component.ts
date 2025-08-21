import { Component, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { IslamicLayoutComponent } from './layouts/islamic-layout.component';
import { AuthService } from './core/services/auth.service';
import { StateService } from './core/services/state.service';
import { I18nService } from './core/services/i18n.service';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, IslamicLayoutComponent],
  template: `
    <app-islamic-layout></app-islamic-layout>
  `,
  styles: [`
    :host {
      display: block;
      min-height: 100vh;
    }
  `]
})
export class AppComponent implements OnInit {
  private readonly authService = inject(AuthService);
  private readonly stateService = inject(StateService);
  private readonly i18nService = inject(I18nService);

  title = 'Itqan CMS';

  async ngOnInit(): Promise<void> {
    // Initialize services
    console.log('🚀 Initializing Itqan CMS...');
    
    // Wait for Auth0 to initialize
    while (!this.authService.isInitialized()) {
      await new Promise(resolve => setTimeout(resolve, 100));
    }
    
    console.log('✅ Itqan CMS initialized successfully');
  }
}
