import { Component } from '@angular/core';
import { CardModule } from 'primeng/card';
import { ButtonModule } from 'primeng/button';

@Component({
  standalone: true,
  selector: 'app-license-details',
  imports: [CardModule, ButtonModule],
  template: `
    <main class="container py-6">
      <p-card header="License: CC0">
        <div class="card-body">
          <p class="text-muted">Public domain dedication.</p>
          <ul class="mt-4">
            <li>Free to copy, modify, distribute.</li>
            <li>No attribution required.</li>
          </ul>
          <button class="mt-4" pButton label="Accept & Download"></button>
        </div>
      </p-card>
    </main>
  `
})
export class LicenseDetailsPage {}


