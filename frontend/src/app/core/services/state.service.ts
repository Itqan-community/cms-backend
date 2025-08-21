import { Injectable, signal, computed, effect } from '@angular/core';
import { User, Resource, AccessRequest, DashboardStats } from '../models';

/**
 * Global state management using Angular Signals
 * Replaces RxJS-based state management for better performance and simplicity
 */
@Injectable({
  providedIn: 'root'
})
export class StateService {
  // Authentication state
  private readonly _currentUser = signal<User | null>(null);
  private readonly _isAuthenticated = signal<boolean>(false);
  private readonly _authLoading = signal<boolean>(false);

  // UI state
  private readonly _currentLanguage = signal<'en' | 'ar'>('en');
  private readonly _isRTL = signal<boolean>(false);
  private readonly _sidebarCollapsed = signal<boolean>(false);
  private readonly _theme = signal<'light' | 'dark'>('light');

  // Content state
  private readonly _resources = signal<Resource[]>([]);
  private readonly _selectedResource = signal<Resource | null>(null);
  private readonly _resourcesLoading = signal<boolean>(false);

  // Access requests state
  private readonly _accessRequests = signal<AccessRequest[]>([]);
  private readonly _selectedAccessRequest = signal<AccessRequest | null>(null);
  private readonly _accessRequestsLoading = signal<boolean>(false);

  // Dashboard state
  private readonly _dashboardStats = signal<DashboardStats | null>(null);
  private readonly _dashboardLoading = signal<boolean>(false);

  // Error state
  private readonly _globalError = signal<string | null>(null);
  private readonly _globalLoading = signal<boolean>(false);

  // Public readonly signals
  readonly currentUser = this._currentUser.asReadonly();
  readonly isAuthenticated = this._isAuthenticated.asReadonly();
  readonly authLoading = this._authLoading.asReadonly();

  readonly currentLanguage = this._currentLanguage.asReadonly();
  readonly isRTL = this._isRTL.asReadonly();
  readonly sidebarCollapsed = this._sidebarCollapsed.asReadonly();
  readonly theme = this._theme.asReadonly();

  readonly resources = this._resources.asReadonly();
  readonly selectedResource = this._selectedResource.asReadonly();
  readonly resourcesLoading = this._resourcesLoading.asReadonly();

  readonly accessRequests = this._accessRequests.asReadonly();
  readonly selectedAccessRequest = this._selectedAccessRequest.asReadonly();
  readonly accessRequestsLoading = this._accessRequestsLoading.asReadonly();

  readonly dashboardStats = this._dashboardStats.asReadonly();
  readonly dashboardLoading = this._dashboardLoading.asReadonly();

  readonly globalError = this._globalError.asReadonly();
  readonly globalLoading = this._globalLoading.asReadonly();

  // Computed signals for derived state
  readonly userRole = computed(() => this._currentUser()?.role?.name || null);
  readonly isAdmin = computed(() => this.userRole() === 'Admin');
  readonly isPublisher = computed(() => this.userRole() === 'Publisher');
  readonly isDeveloper = computed(() => this.userRole() === 'Developer');
  readonly isReviewer = computed(() => this.userRole() === 'Reviewer');

  readonly userDisplayName = computed(() => {
    const user = this._currentUser();
    if (!user) return '';
    return `${user.first_name} ${user.last_name}`.trim() || user.email;
  });

  readonly pendingAccessRequests = computed(() => 
    this._accessRequests().filter(req => req.status === 'pending')
  );

  readonly approvedAccessRequests = computed(() => 
    this._accessRequests().filter(req => req.status === 'approved')
  );

  readonly userAccessRequests = computed(() => {
    const currentUserId = this._currentUser()?.id;
    if (!currentUserId) return [];
    return this._accessRequests().filter(req => req.requester_id === currentUserId);
  });

  readonly publishedResources = computed(() => 
    this._resources().filter(resource => resource.published_at !== null)
  );

  readonly userResources = computed(() => {
    const currentUserId = this._currentUser()?.id;
    if (!currentUserId) return [];
    return this._resources().filter(resource => resource.publisher_id === currentUserId);
  });

  readonly hasAnyLoading = computed(() => 
    this._authLoading() || 
    this._resourcesLoading() || 
    this._accessRequestsLoading() || 
    this._dashboardLoading() || 
    this._globalLoading()
  );

  constructor() {
    // Effect to update RTL state when language changes
    effect(() => {
      const lang = this._currentLanguage();
      this._isRTL.set(lang === 'ar');
      
      // Update document direction
      if (typeof document !== 'undefined') {
        document.documentElement.dir = lang === 'ar' ? 'rtl' : 'ltr';
        document.documentElement.lang = lang;
      }
    });

    // Effect to persist language preference
    effect(() => {
      const lang = this._currentLanguage();
      if (typeof localStorage !== 'undefined') {
        localStorage.setItem('itqan_language', lang);
      }
    });

    // Effect to persist theme preference
    effect(() => {
      const theme = this._theme();
      if (typeof localStorage !== 'undefined') {
        localStorage.setItem('itqan_theme', theme);
        document.documentElement.setAttribute('data-theme', theme);
      }
    });

    // Effect to persist sidebar state
    effect(() => {
      const collapsed = this._sidebarCollapsed();
      if (typeof localStorage !== 'undefined') {
        localStorage.setItem('itqan_sidebar_collapsed', collapsed.toString());
      }
    });

    // Initialize from localStorage
    this.initializeFromStorage();
  }

