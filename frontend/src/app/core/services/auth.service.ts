import { Injectable, signal, inject, PLATFORM_ID } from '@angular/core';
import { isPlatformBrowser } from '@angular/common';
import { Auth0Client, createAuth0Client, User as Auth0User } from '@auth0/auth0-spa-js';
import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import { StateService } from './state.service';
import { User, AuthUser, ApiResponse } from '../models';
import { environment } from '../../../environments/environment';

/**
 * Auth0 SPA SDK integration service
 * Handles authentication flow and integrates with Django backend OIDC
 */
@Injectable({
  providedIn: 'root'
})
export class AuthService {
  private readonly http = inject(HttpClient);
  private readonly router = inject(Router);
  private readonly stateService = inject(StateService);
  private readonly platformId = inject(PLATFORM_ID);

  private auth0Client: Auth0Client | null = null;
  private readonly _isInitialized = signal<boolean>(false);

  readonly isInitialized = this._isInitialized.asReadonly();

  constructor() {
    if (isPlatformBrowser(this.platformId)) {
      this.initializeAuth0();
    } else {
      // For SSR, mark as initialized but don't init Auth0
      this._isInitialized.set(true);
    }
  }

  /**
   * Initialize Auth0 client with configuration from backend
   */
  private async initializeAuth0(): Promise<void> {
    if (!isPlatformBrowser(this.platformId)) {
      return;
    }

    try {
      this.stateService.setAuthLoading(true);

      // Use Auth0 configuration from environment (will be fetched from backend later)
      const config = {
        domain: environment.auth0.domain,
        clientId: environment.auth0.clientId,
        audience: environment.auth0.audience,
        roleClaim: 'https://itqan-cms.com/roles'
      };

      // Create Auth0 client
      this.auth0Client = await createAuth0Client({
        domain: config.domain,
        clientId: config.clientId,
        authorizationParams: {
          redirect_uri: `${window.location.origin}/auth/callback`,
          audience: config.audience,
          scope: 'openid profile email read:current_user update:current_user_metadata'
        },
        cacheLocation: 'localstorage',
        useRefreshTokens: true
      });

      // Check if user is authenticated
      const isAuthenticated = await this.auth0Client.isAuthenticated();
      
      if (isAuthenticated) {
        await this.handleAuthenticatedUser();
      }

      this._isInitialized.set(true);
    } catch (error) {
      console.error('Failed to initialize Auth0:', error);
      this.stateService.setError('Failed to initialize authentication');
    } finally {
      this.stateService.setAuthLoading(false);
    }
  }

  /**
   * Handle authentication callback from Auth0
   */
  async handleAuthCallback(): Promise<void> {
    if (!this.auth0Client) {
      throw new Error('Auth0 client not initialized');
    }

    try {
      this.stateService.setAuthLoading(true);

      // Handle the callback
      await this.auth0Client.handleRedirectCallback();
      
      // Get Auth0 tokens and user info
      const accessToken = await this.auth0Client.getTokenSilently();
      const auth0User = await this.getAuth0User();

      if (!accessToken || !auth0User) {
        throw new Error('Failed to get Auth0 tokens or user information');
      }
      
      // Check if email verification is required
      if (!auth0User.email_verified) {
        // Redirect to email verification page
        await this.router.navigate(['/auth/verify-email']);
        return;
      }
      
      // Exchange Auth0 tokens for Django JWT
      await this.exchangeTokens(accessToken);
      
    } catch (error) {
      console.error('Auth callback error:', error);
      this.stateService.setError('Authentication failed');
      throw error; // Re-throw for the callback component to handle
    } finally {
      this.stateService.setAuthLoading(false);
    }
  }

