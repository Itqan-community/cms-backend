import { Routes } from '@angular/router';

export const searchRoutes: Routes = [
  {
    path: '',
    loadComponent: () => import('./components/search-home.component').then(m => m.SearchHomeComponent)
  }
];
