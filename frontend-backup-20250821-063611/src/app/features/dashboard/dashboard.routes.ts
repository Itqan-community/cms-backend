import { Routes } from '@angular/router';

export const dashboardRoutes: Routes = [
  {
    path: '',
    loadComponent: () => import('./components/dashboard-home.component').then(m => m.DashboardHomeComponent)
  },
  {
    path: 'profile',
    loadComponent: () => import('./components/user-profile.component').then(m => m.UserProfileComponent)
  }
];
