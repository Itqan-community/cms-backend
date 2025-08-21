import { Component, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterOutlet, Router, NavigationEnd } from '@angular/router';
import { IslamicLayoutComponent } from './layouts/islamic-layout.component';
import { AuthService } from './core/services/auth.service';
import { StateService } from './core/services/state.service';
import { I18nService } from './core/services/i18n.service';
import { filter, map } from 'rxjs/operators';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, RouterOutlet, IslamicLayoutComponent],
  template: `
    @if (shouldUseIslamicLayout()) {
      <app-islamic-layout></app-islamic-layout>
    } @else {
      <router-outlet></router-outlet>
    }
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
  private readonly router = inject(Router);

  title = 'Itqan CMS';
  private currentRoute = '';

  async ngOnInit(): Promise<void> {
    // Initialize services
    console.log('🚀 Initializing Itqan CMS...');
    
    // Wait for Auth0 to initialize
    while (!this.authService.isInitialized()) {
      await new Promise(resolve => setTimeout(resolve, 100));
    }
    
    // Track current route for layout decisions
    this.router.events.pipe(
      filter(event => event instanceof NavigationEnd),
      map(event => (event as NavigationEnd).url)
    ).subscribe(url => {
      this.currentRoute = url;
    });
    
    console.log('✅ Itqan CMS initialized successfully');
  }

  shouldUseIslamicLayout(): boolean {
    // Use standalone layout for landing page only
    if (this.currentRoute === '/' || this.currentRoute === '') {
      return false;
    }
    
    // Use Islamic layout for all other routes
    return true;
  }
}