  /**
   * Exchange Auth0 tokens for Django JWT tokens (Task 15: AUTH-002)
   */
  private async exchangeTokens(accessToken: string): Promise<void> {
    try {
      const response = await firstValueFrom(
        this.http.post<any>(`${environment.apiUrl}/api/auth/exchange/`, {
          access_token: accessToken
        })
      );

      if (response && response.tokens) {
        // Store Django JWT tokens
        await this.storeTokens(response.tokens.access, response.tokens.refresh);
        
        // User state is updated via the stored tokens and will be available via getUserProfile
        
        console.log('Token exchange successful');
      } else {
        throw new Error('Invalid response from token exchange endpoint');
      }
    } catch (error: any) {
      console.error('Token exchange failed:', error);
      
      let errorMessage = 'Token exchange failed. Please try again.';
      if (error.error && error.error.error) {
        errorMessage = error.error.error;
      } else if (error.message) {
        errorMessage = error.message;
      }
      
      throw new Error(errorMessage);
    }
  }

  /**
   * Handle authenticated user - get token and sync with backend
   */
  private async handleAuthenticatedUser(): Promise<void> {
    if (!this.auth0Client) return;

    try {
      // Get ID token for backend authentication
      const idToken = await this.auth0Client.getIdTokenClaims();
      
      if (!idToken || !idToken.__raw) {
        throw new Error('No ID token available');
      }

      // Authenticate with Django backend  
      const authResponse = await firstValueFrom(
        this.http.post<ApiResponse<AuthUser>>(`${environment.apiUrl}/api/auth/login/`, {
          token: idToken.__raw
        })
      );

      if (authResponse.status === 'success' && authResponse.data) {
        // Set user in state
        this.stateService.setCurrentUser(authResponse.data.user);
        
        // Store tokens for API requests
        this.storeTokens(authResponse.data);
        
        console.log('User authenticated successfully:', authResponse.data.user.email);
      } else {
        throw new Error(authResponse.message || 'Backend authentication failed');
      }
      
    } catch (error) {
      console.error('Failed to authenticate with backend:', error);
      this.stateService.setError('Failed to authenticate with backend');
      await this.logout();
    }
  }

  /**
   * Initiate login flow
   */
  async login(redirectUrl?: string): Promise<void> {
    if (!isPlatformBrowser(this.platformId) || !this.auth0Client) {
      throw new Error('Auth0 client not initialized or not in browser');
    }

    try {
      // Store redirect URL for after authentication
      if (redirectUrl && typeof sessionStorage !== 'undefined') {
        sessionStorage.setItem('auth_redirect_url', redirectUrl);
      }

      // Start Auth0 login flow
      await this.auth0Client.loginWithRedirect({
        authorizationParams: {
          prompt: 'login'
        }
      });
    } catch (error) {
      console.error('Login error:', error);
      this.stateService.setError('Failed to initiate login');
    }
  }

  /**
   * Initiate GitHub login flow
   */
  async loginWithGitHub(redirectUrl?: string): Promise<void> {
    if (!isPlatformBrowser(this.platformId) || !this.auth0Client) {
      throw new Error('Auth0 client not initialized or not in browser');
    }

    try {
      // Store redirect URL for after authentication
      if (redirectUrl && typeof sessionStorage !== 'undefined') {
        sessionStorage.setItem('auth_redirect_url', redirectUrl);
      }

      // Start Auth0 login flow with GitHub connection
      await this.auth0Client.loginWithRedirect({
        authorizationParams: {
          prompt: 'login',
          connection: 'github'
        }
      });
    } catch (error) {
      console.error('GitHub login error:', error);
      this.stateService.setError('Failed to initiate GitHub login');
    }
  }

  /**
   * Initiate Google login flow
   */
  async loginWithGoogle(redirectUrl?: string): Promise<void> {
    if (!isPlatformBrowser(this.platformId) || !this.auth0Client) {
      throw new Error('Auth0 client not initialized or not in browser');
    }

    try {
      // Store redirect URL for after authentication
      if (redirectUrl && typeof sessionStorage !== 'undefined') {
        sessionStorage.setItem('auth_redirect_url', redirectUrl);
      }

      // Start Auth0 login flow with Google connection
      await this.auth0Client.loginWithRedirect({
        authorizationParams: {
          prompt: 'login',
          connection: 'google-oauth2'
        }
      });
    } catch (error) {
      console.error('Google login error:', error);
      this.stateService.setError('Failed to initiate Google login');
    }
  }

