import { Component } from '@angular/core';
import { CardModule } from 'primeng/card';
import { TableModule } from 'primeng/table';
import { ButtonModule } from 'primeng/button';
import { RouterLink } from '@angular/router';

@Component({
  standalone: true,
  selector: 'app-publisher-details',
  imports: [CardModule, TableModule, ButtonModule, RouterLink],
  template: `
    <main class="container py-6">
      <p-card header="Publisher: Itqan">
        <p class="text-muted">Trusted Quranic resources.</p>
        <p-table [value]="resources" class="mt-4">
          <ng-template pTemplate="header">
            <tr>
              <th>Name</th>
              <th>Version</th>
              <th>Lang</th>
              <th>License</th>
              <th></th>
            </tr>
          </ng-template>
          <ng-template pTemplate="body" let-r>
            <tr>
              <td>{{ r.name }}</td>
              <td>{{ r.version }}</td>
              <td>{{ r.lang }}</td>
              <td>{{ r.license }}</td>
              <td><a [routerLink]="['/resources', r.id]" pButton size="small" label="View"></a></td>
            </tr>
          </ng-template>
        </p-table>
      </p-card>
    </main>
  `
})
export class PublisherDetailsPage {
  resources = [
    { id: 'quran-v1', name: 'Quran Text', version: '1.0.0', lang: 'ar', license: 'CC0' },
    { id: 'tafseer', name: 'Tafseer Sample', version: '0.2.1', lang: 'ar', license: 'CC BY' }
  ];
}


