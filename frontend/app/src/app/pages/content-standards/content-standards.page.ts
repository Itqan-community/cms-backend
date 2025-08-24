import { Component } from '@angular/core';
import { CardModule } from 'primeng/card';

@Component({
  standalone: true,
  selector: 'app-content-standards',
  imports: [CardModule],
  template: `
    <main class="container py-6">
      <p-card header="Content Standards">
        <div class="card-body">
          <p class="text-muted">Guidelines for Quranic data uploads, formats, and metadata.</p>
          <ul class="mt-4">
            <li>Use UTF-8; normalize diacritics.</li>
            <li>Provide license and attribution metadata.</li>
            <li>Include language codes and schema version.</li>
          </ul>
        </div>
      </p-card>
    </main>
  `
})
export class ContentStandardsPage {}


