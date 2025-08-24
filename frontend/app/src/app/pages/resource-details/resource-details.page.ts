import { Component } from '@angular/core';
import { CardModule } from 'primeng/card';
import { ButtonModule } from 'primeng/button';
import { ChipModule } from 'primeng/chip';
import { RouterLink } from '@angular/router';

@Component({
  standalone: true,
  selector: 'app-resource-details',
  imports: [CardModule, ButtonModule, ChipModule, RouterLink],
  template: `
    <main class="container py-6">
      <p-card header="Resource: Quran Text v1">
        <div class="card-body">
          <p>Arabic text with diacritics; format: JSON; size: 12MB.</p>
          <div class="flex gap-2 mt-4">
            <p-chip label="CC0"></p-chip>
            <p-chip label="Arabic"></p-chip>
            <p-chip label="v1.0.0"></p-chip>
          </div>
          <div class="mt-4">
            <a routerLink="/demo/license-terms-dialog" pButton label="View License Terms"></a>
            <a routerLink="/demo/resource-dialog" class="ms-2" pButton label="Open Details Popup"></a>
          </div>
        </div>
      </p-card>
    </main>
  `
})
export class ResourceDetailsPage {}


