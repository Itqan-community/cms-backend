import { Routes } from '@angular/router';

export const routes: Routes = [
  // Asset Store Landing page for all users (ADMIN-001 / SF-03)
  {
    path: '',
    loadComponent: () => import('./features/asset-store/asset-store.component').then(m => m.AssetStoreComponent),
    title: 'Itqan CMS - Islamic Content Management System'
  },

  // Content Standards Page (Public Access - ADMIN-002 / SF-04)
  {
    path: 'content-standards',
    loadComponent: () => import('./features/content-standards/content-standards.component').then(m => m.ContentStandardsComponent),
    title: 'Content & Technical Standards - Itqan CMS'
  },

  // Publishers Page (Public)
  {
    path: 'publishers',
    loadComponent: () => import('./features/dashboard/dashboard.component').then(m => m.DashboardComponent), // Placeholder
    title: 'Publishers - Itqan CMS'
  },

  // About Page (Public)
  {
    path: 'about',
    loadComponent: () => import('./features/dashboard/dashboard.component').then(m => m.DashboardComponent), // Placeholder
    title: 'About the Project - Itqan CMS'
  },
  
  // Dashboard
  {
    path: 'dashboard',
    loadComponent: () => import('./features/dashboard/dashboard.component').then(m => m.DashboardComponent),
    title: 'Dashboard - Itqan CMS'
  },
  
  // Authentication
  {
    path: 'auth',
    children: [
      {
        path: 'register',
        loadComponent: () => import('./features/auth/register.component').then(m => m.RegisterComponent),
        title: 'Register - Itqan CMS'
      },
      {
        path: 'login',
        loadComponent: () => import('./features/auth/login.component').then(m => m.LoginComponent),
        title: 'Login - Itqan CMS'
      },
      {
        path: 'verify-email',
        loadComponent: () => import('./features/auth/email-verification.component').then(m => m.EmailVerificationComponent),
        title: 'Email Verification - Itqan CMS'
      },
      {
        path: 'callback',
        loadComponent: () => import('./features/auth/auth-callback.component').then(m => m.AuthCallbackComponent),
        title: 'Authentication - Itqan CMS'
      }
    ]
  },
  
  // Resources (Publisher/Admin)
  {
    path: 'resources',
    loadComponent: () => import('./features/dashboard/dashboard.component').then(m => m.DashboardComponent), // Placeholder
    title: 'Resources - Itqan CMS'
  },
  
  // Access Requests
  {
    path: 'access-requests',
    loadComponent: () => import('./features/dashboard/dashboard.component').then(m => m.DashboardComponent), // Placeholder
    title: 'Access Requests - Itqan CMS'
  },
  
  // Analytics (Admin/Publisher)
  {
    path: 'analytics',
    loadComponent: () => import('./features/dashboard/dashboard.component').then(m => m.DashboardComponent), // Placeholder
    title: 'Analytics - Itqan CMS'
  },
  
  // Administration (Admin only)
  {
    path: 'admin',
    children: [
      {
        path: 'users',
        loadComponent: () => import('./features/dashboard/dashboard.component').then(m => m.DashboardComponent), // Placeholder
        title: 'User Management - Itqan CMS'
      },
      {
        path: 'roles',
        loadComponent: () => import('./features/dashboard/dashboard.component').then(m => m.DashboardComponent), // Placeholder
        title: 'Role Management - Itqan CMS'
      },
      {
        path: 'licenses',
        loadComponent: () => import('./features/dashboard/dashboard.component').then(m => m.DashboardComponent), // Placeholder
        title: 'License Management - Itqan CMS'
      }
    ]
  },
  
  // Profile
  {
    path: 'profile',
    loadComponent: () => import('./features/dashboard/dashboard.component').then(m => m.DashboardComponent), // Placeholder
    title: 'Profile - Itqan CMS'
  },
  
  // Catch-all redirect
  {
    path: '**',
    redirectTo: '/dashboard'
  }
];
