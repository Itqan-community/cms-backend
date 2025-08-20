import { Injectable, signal } from '@angular/core';
import { Router } from '@angular/router';
import { createAuth0Client, Auth0Client, User } from '@auth0/auth0-spa-js';
import { environment } from '../../../environments/environment';

@Injectable({
  providedIn: 'root'
})
export class AuthService {
  private auth0Client: Auth0Client | null = null;
  
  // Angular Signals for reactive state management
  public user = signal<User | null>(null);
  public isAuthenticated = signal<boolean>(false);
  public isLoading = signal<boolean>(true);
  public error = signal<string | null>(null);

  constructor(private router: Router) {
    this.initializeAuth0();
  }

  private async initializeAuth0(): Promise<void> {
    try {
      this.auth0Client = await createAuth0Client({
        domain: environment.auth0.domain,
        clientId: environment.auth0.clientId,
        authorizationParams: {
          redirect_uri: environment.auth0.redirectUri,
          audience: environment.auth0.audience,
          scope: environment.auth0.scope
        },
        cacheLocation: 'localstorage'
      });

      // Handle the callback if we're returning from Auth0
      if (window.location.search.includes('code=')) {
        await this.handleAuthCallback();
      }

      // Check if user is already authenticated
      const isAuthenticated = await this.auth0Client.isAuthenticated();
      this.isAuthenticated.set(isAuthenticated);

      if (isAuthenticated) {
        const user = await this.auth0Client.getUser();
        this.user.set(user || null);
      }

    } catch (error) {
      console.error('Auth0 initialization error:', error);
      this.error.set('Failed to initialize authentication');
    } finally {
      this.isLoading.set(false);
    }
  }

  async login(): Promise<void> {
    if (!this.auth0Client) {
      throw new Error('Auth0 client not initialized');
    }

    try {
      await this.auth0Client.loginWithRedirect({
        authorizationParams: {
          screen_hint: 'login'
        }
      });
    } catch (error) {
      console.error('Login error:', error);
      this.error.set('Failed to login');
    }
  }

  async register(): Promise<void> {
    if (!this.auth0Client) {
      throw new Error('Auth0 client not initialized');
    }

    try {
      await this.auth0Client.loginWithRedirect({
        authorizationParams: {
          screen_hint: 'signup'
        }
      });
    } catch (error) {
      console.error('Registration error:', error);
      this.error.set('Failed to register');
    }
  }

  async logout(): Promise<void> {
    if (!this.auth0Client) {
      return;
    }

    try {
      await this.auth0Client.logout({
        logoutParams: {
          returnTo: window.location.origin
        }
      });
      
      this.user.set(null);
      this.isAuthenticated.set(false);
    } catch (error) {
      console.error('Logout error:', error);
      this.error.set('Failed to logout');
    }
  }

  async getAccessToken(): Promise<string | undefined> {
    if (!this.auth0Client) {
      return undefined;
    }

    try {
      return await this.auth0Client.getTokenSilently();
    } catch (error) {
      console.error('Token retrieval error:', error);
      return undefined;
    }
  }

  private async handleAuthCallback(): Promise<void> {
    if (!this.auth0Client) {
      return;
    }

    try {
      await this.auth0Client.handleRedirectCallback();
      
      const isAuthenticated = await this.auth0Client.isAuthenticated();
      this.isAuthenticated.set(isAuthenticated);

      if (isAuthenticated) {
        const user = await this.auth0Client.getUser();
        this.user.set(user || null);
        
        // Navigate to dashboard after successful login
        this.router.navigate(['/dashboard']);
      }
    } catch (error) {
      console.error('Auth callback error:', error);
      this.error.set('Authentication callback failed');
      this.router.navigate(['/']);
    }
  }
}
