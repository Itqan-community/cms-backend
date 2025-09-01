import { Routes } from '@angular/router';

export const licensingRoutes: Routes = [
  {
    path: '',
    loadComponent: () => import('./components/licensing-home.component').then(m => m.LicensingHomeComponent)
  }
];
