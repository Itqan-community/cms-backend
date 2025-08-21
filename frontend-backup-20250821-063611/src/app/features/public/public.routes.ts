import { Routes } from '@angular/router';

export const publicRoutes: Routes = [
  {
    path: '',
    loadComponent: () => import('./components/public-home.component').then(m => m.PublicHomeComponent)
  }
];
