import { Component } from '@angular/core';
import { CardModule } from 'primeng/card';
import { ButtonModule } from 'primeng/button';
import { RouterLink } from '@angular/router';

@Component({
  standalone: true,
  selector: 'app-home-unauth',
  imports: [CardModule, ButtonModule, RouterLink],
  template: `
    <main class="container py-6">
      <div class="row">
        <div class="col-6">
          <p-card header="Itqan CMS">
            <div class="card-body">
              <p>Open Quranic data for developers and publishers.</p>
              <a routerLink="/auth/login" pButton label="Login"></a>
              <a routerLink="/auth/register-email" class="ms-2" pButton label="Register"></a>
            </div>
          </p-card>
        </div>
      </div>
    </main>
  `
})
export class HomeUnauthPage {}