  /**
   * Initiate registration flow
   */
  async register(): Promise<void> {
    if (!this.auth0Client) {
      throw new Error('Auth0 client not initialized');
    }

    try {
      await this.auth0Client.loginWithRedirect({
        authorizationParams: {
          screen_hint: 'signup',
          prompt: 'login'
        }
      });
    } catch (error) {
      console.error('Registration error:', error);
      this.stateService.setError('Failed to initiate registration');
    }
  }

  /**
   * Initiate GitHub registration flow
   */
  async registerWithGitHub(): Promise<void> {
    if (!this.auth0Client) {
      throw new Error('Auth0 client not initialized');
    }

    try {
      await this.auth0Client.loginWithRedirect({
        authorizationParams: {
          screen_hint: 'signup',
          connection: 'github'
        }
      });
    } catch (error) {
      console.error('GitHub registration error:', error);
      this.stateService.setError('Failed to initiate GitHub registration');
    }
  }

  /**
   * Initiate Google registration flow
   */
  async registerWithGoogle(): Promise<void> {
    if (!this.auth0Client) {
      throw new Error('Auth0 client not initialized');
    }

    try {
      await this.auth0Client.loginWithRedirect({
        authorizationParams: {
          screen_hint: 'signup',
          connection: 'google-oauth2'
        }
      });
    } catch (error) {
      console.error('Google registration error:', error);
      this.stateService.setError('Failed to initiate Google registration');
    }
  }

  /**
   * Logout user
   */
  async logout(): Promise<void> {
    try {
      // Clear local state
      this.stateService.logout();
      this.clearTokens();

      // Logout from Auth0
      if (this.auth0Client) {
        await this.auth0Client.logout({
          logoutParams: {
            returnTo: `${window.location.origin}/auth/login`
          }
        });
      } else {
        // Fallback if Auth0 client not available
        await this.router.navigate(['/auth/login']);
      }
    } catch (error) {
      console.error('Logout error:', error);
      // Force navigation even if logout fails
      await this.router.navigate(['/auth/login']);
    }
  }

  /**
   * Get current Auth0 user
   */
  async getAuth0User(): Promise<Auth0User | undefined> {
    if (!this.auth0Client) return undefined;
    
    try {
      return await this.auth0Client.getUser();
    } catch (error) {
      console.error('Failed to get Auth0 user:', error);
      return undefined;
    }
  }

  /**
   * Get access token for API requests
   */
  async getAccessToken(): Promise<string | null> {
    if (!this.auth0Client) return null;

    try {
      return await this.auth0Client.getTokenSilently();
    } catch (error) {
      console.error('Failed to get access token:', error);
      
      // If token refresh fails, try to re-authenticate
      if (error && typeof error === 'object' && 'error' in error && (error as any).error === 'login_required') {
        await this.login();
      }
      
      return null;
    }
  }

  /**
   * Check if user is authenticated
   */
  async isAuthenticated(): Promise<boolean> {
    if (!this.auth0Client) return false;
    
    try {
      return await this.auth0Client.isAuthenticated();
    } catch (error) {
      console.error('Failed to check authentication status:', error);
      return false;
    }
  }

  /**
   * Refresh user profile from backend
   */
  async refreshUserProfile(): Promise<void> {
    try {
      this.stateService.setAuthLoading(true);

      const response = await firstValueFrom(
        this.http.get<ApiResponse<User>>(`${environment.apiUrl}/auth/profile/`)
      );

      if (response.status === 'success' && response.data) {
        this.stateService.setCurrentUser(response.data);
      }
    } catch (error) {
      console.error('Failed to refresh user profile:', error);
      this.stateService.setError('Failed to refresh user profile');
    } finally {
      this.stateService.setAuthLoading(false);
    }
  }

