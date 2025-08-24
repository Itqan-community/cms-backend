import { Component } from '@angular/core';
import { CardModule } from 'primeng/card';
import { ButtonModule } from 'primeng/button';
import { RouterLink } from '@angular/router';

@Component({
  standalone: true,
  selector: 'app-home-auth',
  imports: [CardModule, ButtonModule, RouterLink],
  template: `
    <main class="container py-6">
      <p-card header="Welcome back">
        <div class="card-body">
          <p>Your recent resources and publishers.</p>
          <div class="mt-4">
            <a [routerLink]="['/publishers','itqan']" pButton label="Go to Publisher"></a>
          </div>
        </div>
      </p-card>
    </main>
  `
})
export class HomeAuthPage {}


