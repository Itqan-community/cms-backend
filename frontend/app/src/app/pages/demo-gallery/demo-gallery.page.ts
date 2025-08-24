import { Component } from '@angular/core';
import { RouterLink } from '@angular/router';
import { CardModule } from 'primeng/card';
import { ButtonModule } from 'primeng/button';

@Component({
  standalone: true,
  selector: 'app-demo-gallery',
  imports: [RouterLink, CardModule, ButtonModule],
  template: `
    <main class="container py-6">
      <p-card header="Demo Gallery">
        <div class="flex flex-col gap-2">
          <a routerLink="/content-standards" pButton label="Content Standards"></a>
          <a routerLink="/home-unauth" pButton label="Home (Unauth)"></a>
          <a routerLink="/home-auth" pButton label="Home (Auth)"></a>
          <a routerLink="/auth/login" pButton label="Login"></a>
          <a routerLink="/auth/register-oauth" pButton label="Register (GitHub/Google)"></a>
          <a routerLink="/auth/register-email" pButton label="Register (Email)"></a>
          <a routerLink="/auth/profile-capture" pButton label="Profile Capture"></a>
          <a [routerLink]="['/resources', '123']" pButton label="Resource Details"></a>
          <a [routerLink]="['/licenses', 'cc0']" pButton label="License Details"></a>
          <a [routerLink]="['/publishers', 'itqan']" pButton label="Publisher Details"></a>
          <a routerLink="/demo/resource-dialog" pButton label="Resource Dialog"></a>
          <a routerLink="/demo/license-terms-dialog" pButton label="License Terms Dialog"></a>
          <a routerLink="/demo/license-terms-confirm" pButton label="License Terms Confirm"></a>
        </div>
      </p-card>
    </main>
  `
})
export class DemoGalleryPage {}


