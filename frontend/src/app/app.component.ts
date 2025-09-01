import { Component, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterOutlet, Router, NavigationEnd } from '@angular/router';
import { TopNavigationComponent } from './shared/components/top-navigation.component';
import { AuthService } from './core/services/auth.service';
import { StateService } from './core/services/state.service';
import { I18nService } from './core/services/i18n.service';
import { filter, map } from 'rxjs/operators';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, RouterOutlet, TopNavigationComponent],
  templateUrl: './app.component.html',
  styles: [`
    :host {
      display: block;
      min-height: 100vh;
      background: #fafafa;
    }
    
    /* Global Islamic theme styles */
    * {
      box-sizing: border-box;
    }
    
    /* Arabic font support */
    .arabic-text {
      font-family: 'Noto Sans Arabic', 'IBM Plex Sans Arabic', sans-serif;
      direction: rtl;
      text-align: right;
    }
    
    /* RTL support */
    [dir="rtl"] {
      direction: rtl;
      text-align: right;
    }
    
    [dir="ltr"] {
      direction: ltr;
      text-align: left;
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
    
    // Initialize i18n service
    this.i18nService.initialize();
    
    // Wait for Auth0 to initialize
    while (!this.authService.isInitialized()) {
      await new Promise(resolve => setTimeout(resolve, 100));
    }
    
    console.log('✅ Itqan CMS initialized successfully');
  }
}