  /**
   * Update user profile
   */
  async updateUserProfile(updates: Partial<User>): Promise<void> {
    try {
      this.stateService.setAuthLoading(true);

      const response = await firstValueFrom(
        this.http.patch<ApiResponse<User>>(`${environment.apiUrl}/auth/profile/`, updates)
      );

      if (response.status === 'success' && response.data) {
        this.stateService.setCurrentUser(response.data);
      }
    } catch (error) {
      console.error('Failed to update user profile:', error);
      this.stateService.setError('Failed to update user profile');
      throw error;
    } finally {
      this.stateService.setAuthLoading(false);
    }
  }

  /**
   * Check if user has specific role
   */
  hasRole(role: 'Admin' | 'Publisher' | 'Developer' | 'Reviewer'): boolean {
    const currentUser = this.stateService.currentUser();
    return currentUser?.role?.name === role;
  }

  /**
   * Check if user has any of the specified roles
   */
  hasAnyRole(roles: ('Admin' | 'Publisher' | 'Developer' | 'Reviewer')[]): boolean {
    const currentUser = this.stateService.currentUser();
    return roles.includes(currentUser?.role?.name as any);
  }

  /**
   * Store authentication tokens
   */
  private storeTokens(authData: AuthUser): void;
  private storeTokens(accessToken: string, refreshToken: string): void;
  private storeTokens(authDataOrAccessToken: AuthUser | string, refreshToken?: string): void {
    if (isPlatformBrowser(this.platformId) && typeof localStorage !== 'undefined') {
      if (typeof authDataOrAccessToken === 'string') {
        // New format: separate tokens
        localStorage.setItem('itqan_access_token', authDataOrAccessToken);
        if (refreshToken) {
          localStorage.setItem('itqan_refresh_token', refreshToken);
        }
        // For JWT tokens, we'll calculate expiry based on the token itself or set a default
        const defaultExpiry = new Date(Date.now() + 3600000).toISOString(); // 1 hour
        localStorage.setItem('itqan_token_expires_at', defaultExpiry);
      } else {
        // Legacy format: AuthUser object
        localStorage.setItem('itqan_access_token', authDataOrAccessToken.access_token);
        if (authDataOrAccessToken.refresh_token) {
          localStorage.setItem('itqan_refresh_token', authDataOrAccessToken.refresh_token);
        }
        localStorage.setItem('itqan_token_expires_at', authDataOrAccessToken.expires_at);
      }
    }
  }

  /**
   * Clear stored tokens
   */
  private clearTokens(): void {
    if (isPlatformBrowser(this.platformId) && typeof localStorage !== 'undefined') {
      localStorage.removeItem('itqan_access_token');
      localStorage.removeItem('itqan_refresh_token');
      localStorage.removeItem('itqan_token_expires_at');
    }
  }

  /**
   * Get stored access token
   */
  getStoredAccessToken(): string | null {
    if (!isPlatformBrowser(this.platformId) || typeof localStorage === 'undefined') return null;
    return localStorage.getItem('itqan_access_token');
  }

  /**
   * Check if stored token is expired
   */
  isTokenExpired(): boolean {
    if (!isPlatformBrowser(this.platformId) || typeof localStorage === 'undefined') return true;
    
    const expiresAt = localStorage.getItem('itqan_token_expires_at');
    if (!expiresAt) return true;
    
    return new Date(expiresAt) <= new Date();
  }

  /**
   * Force token refresh
   */
  async refreshToken(): Promise<void> {
    if (!this.auth0Client) {
      throw new Error('Auth0 client not initialized');
    }

    try {
      const token = await this.auth0Client.getTokenSilently({
        cacheMode: 'off' // Force refresh
      });
      
      if (token) {
        // Update stored token
        const expiresAt = new Date();
        expiresAt.setHours(expiresAt.getHours() + 1); // Assume 1 hour expiry
        
        if (typeof localStorage !== 'undefined') {
          localStorage.setItem('itqan_access_token', token);
          localStorage.setItem('itqan_token_expires_at', expiresAt.toISOString());
        }
      }
    } catch (error) {
      console.error('Failed to refresh token:', error);
      throw error;
    }
  }
}
