import { Routes } from '@angular/router';

export const routes: Routes = [
  { path: 'demo', loadComponent: () => import('./pages/demo-gallery/demo-gallery.page').then(m => m.DemoGalleryPage) },
  { path: 'content-standards', loadComponent: () => import('./pages/content-standards/content-standards.page').then(m => m.ContentStandardsPage) },
  { path: 'home-unauth', loadComponent: () => import('./pages/home-unauth/home-unauth.page').then(m => m.HomeUnauthPage) },
  { path: 'home-auth', loadComponent: () => import('./pages/home-auth/home-auth.page').then(m => m.HomeAuthPage) },
  { path: 'auth/login', loadComponent: () => import('./pages/auth-login/auth-login.page').then(m => m.LoginPage) },
  { path: 'auth/register-oauth', loadComponent: () => import('./pages/auth-register-oauth/auth-register-oauth.page').then(m => m.RegisterGithubGooglePage) },
  { path: 'auth/register-email', loadComponent: () => import('./pages/auth-register-email/auth-register-email.page').then(m => m.RegisterEmailPage) },
  { path: 'auth/profile-capture', loadComponent: () => import('./pages/auth-profile-capture/auth-profile-capture.page').then(m => m.ProfileCapturePage) },
  { path: 'resources/:id', loadComponent: () => import('./pages/resource-details/resource-details.page').then(m => m.ResourceDetailsPage) },
  { path: 'licenses/:id', loadComponent: () => import('./pages/license-details/license-details.page').then(m => m.LicenseDetailsPage) },
  { path: 'publishers/:id', loadComponent: () => import('./pages/publisher-details/publisher-details.page').then(m => m.PublisherDetailsPage) },
  { path: 'demo/resource-dialog', loadComponent: () => import('./pages/dialog-resource/dialog-resource.page').then(m => m.ResourceDetailsDialogPage) },
  { path: 'demo/license-terms-dialog', loadComponent: () => import('./pages/dialog-license-terms/dialog-license-terms.page').then(m => m.LicenseTermsDialogPage) },
  { path: 'demo/license-terms-confirm', loadComponent: () => import('./pages/dialog-license-confirm/dialog-license-confirm.page').then(m => m.LicenseTermsConfirmDialogPage) },
  { path: '', pathMatch: 'full', redirectTo: 'demo' },
  { path: '**', redirectTo: 'demo' }
];