  // Authentication actions
  setCurrentUser(user: User | null): void {
    this._currentUser.set(user);
    this._isAuthenticated.set(user !== null);
  }

  setAuthLoading(loading: boolean): void {
    this._authLoading.set(loading);
  }

  logout(): void {
    this._currentUser.set(null);
    this._isAuthenticated.set(false);
    this._accessRequests.set([]);
    this._resources.set([]);
    this._selectedResource.set(null);
    this._selectedAccessRequest.set(null);
    this._dashboardStats.set(null);
    this.clearError();
  }

  // UI actions
  setLanguage(language: 'en' | 'ar'): void {
    this._currentLanguage.set(language);
  }

  toggleLanguage(): void {
    const current = this._currentLanguage();
    this._currentLanguage.set(current === 'en' ? 'ar' : 'en');
  }

  setSidebarCollapsed(collapsed: boolean): void {
    this._sidebarCollapsed.set(collapsed);
  }

  toggleSidebar(): void {
    this._sidebarCollapsed.update(collapsed => !collapsed);
  }

  setTheme(theme: 'light' | 'dark'): void {
    this._theme.set(theme);
  }

  toggleTheme(): void {
    const current = this._theme();
    this._theme.set(current === 'light' ? 'dark' : 'light');
  }

  // Resource actions
  setResources(resources: Resource[]): void {
    this._resources.set(resources);
  }

  addResource(resource: Resource): void {
    this._resources.update(resources => [...resources, resource]);
  }

  updateResource(updatedResource: Resource): void {
    this._resources.update(resources => 
      resources.map(resource => 
        resource.id === updatedResource.id ? updatedResource : resource
      )
    );
  }

  removeResource(resourceId: string): void {
    this._resources.update(resources => 
      resources.filter(resource => resource.id !== resourceId)
    );
  }

  setSelectedResource(resource: Resource | null): void {
    this._selectedResource.set(resource);
  }

  setResourcesLoading(loading: boolean): void {
    this._resourcesLoading.set(loading);
  }

  // Access request actions
  setAccessRequests(requests: AccessRequest[]): void {
    this._accessRequests.set(requests);
  }

  addAccessRequest(request: AccessRequest): void {
    this._accessRequests.update(requests => [...requests, request]);
  }

  updateAccessRequest(updatedRequest: AccessRequest): void {
    this._accessRequests.update(requests => 
      requests.map(request => 
        request.id === updatedRequest.id ? updatedRequest : request
      )
    );
  }

  removeAccessRequest(requestId: string): void {
    this._accessRequests.update(requests => 
      requests.filter(request => request.id !== requestId)
    );
  }

  setSelectedAccessRequest(request: AccessRequest | null): void {
    this._selectedAccessRequest.set(request);
  }

  setAccessRequestsLoading(loading: boolean): void {
    this._accessRequestsLoading.set(loading);
  }

  // Dashboard actions
  setDashboardStats(stats: DashboardStats | null): void {
    this._dashboardStats.set(stats);
  }

  setDashboardLoading(loading: boolean): void {
    this._dashboardLoading.set(loading);
  }

  // Error handling
  setError(error: string | null): void {
    this._globalError.set(error);
  }

  clearError(): void {
    this._globalError.set(null);
  }

  setGlobalLoading(loading: boolean): void {
    this._globalLoading.set(loading);
  }

  // Utility methods
  private initializeFromStorage(): void {
    if (typeof localStorage === 'undefined') return;

    // Initialize language
    const savedLanguage = localStorage.getItem('itqan_language') as 'en' | 'ar';
    if (savedLanguage && ['en', 'ar'].includes(savedLanguage)) {
      this._currentLanguage.set(savedLanguage);
    }

    // Initialize theme
    const savedTheme = localStorage.getItem('itqan_theme') as 'light' | 'dark';
    if (savedTheme && ['light', 'dark'].includes(savedTheme)) {
      this._theme.set(savedTheme);
    }

    // Initialize sidebar state
    const savedSidebarState = localStorage.getItem('itqan_sidebar_collapsed');
    if (savedSidebarState) {
      this._sidebarCollapsed.set(savedSidebarState === 'true');
    }
  }

  // Batch operations for performance
  batchUpdateResources(updates: Partial<Resource>[]): void {
    this._resources.update(resources => {
      const resourceMap = new Map(resources.map(r => [r.id, r]));
      
      updates.forEach(update => {
        if (update.id && resourceMap.has(update.id)) {
          const existing = resourceMap.get(update.id)!;
          resourceMap.set(update.id, { ...existing, ...update });
        }
      });
      
      return Array.from(resourceMap.values());
    });
  }

  batchUpdateAccessRequests(updates: Partial<AccessRequest>[]): void {
    this._accessRequests.update(requests => {
      const requestMap = new Map(requests.map(r => [r.id, r]));
      
      updates.forEach(update => {
        if (update.id && requestMap.has(update.id)) {
          const existing = requestMap.get(update.id)!;
          requestMap.set(update.id, { ...existing, ...update });
        }
      });
      
      return Array.from(requestMap.values());
    });
  }

  // Reset methods for testing
  resetState(): void {
    this._currentUser.set(null);
    this._isAuthenticated.set(false);
    this._authLoading.set(false);
    this._resources.set([]);
    this._selectedResource.set(null);
    this._resourcesLoading.set(false);
    this._accessRequests.set([]);
    this._selectedAccessRequest.set(null);
    this._accessRequestsLoading.set(false);
    this._dashboardStats.set(null);
    this._dashboardLoading.set(false);
    this._globalError.set(null);
    this._globalLoading.set(false);
  }
}
