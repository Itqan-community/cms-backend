import { Routes } from '@angular/router';

export const routes: Routes = [
  {
    path: '',
    redirectTo: '/dashboard',
    pathMatch: 'full'
  },
  {
    path: 'auth',
    loadChildren: () => import('./features/auth/auth.routes').then(m => m.authRoutes)
  },
  {
    path: 'dashboard',
    loadChildren: () => import('./features/dashboard/dashboard.routes').then(m => m.dashboardRoutes)
  },
  {
    path: 'admin',
    loadChildren: () => import('./features/admin/admin.routes').then(m => m.adminRoutes)
  },
  {
    path: 'public',
    loadChildren: () => import('./features/public/public.routes').then(m => m.publicRoutes)
  },
  {
    path: 'search',
    loadChildren: () => import('./features/search/search.routes').then(m => m.searchRoutes)
  },
  {
    path: 'licensing',
    loadChildren: () => import('./features/licensing/licensing.routes').then(m => m.licensingRoutes)
  },
  {
    path: 'callback',
    loadComponent: () => import('./features/auth/components/auth-callback.component').then(m => m.AuthCallbackComponent)
  },
  {
    path: '**',
    redirectTo: '/dashboard'
  }
];